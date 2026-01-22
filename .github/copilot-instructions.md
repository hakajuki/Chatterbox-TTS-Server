# Copilot / AI Agent Instructions for Chatterbox-TTS-Server

This file gives focused, actionable guidance so an AI coding agent can be productive immediately in this repo.

1) Purpose & Big Picture
- This project is a FastAPI server that exposes an OpenAI-compatible TTS API around the `chatterbox-tts` engines (Original + Turbo). Core pieces: `server.py` (HTTP entry points), `engine.py` (engine loading / inference orchestration), and `models.py` / `download_model.py` (model acquisition). The Web UI lives in `ui/` and static assets in `static/`.

2) Key flows and boundaries (what to change where)
- HTTP/API: `server.py` defines endpoints; primary TTS endpoint is `/tts`. Use `/docs` for live OpenAPI exploration.
- Engine lifecycle: `engine.py` handles hot-swapping between engines and model loading via `ChatterboxTTS.from_pretrained()`; edits that change model loading or device selection belong here.
- Config: `config.py` implements `YamlConfigManager` and manages `config.yaml`. Prefer config updates in `config.py` or `config.yaml` rather than hard-coding values.
- UI: `ui/` contains the client; presets are in `ui/presets.yaml`. Small frontend changes (presets, UI toggles) go there; server endpoints must remain stable to avoid breaking clients.

3) Developer workflows & common commands
- Quick local start (automated): run the launcher — `./start.sh` (macOS/Linux) or `start.bat` on Windows. CLI flags supported by `start.py`: `--cpu`, `--nvidia`, `--nvidia-cu128`, `--rocm`, `--reinstall`, `--upgrade`, `--verbose`.
- Manual install: create venv, then `pip install -r requirements.txt` (or `requirements-nvidia.txt` / `requirements-nvidia-cu128.txt` / `requirements-rocm.txt` depending on GPU).
- Docker: `docker compose up -d` uses `docker-compose.yml` and hardware-specific compose files in the repo root.
- Verify GPU (from README):
  python -c "import torch; print(torch.__version__, torch.cuda.is_available())"

4) Project-specific conventions & patterns
- Config-first: runtime behavior is driven by `config.yaml` (created by `config.py` if missing). Avoid sprinkling literals — add/consult `config.yaml` for defaults and UI-persistent state (`ui_state`).
- Chunking & audiobook flow: Long-text handling is explicit — `split_text` and `chunk_size` parameters control chunking. Changes to chunking logic will affect concatenation and voice consistency.
- Voice modes: two modes — `Predefined Voices` (files under `voices/`) and `Voice Cloning` (reference upload). Code paths that accept/upload audio must account for both.
- Paralinguistic tags: Turbo supports tags like `[laugh]`, `[cough]` used in `ui/presets.yaml`. When editing tokenizer/prompt handling, preserve tag passthrough.

5) Integration & external dependencies
- Models are downloaded via Hugging Face using `ChatterboxTTS.from_pretrained()`; `download_model.py` can prefetch artifacts. Model repo selection and HF cache path are configurable via `config.yaml`.
- Optional audio tools: `ffmpeg`, `libsndfile1`, and `parselmouth` may be used for post-processing; guard code paths if these are missing.
 - Utility scripts: `ui/beep-server.py` is now a **standalone FastAPI server** for audio censorship (port 8005). It provides both a web UI (`index-beep.html`) and REST API (`/api/censor`). Dependencies: `faster-whisper`, `pydub`, `torch` (GPU optional), and `uvicorn`. Not invoked by the main TTS server—runs independently.

6a) `ui/beep-server.py` — Beep Sync Server
- **Purpose**: Standalone FastAPI service that detects profanity in audio files using Whisper ASR and replaces bad words with beep sounds.
- **Architecture**: Full web server with UI, API, CORS, static file serving, and health check endpoint.
- **Web UI**: `ui/index-beep.html` + `ui/script-beep.js` provide drag-and-drop file upload, bad words input textarea, and audio player for results.
- **API Endpoint**: `POST /api/censor` — accepts `audio_file` (multipart/form-data) and `bad_words` (comma-separated string). Returns censored WAV with detection stats in headers.
- **Key variables**: `DEFAULT_BAD_WORDS` (profanity list), `DEFAULT_BEEP_PATH` (`ui/beep.wav`), `DEFAULT_MIN_GAP_SEC` (0.1s grouping threshold), `DEFAULT_MODEL_SIZE` (`small.en`).
- **Device selection**: Auto-detects CUDA → MPS → CPU; sets `compute_type` (`float16` for accelerators, `int8` for CPU).
- **Quick start**:
  ```bash
  cd ui
  python generate_beep.py    # Create beep.wav
  python beep-server.py       # Start server on http://localhost:8005
  ```
- **Testing**: Run `python ui/test_beep_server.py` to create synthetic audio and verify API.
- **Styling**: Uses same `styles.css` as main UI; file upload components styled with `.file-drop-zone` and `.file-info` BEM classes.
- **Caution**: `DEFAULT_BAD_WORDS` contains explicit terms. For localization or custom lists, consider externalizing to a config file or environment variable.

6) Debugging pointers (where to look first)
- API docs: visit `/docs` when server is running to inspect request/response schemas.
- Health/initial data: `/api/ui/initial-data` returns a good snapshot of server status and config.
- Logs: the launcher prints install/start logs; `server.py` prints startup, loaded engine, and device info. Use the PyTorch GPU snippet above to confirm device availability.
- Repro steps for GPU issues: run launcher with `--reinstall --verbose` to reproduce install problems.

7) Useful files to reference when coding
- `server.py` — HTTP endpoints, request validation for main TTS server
- `engine.py` — model load & inference orchestration
- `config.py` / `config.yaml` — runtime configuration management
- `ui/presets.yaml` — example presets and paralinguistic tag usage
- `voices/` — predefined voice artifacts and expected layout
- `download_model.py` — pre-download helper for Hugging Face artifacts
- `ui/beep-server.py` — **Standalone FastAPI server** for audio censorship. Includes Whisper ASR transcription, bad word detection with timestamp grouping, and beep replacement logic. Runs independently on port 8005 with its own UI (`index-beep.html` + `script-beep.js`). Full REST API at `/api/censor`, health check at `/api/health`, and interactive docs at `/docs`.
- `ui/generate_beep.py` — Utility to create `beep.wav` (1kHz sine wave, 200ms, with fade in/out).
- `ui/test_beep_server.py` — Test harness for Beep Sync Server; creates synthetic audio and validates API responses.

8) What not to change without extra care
- API surface (endpoint names, param names) used by the UI and Colab demo — changing these requires coordinated UI updates in `ui/` and docs in `README.md`.
- Model loading behavior in `engine.py` — this affects memory/device selection and hot-swap semantics.

9) When adding tests or CI
- There are no existing tests; if you add tests, keep them lightweight and focused (small model stubs or mocks for `ChatterboxTTS`). Prefer unit tests around `config.py` and chunking logic.

10) Quick ask for the reviewer
- If any behavior isn't discoverable (custom environment variables, secret paths, or private HF repos), tell me and I will add a short note here.

---
If this looks good I can iterate to include short example request payloads for `/tts`, or merge any content from an existing `.github/copilot-instructions.md` you expect preserved. Ready for feedback.
