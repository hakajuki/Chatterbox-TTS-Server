#!/usr/bin/env python3
"""
Generate a simple beep sound for audio censorship.
Creates a 1kHz sine wave beep lasting 200ms.
"""
import numpy as np
from pydub import AudioSegment
from pathlib import Path

def generate_beep(frequency=1000, duration_ms=200, sample_rate=44100):
    """Generate a simple sine wave beep."""
    t = np.linspace(0, duration_ms / 1000, int(sample_rate * duration_ms / 1000))
    wave = np.sin(2 * np.pi * frequency * t)
    
    # Apply fade in/out to avoid clicks
    fade_samples = int(sample_rate * 0.01)  # 10ms fade
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    wave[:fade_samples] *= fade_in
    wave[-fade_samples:] *= fade_out
    
    # Convert to 16-bit PCM
    wave = (wave * 32767).astype(np.int16)
    
    # Create AudioSegment
    beep = AudioSegment(
        wave.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=1
    )
    
    return beep

if __name__ == "__main__":
    output_path = Path(__file__).parent / "beep.wav"
    
    beep = generate_beep()
    beep.export(str(output_path), format="wav")
    
    print(f"✓ Generated beep sound: {output_path}")
    print(f"  Duration: {len(beep)}ms")
    print(f"  Sample rate: {beep.frame_rate}Hz")
