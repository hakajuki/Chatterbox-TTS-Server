# TTS Job Queue System - Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT (Browser)                             │
│                                                                      │
│  ┌──────────────┐      ┌───────────────┐      ┌─────────────────┐ │
│  │   UI Form    │─────▶│  script.js    │─────▶│  localStorage   │ │
│  │ (Text Input) │      │ (Queue Logic) │      │  - job_id       │ │
│  └──────────────┘      └───────────────┘      │  - start_time   │ │
│         │                     │                │  - params       │ │
│         │                     │                └─────────────────┘ │
│         │                     │                                     │
└─────────┼─────────────────────┼─────────────────────────────────────┘
          │                     │
          │ 1. Submit           │ 2. Poll Status
          │ /tts/enqueue        │ /tts/{id}/status
          ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SERVER (FastAPI)                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │                      server.py                                  ││
│  │  ┌──────────────────────────────────────────────────────────┐  ││
│  │  │ POST /tts/enqueue         Returns: {job_id, status_url} │  ││
│  │  └──────────────────────────────────────────────────────────┘  ││
│  │  ┌──────────────────────────────────────────────────────────┐  ││
│  │  │ GET /tts/{id}/status      Returns: {status, progress}    │  ││
│  │  └──────────────────────────────────────────────────────────┘  ││
│  │  ┌──────────────────────────────────────────────────────────┐  ││
│  │  │ GET /tts/{id}/result      Returns: Audio FileResponse    │  ││
│  │  └──────────────────────────────────────────────────────────┘  ││
│  │  ┌──────────────────────────────────────────────────────────┐  ││
│  │  │ DELETE /tts/{id}          Cancels job                    │  ││
│  │  └──────────────────────────────────────────────────────────┘  ││
│  └────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│                              ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │                      job_queue.py                               ││
│  │                                                                 ││
│  │  ┌────────────────┐    ┌──────────────┐    ┌───────────────┐  ││
│  │  │   JobStatus    │    │   TTSJob     │    │  TTSJobQueue  │  ││
│  │  │     Enum       │    │  (Dataclass) │    │   (Manager)   │  ││
│  │  ├────────────────┤    ├──────────────┤    ├───────────────┤  ││
│  │  │ • QUEUED       │    │ • job_id     │    │ • submit_job()│  ││
│  │  │ • RUNNING      │    │ • status     │    │ • get_job()   │  ││
│  │  │ • COMPLETED    │    │ • params     │    │ • cancel_job()│  ││
│  │  │ • FAILED       │    │ • progress   │    │ • _worker()   │  ││
│  │  │ • CANCELLED    │    │ • output_path│    │ • _cleanup()  │  ││
│  │  └────────────────┘    └──────────────┘    └───────────────┘  ││
│  └────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│                              ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │                   Background Workers                            ││
│  │                                                                 ││
│  │  ┌────────────────────────┐    ┌──────────────────────────┐   ││
│  │  │   Job Processor        │    │   Cleanup Worker         │   ││
│  │  ├────────────────────────┤    ├──────────────────────────┤   ││
│  │  │ • Dequeues jobs        │    │ • Runs every hour        │   ││
│  │  │ • Calls process_tts    │    │ • Removes jobs > 24h old │   ││
│  │  │ • Updates progress     │    │ • Prevents memory leaks  │   ││
│  │  │ • Saves output         │    │                          │   ││
│  │  └────────────────────────┘    └──────────────────────────┘   ││
│  └────────────────────────────────────────────────────────────────┘│
│                              │                                       │
│                              ▼                                       │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │                   TTS Engine (engine.py)                        ││
│  │  • ChatterboxTTS model loading                                 ││
│  │  • Audio synthesis (Original/Turbo)                            ││
│  │  • Chunk processing                                            ││
│  └────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

## Request Flow

### 1. Job Submission Flow

```
User clicks "Generate"
        │
        ▼
script.js collects form data
        │
        ▼
POST /tts/enqueue
        │
        ▼
server.py creates TTSJob
        │
        ▼
job_queue.submit_job(job)
        │
        ▼
Job added to asyncio.Queue
        │
        ▼
Returns {job_id, status: "queued"}
        │
        ▼
script.js saves to localStorage
        │
        ▼
Start polling /tts/{id}/status
```

### 2. Job Processing Flow

```
Background worker running
        │
        ▼
Dequeue next job
        │
        ▼
job.status = RUNNING
        │
        ▼
Call process_tts_job(job)
        │
        ├──▶ Parse parameters
        ├──▶ Load voice
        ├──▶ Split text into chunks
        │    │
        │    └──▶ For each chunk:
        │         ├──▶ Synthesize audio
        │         ├──▶ Update job.current_chunk
        │         └──▶ Calculate job.progress
        │
        ├──▶ Stitch audio chunks
        ├──▶ Encode output (WAV/MP3/FLAC)
        └──▶ Save to disk
        │
        ▼
job.status = COMPLETED
job.output_path = "/path/to/audio.wav"
```

### 3. Status Polling Flow

```
Client polls /tts/{id}/status
        │
        ▼
server.py calls job_queue.get_job(id)
        │
        ▼
Return job.to_dict()
{
  "job_id": "...",
  "status": "running",
  "progress": 45,
  "current_chunk": 3,
  "total_chunks": 7
}
        │
        ▼
script.js updates UI
        │
        ├──▶ If queued/running → Schedule next poll (backoff)
        └──▶ If completed → Fetch result
```

### 4. Result Download Flow

```
Job status = "completed"
        │
        ▼
GET /tts/{id}/result
        │
        ▼
server.py checks job.status
        │
        ├──▶ If not completed → HTTP 425 (Too Early)
        └──▶ If completed:
             │
             ▼
        FileResponse(job.output_path)
             │
             ▼
        Browser downloads audio
             │
             ▼
        script.js creates blob URL
             │
             ▼
        Initialize WaveSurfer player
             │
             ▼
        Clear localStorage
```

