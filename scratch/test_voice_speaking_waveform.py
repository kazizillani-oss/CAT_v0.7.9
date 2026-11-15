import time
import sys
sys.path.insert(0, ".")
from calc_terminal.voice import voice_manager, VoiceState

print("Initial voice state:", voice_manager.state)
waveform_samples = []

def on_voice_update(state, data):
    if state == VoiceState.SPEAKING:
        waveform_samples.append(data.get("rich_waveform", ""))

voice_manager.add_listener(on_voice_update)
print("Speaking test message...")
voice_manager.speak_text("Hello from CAT CLI agent voice mode.")

# Wait for speaking to commence and collect samples
time.sleep(1.0)
print(f"Collected {len(waveform_samples)} speech waveform frames during speaking!")
if waveform_samples:
    print("Sample waveform frame:", waveform_samples[-1][:60])

assert len(waveform_samples) > 0, "No speech waveforms emitted during speaking!"
print("Voice speaking waveform test PASSED!")
