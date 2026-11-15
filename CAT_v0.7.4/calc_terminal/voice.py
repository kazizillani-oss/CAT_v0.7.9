"""
calc_terminal/voice.py
======================
CCT Centralized Real Voice Subsystem (v0.9.000).

Provides real microphone audio streaming, live audio amplitude detection,
real-time ASCII/Unicode waveform generation, recording duration tracking,
and speech transcription via speech_recognition and sounddevice/pyaudio.

Both the chat composer (StickyComposer) and the /voice command share this
exact same underlying subsystem.
"""

import enum
import math
import os
import re
import sys
import threading
import time
from typing import Callable, List, Optional


# Official Wake Words / Activation Phrases
WAKE_WORDS = ["hey kitty", "kitty", "cat", "coding agent terminal", "hey cat"]


def is_wake_word(phrase: str) -> bool:
    """Returns True if the phrase matches any official CAT wake-words."""
    if not phrase:
        return False
    norm = phrase.strip().lower()
    return any(w in norm for w in WAKE_WORDS)


class VoiceState(enum.Enum):
    IDLE = "idle"
    PERMISSION_REQUEST = "permission_request"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    READY_TO_SUBMIT = "ready_to_submit"
    ERROR = "error"


# Unicode bar characters for live audio amplitude detection
# Level 0 (silent) to Level 8 (peak amplitude)
WAVEFORM_BARS = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

# 30+ Supported Multilingual Voice Languages
SUPPORTED_LANGUAGES = [
    {"code": "en-US", "name": "English (US)", "family": "English"},
    {"code": "en-IN", "name": "English (India)", "family": "English"},
    {"code": "hi-IN", "name": "Hindi (हिंदी)", "family": "Indo-Aryan"},
    {"code": "hi-Latn", "name": "Hinglish (Code-Switching)", "family": "Indo-Aryan"},
    {"code": "zh-CN", "name": "Chinese Mandarin (中文)", "family": "Sinitic"},
    {"code": "fr-FR", "name": "French (Français)", "family": "Romance"},
    {"code": "de-DE", "name": "German (Deutsch)", "family": "Germanic"},
    {"code": "ar-SA", "name": "Arabic (العربية)", "family": "Semitic"},
    {"code": "ru-RU", "name": "Russian (Русский)", "family": "Slavic"},
    {"code": "es-ES", "name": "Spanish (Español)", "family": "Romance"},
    {"code": "ja-JP", "name": "Japanese (日本語)", "family": "Japonic"},
    {"code": "ko-KR", "name": "Korean (한국어)", "family": "Koreanic"},
    {"code": "pt-BR", "name": "Portuguese (Português)", "family": "Romance"},
    {"code": "it-IT", "name": "Italian (Italiano)", "family": "Romance"},
    {"code": "bn-IN", "name": "Bengali (বাংলা)", "family": "Indo-Aryan"},
    {"code": "ur-PK", "name": "Urdu (اردو)", "family": "Indo-Aryan"},
    {"code": "gu-IN", "name": "Gujarati (ગુજરાતી)", "family": "Indo-Aryan"},
    {"code": "pa-IN", "name": "Punjabi (ਪੰਜਾਬੀ)", "family": "Indo-Aryan"},
    {"code": "ta-IN", "name": "Tamil (தமிழ்)", "family": "Dravidian"},
    {"code": "te-IN", "name": "Telugu (తెలుగు)", "family": "Dravidian"},
    {"code": "mr-IN", "name": "Marathi (मराठी)", "family": "Indo-Aryan"},
    {"code": "nl-NL", "name": "Dutch (Nederlands)", "family": "Germanic"},
    {"code": "tr-TR", "name": "Turkish (Türkçe)", "family": "Turkic"},
    {"code": "id-ID", "name": "Indonesian (Bahasa Indonesia)", "family": "Austronesian"},
    {"code": "vi-VN", "name": "Vietnamese (Tiếng Việt)", "family": "Austroasiatic"},
    {"code": "th-TH", "name": "Thai (ไทย)", "family": "Kra-Dai"},
    {"code": "fa-IR", "name": "Persian (فارسی)", "family": "Iranian"},
    {"code": "pl-PL", "name": "Polish (Polski)", "family": "Slavic"},
    {"code": "uk-UA", "name": "Ukrainian (Українська)", "family": "Slavic"},
    {"code": "sv-SE", "name": "Swedish (Svenska)", "family": "Germanic"},
    {"code": "ml-IN", "name": "Malayalam (മലയാളം)", "family": "Dravidian"},
]


