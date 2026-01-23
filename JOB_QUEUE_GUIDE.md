# TTS Job Queue System - Implementation Guide

## Overview

The Chatterbox TTS Server now supports asynchronous job processing with a queue system. This allows:

- **Non-blocking requests**: Submit TTS generation and get immediate job ID
- **Progress tracking**: Monitor job status and completion percentage
- **Browser refresh resilience**: Job IDs stored in localStorage survive page reloads
- **Concurrent processing**: Queue handles multiple requests sequentially with status tracking

## API Endpoints

### 1. Enqueue Job
```
POST /tts/enqueue
Content-Type: application/json

{
  "text": "Hello world",
  "voice_mode": "predefined",
  "predefined_voice_id": "voice.wav",
  ...
}

Response (202 Accepted):
{
  "job_id": "uuid-string",
  "status": "queued",
  "message": "Job queued for processing",
  "status_url": "/tts/{job_id}/status",
  "result_url": "/tts/{job_id}/result"
}
```

### 2. Check Job Status
```
GET /tts/{job_id}/status

Response (200 OK):
{
  "job_id": "uuid",
  "status": "running",  // queued | running | completed | failed | cancelled
  "progress": 45,        // 0-100
  "created_at": 1234567890.0,
  "started_at": 1234567891.0,
  "elapsed_sec": 5.2,
  "current_chunk": 3,
  "total_chunks": 7
}
```

### 3. Get Result
```
GET /tts/{job_id}/result

Response (200 OK):
Content-Type: audio/wav
Content-Disposition: attachment; filename="tts_job_uuid_timestamp.wav"

<audio binary data>

Error responses:
- 404: Job not found
- 425: Job still queued/running (Too Early)
- 410: Job was cancelled (Gone)
- 500: Job failed with error
```

### 4. Cancel Job
```
DELETE /tts/{job_id}

Response (200 OK):
{
  "message": "Job uuid cancelled successfully"
}
```

## UI Implementation

### LocalStorage Keys
- `tts_current_job_id`: Current/most recent job ID
- `tts_job_params`: Parameters of current job (for display)

### Client Flow

1. **Submit Generation**
   ```javascript
   const response = await fetch('/tts/enqueue', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify(ttsParams)
   });
   const { job_id } = await response.json();
   localStorage.setItem('tts_current_job_id', job_id);
   ```

2. **Poll Status**
   ```javascript
   async function pollJobStatus(jobId) {
     const response = await fetch(`/tts/${jobId}/status`);
     const status = await response.json();
     
     if (status.status === 'completed') {
       // Fetch result
       window.location.href = `/tts/${jobId}/result`;
       localStorage.removeItem('tts_current_job_id');
     } else if (status.status === 'failed') {
       showError(status.error);
       localStorage.removeItem('tts_current_job_id');
     } else {
       // Update progress UI
       updateProgress(status.progress);
       // Poll again with exponential backoff
       setTimeout(() => pollJobStatus(jobId), 1000);
     }
   }
   ```

3. **Resume After Refresh**
   ```javascript
   window.addEventListener('load', () => {
     const savedJobId = localStorage.getItem('tts_current_job_id');
     if (savedJobId) {
       // Resume polling
       pollJobStatus(savedJobId);
     }
   });
   ```

## Server Implementation Details

### Job Queue Module (`job_queue.py`)

- **TTSJob**: Dataclass tracking job state, progress, timestamps, output
- **JobStatus**: Enum (QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED)
- **TTSJobQueue**: Queue manager with background worker and cleanup

### Key Features

1. **Background Worker**: `asyncio` task processes jobs sequentially
2. **Progress Tracking**: Updates job progress during multi-chunk generation
3. **Auto-cleanup**: Removes jobs older than TTL (default 24h)
4. **Cancellation**: Jobs can be cancelled if queued or running

### Integration Points

In `server.py`:
- Import: `from job_queue import get_job_queue, JobStatus, TTSJob`
- Lifespan: Start/stop queue workers
- Process function: `process_tts_job(job)` - core TTS logic
- Endpoints: `/tts/enqueue`, `/tts/{id}/status`, `/tts/{id}/result`

## Configuration

Add to `config.yaml`:
```yaml
job_queue:
  max_retries: 0
  job_ttl_hours: 24
  cleanup_interval_sec: 3600
```

## Backward Compatibility

The original `/tts` endpoint remains unchanged for synchronous requests.
Clients can choose:
- `/tts` - Synchronous (waits for completion)
- `/tts/enqueue` - Asynchronous (immediate response, poll for result)

## Testing

### Manual Test
```bash
# 1. Submit job
curl -X POST http://localhost:8004/tts/enqueue \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","voice_mode":"predefined","predefined_voice_id":"voice.wav"}'

# Response: {"job_id": "abc-123", ...}

# 2. Check status
curl http://localhost:8004/tts/abc-123/status

# 3. Get result (when completed)
curl http://localhost:8004/tts/abc-123/result -o output.wav
```

### Python Test
```python
import requests
import time

# Submit
response = requests.post('http://localhost:8004/tts/enqueue', json={
    'text': 'Test generation',
    'voice_mode': 'predefined',
    'predefined_voice_id': 'voice.wav'
})
job_id = response.json()['job_id']
print(f"Job ID: {job_id}")

# Poll
while True:
    status = requests.get(f'http://localhost:8004/tts/{job_id}/status').json()
    print(f"Status: {status['status']}, Progress: {status.get('progress', 0)}%")
    
    if status['status'] == 'completed':
        # Download result
        audio = requests.get(f'http://localhost:8004/tts/{job_id}/result')
        with open('result.wav', 'wb') as f:
            f.write(audio.content)
        break
    elif status['status'] == 'failed':
        print(f"Error: {status['error']}")
        break
    
    time.sleep(1)
```

## Future Enhancements

1. **Redis backend**: Persist jobs across server restarts
2. **WebSocket updates**: Real-time progress instead of polling
3. **Job priority**: High/normal/low priority queue
4. **Rate limiting**: Per-user job quotas
5. **Job history**: List recent jobs for a user
6. **Batch jobs**: Submit multiple texts as one job

## Troubleshooting

### Job Stuck in "queued"
- Check server logs for worker errors
- Verify TTS model is loaded (`/api/model-info`)
- Restart server to reset queue

### Jobs Disappearing
- Check job TTL setting (default 24h cleanup)
- Verify output directory is writable
- Check disk space

### High Memory Usage
- Adjust TTL to cleanup sooner
- Limit concurrent jobs (currently sequential)
- Monitor output directory size
