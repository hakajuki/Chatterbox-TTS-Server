#!/usr/bin/env python3
"""
Test script for Beep Sync Server.
Creates a test audio file with speech and sends it for censorship.
"""
import requests
import tempfile
from pathlib import Path
from pydub import AudioSegment
from pydub.generators import Sine

def create_test_audio():
    """Create a simple test audio with multiple tones representing 'bad words'."""
    # Create silent base
    audio = AudioSegment.silent(duration=5000, frame_rate=22050)
    
    # Add some tones (simulating speech segments)
    tone1 = Sine(440).to_audio_segment(duration=500)  # A4 note
    tone2 = Sine(523).to_audio_segment(duration=500)  # C5 note
    tone3 = Sine(659).to_audio_segment(duration=500)  # E5 note
    
    # Place tones at different positions
    audio = audio.overlay(tone1, position=500)
    audio = audio.overlay(tone2, position=1500)
    audio = audio.overlay(tone3, position=3000)
    
    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio.export(temp_file.name, format="wav")
    return Path(temp_file.name)

def test_censor_api(server_url="http://localhost:8005"):
    """Test the /api/censor endpoint."""
    print("🧪 Testing Beep Sync Server...")
    
    # Test 1: Health check
    print("\n1️⃣  Testing health endpoint...")
    try:
        response = requests.get(f"{server_url}/api/health")
        if response.ok:
            health = response.json()
            print(f"   ✓ Server is healthy")
            print(f"     Device: {health.get('device')}")
            print(f"     Model: {health.get('model')}")
            print(f"     Compute type: {health.get('compute_type')}")
        else:
            print(f"   ✗ Health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"   ✗ Cannot connect to server: {e}")
        print(f"     Make sure server is running on {server_url}")
        return
    
    # Test 2: Create test audio
    print("\n2️⃣  Creating test audio file...")
    test_audio_path = create_test_audio()
    print(f"   ✓ Test audio created: {test_audio_path}")
    print(f"     Duration: {AudioSegment.from_file(test_audio_path).duration_seconds:.1f}s")
    
    # Test 3: Submit for censorship
    print("\n3️⃣  Submitting audio for censorship...")
    with open(test_audio_path, "rb") as f:
        files = {"audio_file": f}
        data = {"bad_words": "test,example,sample"}  # Won't match tone audio, but tests API
        
        response = requests.post(f"{server_url}/api/censor", files=files, data=data)
    
    if response.ok:
        print("   ✓ Censorship completed")
        print(f"     Detected count: {response.headers.get('X-Detected-Count', '0')}")
        print(f"     Groups censored: {response.headers.get('X-Groups-Censored', '0')}")
        
        # Save result
        output_path = test_audio_path.parent / "censored_test.wav"
        with open(output_path, "wb") as out:
            out.write(response.content)
        print(f"     Output saved: {output_path}")
        
        # Verify output
        result_audio = AudioSegment.from_file(output_path)
        print(f"     Output duration: {result_audio.duration_seconds:.1f}s")
    else:
        print(f"   ✗ Censorship failed: {response.status_code}")
        print(f"     Error: {response.text}")
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    test_audio_path.unlink()
    if (test_audio_path.parent / "censored_test.wav").exists():
        (test_audio_path.parent / "censored_test.wav").unlink()
    print("   ✓ Test files removed")
    
    print("\n✅ Test complete!")

if __name__ == "__main__":
    import sys
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8005"
    test_censor_api(server_url)
