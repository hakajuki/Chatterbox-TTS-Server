# Quick Start: TTS Job Queue System

## What Changed?

The TTS generation now uses an **asynchronous queue system**:
- ✅ Non-blocking: Get immediate response with job ID
- ✅ Progress tracking: See real-time generation progress
- ✅ Browser refresh resilient: Jobs survive page reloads
- ✅ Backward compatible: Original `/tts` endpoint still works

## For Users (Web UI)

### Normal Usage
1. Enter text and configure settings as before
2. Click "Generate"
3. Watch progress in the loading overlay
4. **NEW:** You can now refresh the browser during generation!
5. Audio will download when complete

### Refreshing During Generation
- Job ID is saved in localStorage
- Progress automatically resumes after refresh
- No need to re-submit the request

### Canceling Jobs
- Click "Cancel" button during generation
- Job will be cancelled on the server
- Safe to start a new generation immediately

## For Developers (API)

### Synchronous (Original)
```bash
curl -X POST http://localhost:8004/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello","voice_mode":"predefined","predefined_voice_id":"voice.wav"}' \
  -o output.wav
```

### Asynchronous (New Queue System)

**1. Submit Job:**
```bash
curl -X POST http://localhost:8004/tts/enqueue \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello","voice_mode":"predefined","predefined_voice_id":"voice.wav"}'

Response:
{
  "job_id": "abc-123-def-456",
  "status": "queued",
  "message": "Job queued for processing",
  "status_url": "/tts/abc-123-def-456/status",
  "result_url": "/tts/abc-123-def-456/result"
}
```

**2. Poll Status:**
```bash
curl http://localhost:8004/tts/abc-123-def-456/status

Response:
{
  "job_id": "abc-123-def-456",
  "status": "running",        # queued | running | completed | failed | cancelled
  "progress": 45,              # 0-100
  "current_chunk": 3,
  "total_chunks": 7,
  "created_at": 1234567890.0,
  "started_at": 1234567891.0,
  "elapsed_sec": 5.2
}
```

**3. Download Result (when status = "completed"):**
```bash
curl http://localhost:8004/tts/abc-123-def-456/result -o output.wav
```

**4. Cancel Job (optional):**
```bash
curl -X DELETE http://localhost:8004/tts/abc-123-def-456
```

## Testing

### Quick Test
```bash
# Make sure server is running
python server.py

# In another terminal, run the test script
python test_job_queue.py
```

The test script will:
1. Submit a test job
2. Poll status with progress updates
3. Download the result
4. Test error cases

### Browser Test
1. Start server: `python server.py` or `./start.sh`
2. Open http://localhost:8004
3. Generate audio with any text
4. **During generation:** Press F5 to refresh browser
5. Watch polling resume automatically
6. Result downloads when complete

## File Structure

```
Chatterbox-TTS-Server-main/
├── job_queue.py                 # NEW: Job queue implementation
├── server.py                     # MODIFIED: Added queue endpoints
├── ui/
│   └── script.js                # MODIFIED: Queue-based client
├── test_job_queue.py            # NEW: Automated tests
├── JOB_QUEUE_GUIDE.md           # NEW: Detailed documentation
├── IMPLEMENTATION_SUMMARY.md     # NEW: Complete change log
└── QUICK_START.md               # NEW: This file
```

## Configuration (Optional)

Add to `config.yaml` to customize behavior:

```yaml
job_queue:
  job_ttl_hours: 24              # How long to keep completed jobs
  cleanup_interval_sec: 3600     # How often to run cleanup (1 hour)
```

## Troubleshooting

### Jobs Not Visible After Server Restart
- **Expected behavior**: Jobs are stored in memory
- **Solution**: Jobs are cleaned up on restart (by design)
- **Future enhancement**: Add Redis for persistent storage

### Progress Not Updating
- Check browser console for errors
- Verify polling is not blocked by CORS
- Ensure job ID is valid

### Result Download Fails
- Wait for `status === "completed"`
- Check server logs for TTS errors
- Verify output directory is writable

## Need Help?

- Read full guide: [JOB_QUEUE_GUIDE.md](JOB_QUEUE_GUIDE.md)
- Implementation details: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- Check server logs: `python server.py` output
- Run tests: `python test_job_queue.py`

## Migration from Old System

**No migration needed!** The system is backward compatible:
- Web UI automatically uses new queue system
- Original `/tts` endpoint still works
- Existing integrations continue to function

To use the new system in your own code, switch from `/tts` to `/tts/enqueue` and implement polling.
