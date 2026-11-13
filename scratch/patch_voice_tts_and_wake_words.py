# -*- coding: utf-8 -*-
"""
scratch/patch_voice_tts_and_wake_words.py
Adds wake word detection for 'hey kitty', 'kitty', 'cat', 'coding agent terminal', 'hey cat'
and bidirectional TTS speech output to calc_terminal/voice.py
"""
import re

with open("calc_terminal/voice.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add WAKE_WORDS definition
wake_def = '''# Official Wake Words / Activation Phrases
WAKE_WORDS = ["hey kitty", "kitty", "cat", "coding agent terminal", "hey cat"]


def is_wake_word(phrase: str) -> bool:
    """Returns True if the phrase matches any official CAT wake-words."""
    if not phrase:
        return False
    norm = phrase.strip().lower()
    return any(w in norm for w in WAKE_WORDS)
'''

if "WAKE_WORDS = [" not in code:
    code = code.replace('class VoiceState(enum.Enum):', wake_def + '\n\nclass VoiceState(enum.Enum):')

# 2. Add TTS speaking methods to VoiceManager
tts_methods = '''    def is_wake_word_phrase(self, text: str) -> bool:
        """Returns True if text contains any recognized wake phrase."""
        return is_wake_word(text)

    def set_voice_output_enabled(self, enabled: bool) -> None:
        """Toggle text-to-speech output generation."""
        self._voice_output_enabled = bool(enabled)

    def is_voice_output_enabled(self) -> bool:
        return getattr(self, "_voice_output_enabled", True)

    def stop_speaking(self) -> None:
        """Interrupt and cancel any active speech synthesis output."""
        try:
            self._speaking_stop_event.set()
        except Exception:
            pass
        if self.state == VoiceState.SPEAKING:
            self.state = VoiceState.IDLE
            self._notify()

    def speak_text(self, text: str) -> None:
        """Synthesize and speak text out loud asynchronously (bidirectional voice)."""
        if not getattr(self, "_voice_output_enabled", True) or not text:
            return

        # Clean text for clean speech: remove code blocks, markdown stars, links
        clean = re.sub(r'```[\\s\\S]*?```', '', text)
        clean = re.sub(r'`[^`]+`', '', clean)
        clean = re.sub(r'\\[([^\\]]+)\\]\\([^\\)]+\\)', r'\\1', clean)
        clean = re.sub(r'[#*_\`~>]', '', clean).strip()
        if not clean:
            return

        # Truncate very long prose for audio speech (max 300 words)
        words = clean.split()
        if len(words) > 300:
            clean = " ".join(words[:300]) + "..."

        self._speaking_stop_event.clear()
        threading.Thread(target=self._speak_worker, args=(clean,), daemon=True).start()

    def _speak_worker(self, text: str) -> None:
        """Background speech synthesis worker using platform audio engine."""
        prev_state = self.state
        self.state = VoiceState.SPEAKING
        self._notify()
        try:
            if sys.platform == "win32":
                try:
                    import win32com.client
                    import pythoncom
                    pythoncom.CoInitialize()
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    # 1 = SVSFlagsAsync
                    speaker.Speak(text, 1)
                    while speaker.Status.RunningState != 1:
                        if self._speaking_stop_event.is_set():
                            speaker.Speak("", 2)  # SVSFPurgeBeforeSpeak
                            break
                        time.sleep(0.05)
                except Exception:
                    # Fallback to PowerShell speech synthesis
                    import subprocess
                    ps_cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text[:200]}')"
                    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=10)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["say", text[:300]], capture_output=True, timeout=15)
            else:
                import subprocess
                for cmd in ["espeak", "spd-say"]:
                    try:
                        subprocess.run([cmd, text[:300]], capture_output=True, timeout=15)
                        break
                    except Exception:
                        pass
        except Exception as e:
            pass
        finally:
            if self.state == VoiceState.SPEAKING:
                self.state = VoiceState.IDLE
                self._notify()
'''

if "def speak_text(" not in code:
    idx = code.find("def stop_and_transcribe(self)")
    assert idx != -1, "Could not find stop_and_transcribe"
    code = code[:idx] + tts_methods + "\n    " + code[idx:]

# 3. Initialize _speaking_stop_event in __init__
init_code = '''        self._voice_output_enabled = True
        self._speaking_stop_event = threading.Event()'''

if "_speaking_stop_event" not in code:
    code = code.replace("self._transcribed_text = \"\"", "self._transcribed_text = \"\"\n" + init_code)

with open("calc_terminal/voice.py", "w", encoding="utf-8") as f:
    f.write(code)

print("calc_terminal/voice.py successfully patched with wake words and bidirectional TTS!")

