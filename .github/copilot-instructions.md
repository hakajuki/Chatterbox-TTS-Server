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
 - Utility scripts: `ui/beep-server.py` depends on `faster-whisper`, `pydub`, and `torch` (GPU optional). Treat it as a developer utility — it runs locally on audio files and is not invoked by the main server. When editing or reusing it, ensure the environment includes `faster-whisper` and `pydub` and that required model weights are available.

6a) `ui/beep-server.py` quick notes
- Purpose: detect profanity/forbidden words via speech-to-text timestamps and replace the corresponding audio ranges with a beep audio segment. Useful for creating censored preview clips.
- Key variables: `BAD_WORDS` (list of tokens — expand with local-language tokens like Vietnamese slang), `beep_path` (path to beep wav), `min_gap_sec` (how close words are grouped), and `model_size` (e.g., `small.en`).
- Hardware: the script auto-selects `device = 'cuda' if torch.cuda.is_available() else 'cpu'` and chooses `compute_type` (`float16` on CUDA, `int8` otherwise).
- Quick run: the script includes an example invocation at the bottom; you can run it directly:

```bash
python ui/beep-server.py
```

- Caution: The `BAD_WORDS` list contains explicit terms; avoid committing additions with offensive content to public branches. Consider keeping a localized words file out-of-repo or loading from `config.yaml` if you need localization.

6) Debugging pointers (where to look first)
- API docs: visit `/docs` when server is running to inspect request/response schemas.
- Health/initial data: `/api/ui/initial-data` returns a good snapshot of server status and config.
- Logs: the launcher prints install/start logs; `server.py` prints startup, loaded engine, and device info. Use the PyTorch GPU snippet above to confirm device availability.
- Repro steps for GPU issues: run launcher with `--reinstall --verbose` to reproduce install problems.

7) Useful files to reference when coding
- `server.py` — HTTP endpoints, request validation
- `engine.py` — model load & inference orchestration
- `config.py` / `config.yaml` — runtime configuration management
- `ui/presets.yaml` — example presets and paralinguistic tag usage
- `voices/` — predefined voice artifacts and expected layout
- `download_model.py` — pre-download helper for Hugging Face artifacts
- `ui/beep-server.py` — local utility that censors audio by detecting "bad words" using `faster-whisper` and replacing them with a beep (`pydub` audio edits). It's a standalone script (not integrated into the FastAPI endpoints); it accepts input/output file paths and is configurable via the `BAD_WORDS` list and `min_gap_sec` parameter.

8) What not to change without extra care
- API surface (endpoint names, param names) used by the UI and Colab demo — changing these requires coordinated UI updates in `ui/` and docs in `README.md`.
- Model loading behavior in `engine.py` — this affects memory/device selection and hot-swap semantics.

9) When adding tests or CI
- There are no existing tests; if you add tests, keep them lightweight and focused (small model stubs or mocks for `ChatterboxTTS`). Prefer unit tests around `config.py` and chunking logic.

10) Quick ask for the reviewer
- If any behavior isn't discoverable (custom environment variables, secret paths, or private HF repos), tell me and I will add a short note here.

---
If this looks good I can iterate to include short example request payloads for `/tts`, or merge any content from an existing `.github/copilot-instructions.md` you expect preserved. Ready for feedback.
