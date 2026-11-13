with open("calc_terminal/voice.py", "r", encoding="utf-8") as f:
    vcode = f.read()

helper = '''    def amplitude_to_bar(self, amp: float) -> str:
        """Map normalized amplitude [0.0, 1.0] to a Unicode waveform bar."""
        norm_amp = max(0.0, min(1.0, float(amp)))
        bar_idx = min(len(WAVEFORM_BARS) - 1, int(norm_amp * (len(WAVEFORM_BARS) - 1)))
        return WAVEFORM_BARS[bar_idx]

    def get_duration_str(self) -> str:'''

vcode = vcode.replace("    def get_duration_str(self) -> str:", helper)
with open("calc_terminal/voice.py", "w", encoding="utf-8") as f:
    f.write(vcode)

with open("calc_terminal/tests/test_v090_voice_and_composer_layout.py", "r", encoding="utf-8") as f:
    tcode = f.read()

tcode = tcode.replace("vm._amplitude_to_bar", "vm.amplitude_to_bar")
with open("calc_terminal/tests/test_v090_voice_and_composer_layout.py", "w", encoding="utf-8") as f:
    f.write(tcode)

print("Updated voice.py and test")