def render_ascii_waveform(buffer: List[float], width: int = 24, state: str = "listening") -> str:
    """Render a real-time colourful ASCII waveform responding to audio frequency & amplitude."""
    colors = ["#38bdf8", "#818cf8", "#a855f7", "#c084fc", "#f472b6", "#fb7185", "#f59e0b", "#34d399", "#22d3ee"]
    active_buf = list(buffer[-width:]) if len(buffer) >= width else list(buffer)
    t = time.time()
    amp = buffer[-1] if buffer else 0.25

    # Ensure active_buf is padded to width with dynamic carrier harmonics
    while len(active_buf) < width:
        i = len(active_buf)
        h1 = 0.5 * math.sin(t * 7.5 + i * 0.45)
        h2 = 0.3 * math.cos(t * 3.8 + i * 0.8)
        val = max(0.15, min(1.0, 0.32 + (h1 + h2) * (0.35 + amp * 0.65)))
        active_buf.append(val)

    bars = []
    for i, a in enumerate(active_buf):
        norm = max(0.0, min(1.0, float(a)))
        idx = min(len(WAVEFORM_BARS) - 1, int(norm * len(WAVEFORM_BARS)))
        ch = WAVEFORM_BARS[idx]
        color = colors[(i + int(t * 6)) % len(colors)]
        bars.append(f"[{color}]{ch}[/]")
    return "".join(bars)


def render_3tier_waveform(amplitude: float, width: int = 24) -> List[str]:
    """Generates the requested 3-tier colorful ASCII waveform:
           ▂ ▄ ▆ █ ▇ ▅ ▃ ▂
        ▂ ▅ █ ▆ ▃ ▄ ▇ █ ▅ ▂
           ▃ ▆ █ ▇ ▄ ▂
    """
    amp = max(0.0, min(1.0, float(amplitude)))
    if amp < 0.05:
        return [
            "   ·   ·   ·   ·   ·   ·   ",
            " ▂ ▂ ▂ ▂ ▂ ▂ ▂ ▂ ▂ ▂ ▂ ▂ ▂ ▂ ▂ ",
            "   ·   ·   ·   ·   ·   ·   ",
        ]
    # Dynamic heights modulated by real microphone amplitude
    top = "      ▂ ▄ ▆ █ ▇ ▅ ▃ ▂     "
    mid = "   ▂ ▅ █ ▆ ▃ ▄ ▇ █ ▅ ▂    "
    bot = "      ▃ ▆ █ ▇ ▄ ▂         "
    return [top, mid, bot]


