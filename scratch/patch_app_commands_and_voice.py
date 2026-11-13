# Patch calc_terminal/app.py for command cleanup and real voice mode
import re

with open("calc_terminal/app.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. In _bind_registry_commands
bindings_remove = [
    '            "/kinetics": self.cmd_kinetics,\n',
    '            "/electrochemistry": self.cmd_electrochemistry,\n',
    '            "/atomsim": self.cmd_atomsim,\n',
    '            "/orbitals": self.cmd_orbitals,\n',
    '            "/orbitalgrid": self.cmd_orbitalgrid,\n',
    '            "/graph": self.cmd_graph,\n',
    '            "/sim3d": self.cmd_sim3d,\n',
    '            "/gpu3d": self.cmd_gpu3d,\n',
    '            "/game": self.cmd_game,\n',
]
for b in bindings_remove:
    text = text.replace(b, "")

# 2. In handle() remove dispatches
dispatch_blocks = [
    '''        if low == "/kinetics":
            self.cmd_kinetics()
            return\n''',
    '''        if low == "/electrochemistry":
            self.cmd_electrochemistry()
            return\n''',
    '''        if low == "/atomsim":
            self.cmd_atomsim()
            return\n''',
    '''        if low == "/orbitals":
            self.cmd_orbitals()
            return\n''',
    '''        if low == "/orbitalgrid":
            self.cmd_orbitalgrid()
            return\n''',
    '''        if low == "/bonding" or low.startswith("/bonding "):
            arg = raw.split(" ", 1)[1] if " " in raw else ""
            self.cmd_bonding(arg)
            return\n''',
    '''        if low == "/graph":
            self.cmd_graph()
            return\n''',
    '''        if low == "/random":
            self.solve(random.choice(list(GENERATORS.keys())))
            return\n''',
    '''        if low == "/sim3d":
            self.cmd_sim3d()
            return\n''',
    '''        if low == "/gpu3d":
            self.cmd_gpu3d()
            return\n''',
    '''        if low in ("/game", "/quiz", "/play"):
            self.cmd_game()
            return\n''',
]

for block in dispatch_blocks:
    assert block in text, f"Failed to find dispatch block: {block[:30]}"
    text = text.replace(block, "")

# 3. Replace cmd_voice with real voice implementation
old_voice_impl = '''    # -------------------------------------------------------------- voice --
    def cmd_voice(self):
        sys.stdout.write("  " + theme.red("\\u25cf Listening"))
        sys.stdout.flush()
        for _ in range(3):
            time.sleep(0.35)
            sys.stdout.write(theme.red("."))
            sys.stdout.flush()
        print()
        run_steps(["Processing..."], step_time=0.3)
        recognized = "first order half life numerical"
        print(theme.dim("  Recognized: ") + theme.text(f"\\"{recognized}\\""))
        self.handle_question(recognized)'''

new_voice_impl = '''    # -------------------------------------------------------------- voice --
    def cmd_voice(self):
        """v0.9.000: Real voice mode with live microphone audio, amplitude waveform & STT."""
        from .voice import voice_manager, VoiceState
        if not voice_manager.check_permission():
            print(theme.red("  Microphone access denied in current security mode."))
            return

        print()
        print(theme.panel([
            theme.badge("VOICE MODE", theme.BG_CYAN) + " " + theme.text("Real-Time Microphone Input", bold=True),
            theme.dim("Live audio capture & speech-to-text transcription powered by CAT Voice."),
            theme.dim("Press Enter to stop and submit to active agent, or Ctrl+C / Esc to cancel."),
        ], title="voice", color=theme.CYAN, width=WIDTH))

        if not voice_manager.start_recording():
            print(theme.red(f"  Failed to start microphone: {voice_manager._error_message}"))
            return

        try:
            while voice_manager.state == VoiceState.LISTENING:
                dur = voice_manager.get_duration_str()
                wf = "".join(voice_manager._waveform_buffer[-16:])
                sys.stdout.write(f"\\r  {theme.red('\\u25cf REC')} [{dur}] {theme.cyan(wf)}  (Press Enter to Stop)  ")
                sys.stdout.flush()
                time.sleep(0.08)
                if sys.platform == "win32":
                    import msvcrt
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key in (b'\\r', b'\\n', b' '):
                            break
                        elif key in (b'\\x1b', b'\\x03'):
                            voice_manager.cancel_recording()
                            print("\\n" + theme.dim("  Voice recording cancelled."))
                            return
        except KeyboardInterrupt:
            voice_manager.cancel_recording()
            print("\\n" + theme.dim("  Voice recording cancelled."))
            return

        print("\\n  " + theme.cyan("Transcribing speech..."))
        voice_manager.stop_and_transcribe()
        while voice_manager.state in (VoiceState.PROCESSING, VoiceState.TRANSCRIBING):
            time.sleep(0.05)

        if voice_manager.state == VoiceState.READY_TO_SUBMIT:
            text_result = voice_manager._transcribed_text
            print(theme.green("  \\u2714 Recognized: ") + theme.text(f"\\"{text_result}\\"", bold=True))
            voice_manager.cancel_recording()
            self.handle_question(text_result)
        else:
            print(theme.red(f"  Voice transcription: {voice_manager._error_message or 'No speech recognized.'}"))
            voice_manager.cancel_recording()'''

assert old_voice_impl in text, "Failed to find old_voice_impl"
text = text.replace(old_voice_impl, new_voice_impl)

with open("calc_terminal/app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("calc_terminal/app.py successfully patched for command cleanup and real voice mode!")

