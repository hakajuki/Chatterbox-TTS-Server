# TTS Job Queue Implementation - Changes Summary

## Date: 2024
## Objective: Convert TTS generation from synchronous single-request to asynchronous queue-based system with localStorage persistence

---

## Files Created

### 1. `job_queue.py` (NEW - 330 lines)
Complete job queue system implementation.

**Key Components:**
- `JobStatus` enum: QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED
- `TTSJob` dataclass: Tracks job state, progress, metadata, timestamps
- `TTSJobQueue` class: Queue manager with background workers
  - `submit_job()`: Enqueue new jobs
  - `get_job()`: Retrieve job status
  - `cancel_job()`: Cancel pending/running jobs
  - `_worker()`: Background task processing jobs sequentially
  - `_cleanup_worker()`: Hourly cleanup of old jobs (24h TTL)

**Dependencies:**
```python
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Callable, Any
from enum import Enum
```

### 2. `JOB_QUEUE_GUIDE.md` (NEW - Documentation)
Comprehensive guide covering:
- API endpoint specifications
- Client implementation examples
- Server architecture details
- Configuration options
- Testing procedures
- Troubleshooting tips

### 3. `test_job_queue.py` (NEW - Test Script)
Automated testing script that:
- Submits test job via `/tts/enqueue`
- Polls status with exponential backoff
- Downloads result when complete
- Tests edge cases (invalid job IDs)
- Handles keyboard interrupts gracefully

**Usage:**
```bash
python test_job_queue.py
```

---

## Files Modified

### 1. `server.py`

#### Import Additions (Line ~15)
```python
from job_queue import get_job_queue, JobStatus, TTSJob
```

#### Lifespan Modifications (Lines ~170-190)
- Added job queue initialization: `job_q = get_job_queue()`
- Registered processing callback: `job_q.set_processing_callback(process_tts_job)`
- Added startup: `await job_q.start()`
- Added shutdown: `await job_q.stop()`

#### New Function: `process_tts_job()` (~150 lines, after audio helpers)
Extracted core TTS logic into async callback for job queue:
- Parses job parameters
- Resolves voice paths (predefined/clone modes)
- Synthesizes audio chunks with progress updates
- Stitches audio with crossfade
- Encodes output (WAV/MP3/FLAC)
- Saves to disk
- Updates job progress throughout: `job.progress`, `job.current_chunk`, `job.total_chunks`

**Function Signature:**
```python
async def process_tts_job(job: TTSJob) -> Dict:
    """Process a TTS job from the queue"""
    # Returns: {"output_path": Path, "output_format": str}
```

#### New API Endpoints (Added before original `/tts`)

**POST /tts/enqueue**
- Accepts: `CustomTTSRequest` (same schema as `/tts`)
- Returns: `{job_id, status: "queued", message, status_url, result_url}`
- HTTP Status: 202 Accepted

**GET /tts/{job_id}/status**
- Returns: `job.to_dict()` with fields:
  - `job_id`, `status`, `progress` (0-100)
  - `current_chunk`, `total_chunks`
  - `created_at`, `started_at`, `completed_at`, `elapsed_sec`
  - `error` (if failed)
- HTTP Status: 200 OK, 404 Not Found

**GET /tts/{job_id}/result**
- Returns: `FileResponse` with audio stream
- HTTP Status:
  - 200 OK (completed)
  - 404 Not Found (invalid job_id)
  - 425 Too Early (still queued/running)
  - 410 Gone (cancelled)
  - 500 Internal Server Error (failed)

**DELETE /tts/{job_id}**
- Cancels job if queued or running
- Returns: `{message: "Job {job_id} cancelled successfully"}`
- HTTP Status: 200 OK, 404 Not Found

#### Backward Compatibility
Original `POST /tts` endpoint remains **unchanged** for synchronous requests.

---

### 2. `ui/script.js`

#### New Global Variables (Top of file)
```javascript
let currentJobId = null;
let pollInterval = null;
let pollCount = 0;
const POLL_INTERVALS = [1000, 2000, 3000, 5000, 10000]; // Exponential backoff
```

#### Modified: `submitTTSRequest()` (Completely Rewritten)
Changed from synchronous to asynchronous queue-based:
1. Submits job to `/tts/enqueue` instead of `/tts`
2. Saves job info to localStorage:
   - `tts_current_job_id`: Job UUID
   - `tts_job_start_time`: Timestamp for duration calculation
   - `tts_job_params`: Voice mode and parameters for display
3. Starts polling: `pollJobStatus()`

#### New Function: `pollJobStatus()`
Polls `/tts/{job_id}/status` endpoint:
- Updates UI with progress and chunk info
- Handles terminal states:
  - `completed`: Calls `handleJobComplete()`
  - `failed`: Shows error notification
  - `cancelled`: Shows cancelled message
- Uses exponential backoff: 1s → 2s → 3s → 5s → 10s (max)

#### New Function: `scheduleNextPoll()`
Manages polling intervals with exponential backoff.

#### New Function: `handleJobComplete()`
When job completes:
1. Downloads result via `/tts/{job_id}/result`
2. Creates blob URL for audio player
3. Calculates generation time
4. Initializes WaveSurfer player
5. Clears localStorage and job state