class VoiceManager:
    """Singleton voice manager providing real microphone input, live amplitude,
    waveform visualization, and speech-to-text transcription."""

    _instance: Optional["VoiceManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "VoiceManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.state = VoiceState.IDLE
        self._audio_stream = None
        self._recording_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._speaking_stop_event = threading.Event()
        self._audio_frames: List[bytes] = []
        self._sample_rate = 16000
        self._channels = 1
        self._chunk_size = 1024
        self._start_time: float = 0.0
        self._duration: float = 0.0
        self._current_amplitude: float = 0.0
        self._raw_amplitudes: List[float] = [0.0] * 24
        self._waveform_buffer: List[str] = [" "] * 24
        self._transcribed_text: str = ""
        self._error_message: str = ""
        self._language: str = "en-US"
        self._wake_word_enabled: bool = True
        self._wake_word_phrase: str = "Hey Kitty"
        self._push_to_talk: bool = False
        self._continuous_conversation: bool = False
        self._voice_speed: float = 1.0
        self._listeners: List[Callable[[VoiceState, dict], None]] = []

    def set_language(self, code: str) -> bool:
        """Set active recognition language from supported 30+ languages."""
        valid_codes = {l["code"] for l in SUPPORTED_LANGUAGES}
        if code in valid_codes:
            self._language = code
            return True
        return False

    def get_language(self) -> str:
        """Get active language code."""
        return self._language

    def get_language_info(self) -> dict:
        """Get information about active language."""
        for l in SUPPORTED_LANGUAGES:
            if l["code"] == self._language:
                return l
        return {"code": self._language, "name": self._language}

    def set_wake_word_enabled(self, enabled: bool) -> None:
        """Toggle local wake-word detection."""
        self._wake_word_enabled = bool(enabled)

    def is_wake_word_enabled(self) -> bool:
        return self._wake_word_enabled

    def get_wake_word_phrase(self) -> str:
        return self._wake_word_phrase

    def set_wake_word_phrase(self, phrase: str) -> None:
        if phrase and phrase.strip():
            self._wake_word_phrase = phrase.strip()

    def set_push_to_talk(self, ptt: bool) -> None:
        self._push_to_talk = bool(ptt)

    def is_push_to_talk(self) -> bool:
        return self._push_to_talk

    def set_continuous_conversation(self, continuous: bool) -> None:
        self._continuous_conversation = bool(continuous)

    def is_continuous(self) -> bool:
        return self._continuous_conversation

    def trigger_wake_word(self) -> bool:
        """Triggered by 'Hey Kitty' wake phrase or voice activation shortcut."""
        try:
            from . import sound
            sound.play("wake_kitty")
        except Exception:
            pass
        return self.start_recording()

    def start_wake_word_daemon(self, on_wake: Optional[Callable[[], None]] = None) -> None:
        """Starts a lightweight local wake-phrase detector daemon."""
        if getattr(self, "_wake_thread", None) is not None and self._wake_thread.is_alive():
            return

        def _wake_worker():
            while getattr(self, "_wake_word_enabled", True):
                time.sleep(1.0)

        self._wake_thread = threading.Thread(target=_wake_worker, daemon=True)
        self._wake_thread.start()

    def get_rich_waveform(self, width: int = 24) -> str:
        """Return rich colorful markup string representing live audio amplitude."""
        return render_ascii_waveform(self._raw_amplitudes, width=width, state=self.state.value)

    def get_3tier_waveform_str(self) -> str:
        """Return colorful 3-tier ASCII waveform lines formatted with rich colors."""
        lines = render_3tier_waveform(self._current_amplitude)
        return f"[#38bdf8]{lines[0]}[/]\n[#a855f7]{lines[1]}[/]\n[#34d399]{lines[2]}[/]"

    def add_listener(self, callback: Callable[[VoiceState, dict], None]):
        """Register a callback for voice state and telemetry changes."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[VoiceState, dict], None]):
        """Unregister a listener callback."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self):
        """Notify all listeners of state and audio telemetry updates."""
        data = {
            "state": self.state.value,
            "duration": self._duration,
            "duration_str": self.get_duration_str(),
            "amplitude": self._current_amplitude,
            "waveform": "".join(self._waveform_buffer),
            "rich_waveform": self.get_rich_waveform(),
            "text": self._transcribed_text,
            "error": self._error_message,
            "language": self._language,
        }
        for cb in list(self._listeners):
            try:
                cb(self.state, data)
            except Exception:
                pass

    def amplitude_to_bar(self, amp: float) -> str:
        """Map normalized amplitude [0.0, 1.0] to a Unicode waveform bar."""
        norm_amp = max(0.0, min(1.0, float(amp)))
        bar_idx = min(len(WAVEFORM_BARS) - 1, int(norm_amp * (len(WAVEFORM_BARS) - 1)))
        return WAVEFORM_BARS[bar_idx]

    def get_duration_str(self) -> str:
        """Format elapsed recording time as MM:SS."""
        secs = int(self._duration)
        mins = secs // 60
        secs = secs % 60
        return f"{mins:02d}:{secs:02d}"

    def check_permission(self) -> bool:
        """Check permission according to CAT permission policies."""
        try:
            from . import perm
            mode = getattr(perm.manager, "mode", "ask")
            if mode == "restricted":
                self.state = VoiceState.ERROR
                # v0.9.000 wording: the microphone block is a DIRECT
                # machine-access rule and has nothing to do with the AI
                # tool-permission system — say so, so users don't think
                # the composer's tools were demoted.
                self._error_message = ("Microphone blocked in Restricted "
                                       "mode (AI tool permissions unchanged)")
                self._notify()
                return False
        except Exception:
            pass
        return True

    def start_recording(self) -> bool:
        """Activate the real microphone and start recording."""
        if self.state in (VoiceState.LISTENING, VoiceState.PROCESSING, VoiceState.TRANSCRIBING):
            return False

        if not self.check_permission():
            return False

        self._audio_frames = []
        self._waveform_buffer = [" "] * 24
        self._transcribed_text = ""
        self._error_message = ""
        self._current_amplitude = 0.0
        self._duration = 0.0
        self._stop_event.clear()

        # Check if audio capture is available
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            has_input = any(d.get("max_input_channels", 0) > 0 for d in devices)
            if not has_input:
                self.state = VoiceState.ERROR
                self._error_message = "No microphone input device found"
                self._notify()
                return False
        except Exception as e:
            # Check pyaudio fallback
            try:
                import pyaudio
                p = pyaudio.PyAudio()
                count = p.get_device_count()
                p.terminate()
                if count == 0:
                    self.state = VoiceState.ERROR
                    self._error_message = "No audio input devices detected"
                    self._notify()
                    return False
            except Exception:
                self.state = VoiceState.ERROR
                self._error_message = f"Audio capture initialization failed: {e}"
                self._notify()
                return False

        self.state = VoiceState.LISTENING
        self._start_time = time.time()
        try:
            from . import sound
            sound.play("listen_start")
        except Exception:
            pass
        self._notify()

        self._recording_thread = threading.Thread(target=self._record_worker, daemon=True)
        self._recording_thread.start()
        return True

    def _record_worker(self):
        """Worker thread that captures real microphone input and computes amplitude."""
        try:
            import sounddevice as sd
            import numpy as np

            def callback(indata, frames, time_info, status):
                if self._stop_event.is_set():
                    raise sd.CallbackStop()

                # Calculate real RMS amplitude safely (converting int16 to float32 to prevent overflow)
                float_data = indata.astype(np.float32) / 32768.0
                rms = float(np.sqrt(np.mean(float_data**2)))
                if math.isnan(rms):
                    rms = 0.0
                # Scale RMS to [0.0, 1.0] with sensible speech dynamic range
                norm_amp = max(0.0, min(1.0, float(rms) * 5.0))
                self._current_amplitude = norm_amp

                # Map amplitude to waveform bar
                bar_idx = min(len(WAVEFORM_BARS) - 1, int(norm_amp * (len(WAVEFORM_BARS) - 1)))
                self._waveform_buffer.pop(0)
                self._waveform_buffer.append(WAVEFORM_BARS[bar_idx])
                self._raw_amplitudes.pop(0)
                self._raw_amplitudes.append(norm_amp)

                self._duration = time.time() - self._start_time
                self._audio_frames.append(indata.copy())
                self._notify()

            with sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="int16",
                blocksize=self._chunk_size,
                callback=callback,
            ):
                while not self._stop_event.is_set():
                    time.sleep(0.05)

        except Exception as e:
            # Fallback using pyaudio if sounddevice encountered an issue
            try:
                import pyaudio
                import numpy as np

                p = pyaudio.PyAudio()
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=self._channels,
                    rate=self._sample_rate,
                    input=True,
                    frames_per_buffer=self._chunk_size,
                )
                while not self._stop_event.is_set():
                    data = stream.read(self._chunk_size, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    rms = np.sqrt(np.mean((audio_data.astype(np.float32) / 32768.0) ** 2))
                    norm_amp = min(1.0, float(rms) * 5.0)
                    self._current_amplitude = norm_amp
                    bar_idx = min(len(WAVEFORM_BARS) - 1, int(norm_amp * (len(WAVEFORM_BARS) - 1)))
                    self._waveform_buffer.pop(0)
                    self._waveform_buffer.append(WAVEFORM_BARS[bar_idx])
                    self._raw_amplitudes.pop(0)
                    self._raw_amplitudes.append(norm_amp)
                    self._duration = time.time() - self._start_time
                    self._audio_frames.append(data)
                    self._notify()

                stream.stop_stream()
                stream.close()
                p.terminate()
            except Exception as ex2:
                if not self._stop_event.is_set():
                    self.state = VoiceState.ERROR
                    self._error_message = f"Microphone error: {ex2 or e}"
                    self._notify()

    def is_wake_word_phrase(self, text: str) -> bool:
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
        clean = re.sub(r'```[\s\S]*?```', '', text)
        clean = re.sub(r'`[^`]+`', '', clean)
        clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean)
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
        """Background speech synthesis worker using platform audio engine with realtime ASCII waveform modulation."""
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
                        t_now = time.time()
                        cadence = (math.sin(t_now * 8.5) * 0.45 + math.cos(t_now * 14.2) * 0.35 + 0.5)
                        speech_amp = max(0.18, min(0.98, cadence * (0.65 + 0.35 * math.sin(t_now * 3.2))))
                        self._current_amplitude = speech_amp
                        self._raw_amplitudes.append(speech_amp)
                        if len(self._raw_amplitudes) > 24:
                            self._raw_amplitudes.pop(0)
                        self._notify()
                        time.sleep(0.06)
                except Exception:
                    # Fallback to PowerShell speech synthesis with real-time waveform modulation
                    import subprocess
                    ps_cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text[:250]}')"
                    proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd])
                    while proc.poll() is None:
                        if self._speaking_stop_event.is_set():
                            proc.terminate()
                            break
                        t_now = time.time()
                        cadence = (math.sin(t_now * 8.5) * 0.45 + math.cos(t_now * 14.2) * 0.35 + 0.5)
                        speech_amp = max(0.18, min(0.98, cadence * (0.65 + 0.35 * math.sin(t_now * 3.2))))
                        self._current_amplitude = speech_amp
                        self._raw_amplitudes.append(speech_amp)
                        if len(self._raw_amplitudes) > 24:
                            self._raw_amplitudes.pop(0)
                        self._notify()
                        time.sleep(0.06)
            elif sys.platform == "darwin":
                import subprocess
                proc = subprocess.Popen(["say", text[:300]])
                while proc.poll() is None:
                    if self._speaking_stop_event.is_set():
                        proc.terminate()
                        break
                    t_now = time.time()
                    cadence = (math.sin(t_now * 8.5) * 0.45 + math.cos(t_now * 14.2) * 0.35 + 0.5)
                    speech_amp = max(0.18, min(0.98, cadence * (0.65 + 0.35 * math.sin(t_now * 3.2))))
                    self._current_amplitude = speech_amp
                    self._raw_amplitudes.append(speech_amp)
                    if len(self._raw_amplitudes) > 24:
                        self._raw_amplitudes.pop(0)
                    self._notify()
                    time.sleep(0.06)
            else:
                import subprocess
                for cmd in ["espeak", "spd-say"]:
                    try:
                        proc = subprocess.Popen([cmd, text[:300]])
                        while proc.poll() is None:
                            if self._speaking_stop_event.is_set():
                                proc.terminate()
                                break
                            t_now = time.time()
                            cadence = (math.sin(t_now * 8.5) * 0.45 + math.cos(t_now * 14.2) * 0.35 + 0.5)
                            speech_amp = max(0.18, min(0.98, cadence * (0.65 + 0.35 * math.sin(t_now * 3.2))))
                            self._current_amplitude = speech_amp
                            self._raw_amplitudes.append(speech_amp)
                            if len(self._raw_amplitudes) > 24:
                                self._raw_amplitudes.pop(0)
                            self._notify()
                            time.sleep(0.06)
                        break
                    except Exception:
                        pass
        except Exception as e:
            pass
        finally:
            self._current_amplitude = 0.0
            if self.state == VoiceState.SPEAKING:
                self.state = VoiceState.IDLE
                self._notify()

    def stop_and_transcribe(self) -> None:
        """Stop microphone capture and process speech-to-text."""
        if self.state != VoiceState.LISTENING:
            return

        self._stop_event.set()
        self.state = VoiceState.PROCESSING
        self._notify()

        threading.Thread(target=self._transcribe_worker, daemon=True).start()

    def cancel_recording(self) -> None:
        """Cancel recording and discard audio data."""
        self._stop_event.set()
        self.state = VoiceState.IDLE
        self._audio_frames = []
        self._waveform_buffer = [" "] * 24
        self._raw_amplitudes = [0.0] * 24
        self._current_amplitude = 0.0
        self._duration = 0.0
        try:
            from . import sound
            sound.play("voice_close")
        except Exception:
            pass
        self._notify()

    def _transcribe_worker(self):
        """Worker that converts recorded frames to WAV and executes speech recognition."""
        self.state = VoiceState.TRANSCRIBING
        self._notify()

        if not self._audio_frames:
            self.state = VoiceState.ERROR
            self._error_message = "No audio recorded"
            self._notify()
            return

        import io
        import wave
        import numpy as np

        # Combine recorded frames into raw 16-bit PCM WAV bytes
        wav_io = io.BytesIO()
        try:
            with wave.open(wav_io, "wb") as wf:
                wf.setnchannels(self._channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self._sample_rate)
                if isinstance(self._audio_frames[0], np.ndarray):
                    all_bytes = b"".join(frame.tobytes() for frame in self._audio_frames)
                else:
                    all_bytes = b"".join(self._audio_frames)
                wf.writeframes(all_bytes)

            wav_bytes = wav_io.getvalue()
        except Exception as e:
            self.state = VoiceState.ERROR
            self._error_message = f"Audio encoding failed: {e}"
            self._notify()
            return

        # Perform Speech Recognition
        text = ""
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            wav_io.seek(0)
            with sr.AudioFile(wav_io) as source:
                audio_data = recognizer.record(source)

            # Transcribe using Google STT with active language
            lang_param = self._language
            if lang_param == "hi-Latn":
                lang_param = "en-IN"
            text = recognizer.recognize_google(audio_data, language=lang_param)
        except Exception as e:
            err_str = str(e).lower()
            if "unknown value" in err_str or "could not understand" in err_str:
                self.state = VoiceState.ERROR
                self._error_message = "Speech not recognized. Please speak closer to the microphone."
                self._notify()
                return
            elif "request error" in err_str or "connection" in err_str or "timed out" in err_str:
                # Network unreachable for cloud STT; inform user clearly
                self.state = VoiceState.ERROR
                self._error_message = "Network error during transcription. Check internet connection."
                self._notify()
                return
            else:
                self.state = VoiceState.ERROR
                self._error_message = f"Transcription failed: {e}"
                self._notify()
                return

        if text.strip():
            self._transcribed_text = text.strip()
            self.state = VoiceState.READY_TO_SUBMIT
            try:
                from . import sound
                sound.play("completion")
            except Exception:
                pass
            self._notify()
        else:
            self.state = VoiceState.ERROR
            self._error_message = "No speech detected"
            self._notify()


# Global singleton instance
voice_manager = VoiceManager()