## State Transitions

```
Job Lifecycle States:
┌───────────────────────────────────────────────────────────────┐
│                                                                │
│   [CREATED] ──submit──▶ [QUEUED] ──worker──▶ [RUNNING]        │
│                            │                     │             │
│                            │                     ├──success──▶ [COMPLETED]
│                            │                     │             │
│                            │                     ├──error────▶ [FAILED]
│                            │                     │             │
│                            └──cancel────────────┬┘             │
│                                                 │              │
│                                            [CANCELLED]          │
│                                                                │
└───────────────────────────────────────────────────────────────┘

Terminal States (job complete):
• COMPLETED
• FAILED  
• CANCELLED
```

## Data Flow

```
┌──────────────┐
│   Request    │
│   Params     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   TTSJob     │
│ (In Memory)  │
└──────┬───────┘
       │
       │ Processing
       ▼
┌──────────────┐
│ Audio Chunks │
│  (Tensors)   │
└──────┬───────┘
       │
       │ Stitching
       ▼
┌──────────────┐
│ Final Audio  │
│   (Bytes)    │
└──────┬───────┘
       │
       │ Encoding
       ▼
┌──────────────┐
│ Output File  │
│  (On Disk)   │
└──────────────┘
```

## Storage Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (Client)                          │
│  localStorage:                                               │
│  • tts_current_job_id      (string: UUID)                   │
│  • tts_job_start_time      (string: timestamp)              │
│  • tts_job_params          (JSON: voice settings)           │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ HTTP
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Server (Memory)                           │
│  job_queue._jobs:       Dict[str, TTSJob]                   │
│  • Key: job_id                                              │
│  • Value: TTSJob object with status, progress, metadata     │
│  • Cleanup: Remove after 24 hours                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ File I/O
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Filesystem (Disk)                         │
│  outputs/                                                    │
│  • tts_job_{uuid}_{timestamp}.{format}                      │
│  • Persists across server restarts                          │
│  • Manual cleanup required                                  │
└─────────────────────────────────────────────────────────────┘
```

## Timing Diagram

```
Time  Client                Server               Job Queue            TTS Engine
─────┼─────────────────────┼────────────────────┼────────────────────┼───────────
0ms   │ POST /enqueue       │                    │                    │
      │ ───────────────────▶│                    │                    │
      │                     │ submit_job()       │                    │
10ms  │                     │ ──────────────────▶│                    │
      │                     │                    │ [Job in Queue]     │
      │                     │ {job_id: "abc"}    │                    │
      │ ◀───────────────────│                    │                    │
      │                     │                    │                    │
100ms │ GET /status         │                    │                    │
      │ ───────────────────▶│ get_job("abc")     │                    │
      │                     │ ──────────────────▶│                    │
      │                     │ {status: "queued"} │                    │
      │ ◀───────────────────│                    │                    │
      │                     │                    │                    │
      │ [1s delay]          │                    │ worker dequeues    │
      │                     │                    │ ──────────────────▶│
1s    │                     │                    │                    │ synthesize()
      │ GET /status         │                    │ [status=RUNNING]   │
2s    │ ───────────────────▶│                    │ progress=20%       │
      │ {progress: 20%}     │                    │                    │
      │ ◀───────────────────│                    │                    │
      │                     │                    │                    │
      │ [2s delay]          │                    │                    │
4s    │ GET /status         │                    │ progress=50%       │
      │ ───────────────────▶│                    │                    │
      │ {progress: 50%}     │                    │                    │
      │ ◀───────────────────│                    │                    │
      │                     │                    │                    │
      │ [3s delay]          │                    │ progress=100%      │
7s    │ GET /status         │                    │ [status=COMPLETED] │
      │ ───────────────────▶│                    │                    │
      │ {status: "completed"}│                   │                    │
      │ ◀───────────────────│                    │                    │
      │                     │                    │                    │
      │ GET /result         │                    │                    │
8s    │ ───────────────────▶│                    │                    │
      │ [audio stream]      │                    │                    │
      │ ◀───────────────────│                    │                    │
      │ ✓ Download Complete │                    │                    │
```

## Error Handling

```
┌─────────────────┐
│   Try Submit    │
└────────┬────────┘
         │
    ┌────▼────┐
    │ Success?│
    └────┬────┘
         │
    ┌────┴────┐
    │   Yes   │   No
    │         │    │
    │         │    └──▶ Show error notification
    │         │         Clear job state
    │         │
    ▼         │
┌──────────────┐
│ Start Poll   │
└──────┬───────┘
       │
  ┌────▼────┐
  │ Status? │
  └────┬────┘
       │
  ┌────┴────────────────┐
  │ queued/running      │ completed    │ failed/cancelled
  │                     │              │
  ▼                     ▼              ▼
Schedule next poll   Download      Show error
                     Success!      Clear state
```

---

## Key Design Decisions

1. **Async Queue**: Uses `asyncio.Queue` for simple, reliable job ordering
2. **Polling**: Client-side polling with exponential backoff (simple, no WebSocket complexity)
3. **In-Memory**: Fast access, automatic cleanup (trade-off: jobs lost on restart)
4. **Progress Tracking**: Chunk-level granularity for user feedback
5. **LocalStorage**: Browser-side persistence for refresh resilience
6. **Backward Compatible**: Original `/tts` endpoint preserved

## Scalability Considerations

- **Current**: Sequential processing, single worker
- **Future**: Multiple workers, GPU parallelization
- **Persistence**: Add Redis for production deployments
- **Distribution**: Horizontal scaling with shared queue backend