#### New Function: `updateLoadingStatus(message, progress)`
Updates loading overlay with status message and progress percentage.

#### New Function: `clearJobState()`
Cleans up all job-related state:
- Clears `currentJobId`, `pollInterval`, `pollCount`
- Removes localStorage keys
- Stops polling timeout

#### New Function: `resumeSavedJob()`
Called on page load:
- Checks localStorage for `tts_current_job_id`
- If found, resumes polling from where it left off
- Handles browser refresh during generation

#### Modified: Cancel Button Handler
Changed from simple UI cancel to server-side job cancellation:
- Sends `DELETE /tts/{job_id}` request
- Clears local state
- Shows cancellation notification

#### Added: Page Load Hook (Bottom of DOMContentLoaded)
```javascript
await fetchInitialData();
// Resume job if browser was refreshed during generation
await resumeSavedJob();
```

---

## Key Features Implemented

### 1. **Asynchronous Processing**
- Jobs processed in background queue
- Immediate response to client (HTTP 202)
- Non-blocking UI

### 2. **Progress Tracking**
- Real-time progress updates (0-100%)
- Chunk-level progress (`current_chunk/total_chunks`)
- Elapsed time calculation

### 3. **Browser Refresh Resilience**
- Job ID persisted in localStorage
- Automatic resumption on page reload
- Status and progress preserved

### 4. **Job Lifecycle Management**
- States: QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED
- Automatic cleanup after 24 hours
- Manual cancellation support

### 5. **Backward Compatibility**
- Original `/tts` endpoint unchanged
- Existing clients continue to work
- Optional migration to new queue system

---

## Configuration

No additional configuration required. Optional settings can be added to `config.yaml`:

```yaml
job_queue:
  max_retries: 0
  job_ttl_hours: 24
  cleanup_interval_sec: 3600
  output_path: "outputs"  # Inherits from paths.output
```

---

## Testing

### 1. Automated Testing
```bash
# Run test script (requires server running)
python test_job_queue.py
```

### 2. Manual Browser Testing
1. Start server: `python server.py` or `./start.sh`
2. Open http://localhost:8004
3. Enter text and generate audio
4. Observe progress updates in loading overlay
5. **During generation:** Refresh browser
6. Verify that polling resumes automatically
7. Download result when complete

### 3. API Testing with cURL
```bash
# Submit job
curl -X POST http://localhost:8004/tts/enqueue \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","voice_mode":"predefined","predefined_voice_id":"voice.wav"}'

# Get status
curl http://localhost:8004/tts/{job_id}/status

# Download result
curl http://localhost:8004/tts/{job_id}/result -o result.wav

# Cancel job
curl -X DELETE http://localhost:8004/tts/{job_id}
```

---

## Migration Notes

### For Users
- **No action required** - UI automatically uses new queue system
- Backward compatible with existing workflows
- Generation now survives browser refreshes

### For API Clients
- **Optional migration** to `/tts/enqueue` for async benefits
- Original `/tts` endpoint still available for sync requests
- New endpoints provide better progress tracking

### For Developers
- Job queue is in-memory (survives during runtime only)
- For production: Consider Redis backend for job persistence
- Cleanup worker prevents memory leaks (24h TTL)

---

## Performance Characteristics

- **Throughput**: Sequential processing (1 job at a time)
- **Memory**: In-memory job store with automatic cleanup
- **Polling**: Exponential backoff (1s to 10s max)
- **Storage**: Output files saved to disk, references in memory
- **Cleanup**: Hourly sweep removes jobs older than 24 hours

---

## Future Enhancements (Optional)

1. **Persistent Storage**: Redis/SQLite backend for server restart resilience
2. **WebSocket Updates**: Real-time push instead of polling
3. **Job Priority**: High/normal/low priority queues
4. **Batch Jobs**: Process multiple texts as single job
5. **Job History**: User-specific job history view
6. **Rate Limiting**: Per-user job quotas
7. **Concurrent Processing**: Multiple workers for GPU efficiency

---

## Troubleshooting

### Issue: Jobs not processing
**Solution:** Check server logs, verify TTS model loaded

### Issue: Jobs disappearing after restart
**Expected:** In-memory storage, jobs cleared on restart. Implement Redis for persistence.

### Issue: High memory usage
**Solution:** Decrease `job_ttl_hours` in config, increase cleanup frequency

### Issue: Polling too frequent/infrequent
**Solution:** Adjust `POLL_INTERVALS` array in `ui/script.js`

---

## Summary Statistics

- **Lines Added**: ~650 (330 job_queue.py + 200 server.py + 120 script.js)
- **New Files**: 3 (job_queue.py, JOB_QUEUE_GUIDE.md, test_job_queue.py)
- **Modified Files**: 2 (server.py, ui/script.js)
- **API Endpoints Added**: 4 (/enqueue, /status, /result, DELETE)
- **Backward Compatibility**: 100% (original /tts unchanged)

---

**Implementation Status: COMPLETE ✓**
- All server-side components implemented
- UI updated with localStorage persistence
- Documentation and tests created
- Ready for end-to-end testing
