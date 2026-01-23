#!/usr/bin/env python3
"""
Test script for the TTS job queue system.
Submits a test job and monitors its progress.
"""

import requests
import time
import sys
import json

BASE_URL = "http://localhost:8004"

def test_job_queue():
    """Test the complete job queue workflow"""
    
    print("=" * 60)
    print("Testing TTS Job Queue System")
    print("=" * 60)
    
    # 1. Submit a job
    print("\n1. Submitting TTS job...")
    payload = {
        "text": "This is a test of the job queue system.",
        "voice_mode": "predefined",
        "predefined_voice_id": "voice.wav",  # Adjust based on your setup
        "temperature": 0.7,
        "exaggeration": 0.5,
        "cfg_weight": 3.0,
        "speed_factor": 1.0,
        "language": "en",
        "output_format": "wav",
        "seed": 42,
        "split_text": False
    }
    
    try:
        response = requests.post(f"{BASE_URL}/tts/enqueue", json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        job_id = result.get("job_id")
        print(f"✓ Job submitted successfully!")
        print(f"  Job ID: {job_id}")
        print(f"  Status: {result.get('status')}")
        print(f"  Status URL: {result.get('status_url')}")
        print(f"  Result URL: {result.get('result_url')}")
        
    except requests.exceptions.ConnectionError:
        print("✗ Error: Could not connect to server.")
        print("  Make sure the server is running on http://localhost:8004")
        return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Error submitting job: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text}")
        return False
    
    # 2. Poll job status
    print("\n2. Polling job status...")
    start_time = time.time()
    poll_count = 0
    last_progress = -1
    
    while True:
        poll_count += 1
        elapsed = time.time() - start_time
        
        try:
            response = requests.get(f"{BASE_URL}/tts/{job_id}/status", timeout=5)
            response.raise_for_status()
            status = response.json()
            
            job_status = status.get("status")
            progress = status.get("progress", 0)
            current_chunk = status.get("current_chunk", 0)
            total_chunks = status.get("total_chunks", 0)
            
            # Only print if progress changed
            if progress != last_progress:
                chunk_info = f" [{current_chunk}/{total_chunks} chunks]" if total_chunks > 0 else ""
                print(f"  Poll #{poll_count} ({elapsed:.1f}s): {job_status} - {progress}%{chunk_info}")
                last_progress = progress
            
            # Check terminal states
            if job_status == "completed":
                print(f"\n✓ Job completed successfully in {elapsed:.2f} seconds!")
                break
            elif job_status == "failed":
                error = status.get("error", "Unknown error")
                print(f"\n✗ Job failed: {error}")
                return False
            elif job_status == "cancelled":
                print("\n✗ Job was cancelled")
                return False
            
            # Wait before next poll (with exponential backoff)
            wait_time = min(1.0 * (1.5 ** (poll_count - 1)), 5.0)
            time.sleep(wait_time)
            
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
            print("Attempting to cancel job...")
            try:
                requests.delete(f"{BASE_URL}/tts/{job_id}", timeout=5)
                print("✓ Job cancelled")
            except:
                print("✗ Failed to cancel job")
            return False
        except requests.exceptions.RequestException as e:
            print(f"\n✗ Error checking status: {e}")
            return False
    
    # 3. Download result
    print("\n3. Downloading result...")
    try:
        response = requests.get(f"{BASE_URL}/tts/{job_id}/result", timeout=30)
        response.raise_for_status()
        
        # Get filename from Content-Disposition header
        content_disp = response.headers.get('Content-Disposition', '')
        filename = 'test_result.wav'
        if 'filename=' in content_disp:
            filename = content_disp.split('filename=')[1].replace('"', '')
        
        # Save the audio file
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        file_size = len(response.content)
        print(f"✓ Result downloaded successfully!")
        print(f"  File: {filename}")
        print(f"  Size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error downloading result: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    return True


def test_job_status_endpoints():
    """Test status endpoint edge cases"""
    print("\n" + "=" * 60)
    print("Testing Edge Cases")
    print("=" * 60)
    
    # Test with invalid job ID
    print("\n1. Testing invalid job ID...")
    try:
        response = requests.get(f"{BASE_URL}/tts/invalid-job-id/status", timeout=5)
        if response.status_code == 404:
            print("✓ Correctly returns 404 for invalid job ID")
        else:
            print(f"✗ Unexpected status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    print("\nChatterbox TTS Job Queue Test")
    print("Make sure the server is running with: python server.py\n")
    
    # Run main test
    success = test_job_queue()
    
    # Run edge case tests
    if success:
        test_job_status_endpoints()
    
    sys.exit(0 if success else 1)
