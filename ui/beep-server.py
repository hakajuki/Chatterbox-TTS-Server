#!/usr/bin/env python3
"""
Beep Sync Server - FastAPI service for audio censorship using Whisper + pydub.
Provides a web UI and API endpoint to detect and censor profanity in audio files.
"""
import logging
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

import torch
import uvicorn
from faster_whisper import WhisperModel
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydub import AudioSegment

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- Global Configuration ---
DEFAULT_MODEL_SIZE = "small.en"
DEFAULT_MIN_GAP_SEC = 0.1
DEFAULT_BEEP_PATH = Path(__file__).parent / "beep.wav"

# Device selection: prefer CUDA, then Apple MPS, else CPU
if torch.cuda.is_available():
    DEVICE = "cuda"
# elif getattr(torch.backends, 'mps', None) is not None and torch.backends.mps.is_available():
#     DEVICE = "mps"
else:
    DEVICE = "cpu"

COMPUTE_TYPE = "float16" if DEVICE in ("cuda", "mps") else "int8"

logger.info(f"Beep Sync Server initializing: device={DEVICE}, compute_type={COMPUTE_TYPE}")

# Load Whisper model globally
model = WhisperModel(DEFAULT_MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
logger.info(f"Whisper model '{DEFAULT_MODEL_SIZE}' loaded successfully.")

# --- Default Bad Words List ---
DEFAULT_BAD_WORDS = [
    "fuck", "fucking", "fucked", "fucker", "shit", "shitting", "asshole", "bitch",
    "damn", "cunt", "dick", "pussy", "motherfucker", "bastard", "cock", "twat",
]

# --- Audio Censorship Function ---
def censor_audio_with_beep(
    input_audio_path: Path,
    output_audio_path: Path,
    bad_words: List[str],
    beep_path: Path = DEFAULT_BEEP_PATH,
    min_gap_sec: float = DEFAULT_MIN_GAP_SEC
) -> dict:
    """
    Detect bad words using faster-whisper and replace them with beep sounds.
    
    Args:
        input_audio_path: Path to input audio file
        output_audio_path: Path to save censored audio
        bad_words: List of words to censor (case-insensitive)
        beep_path: Path to beep sound file
        min_gap_sec: Minimum gap to consider words as consecutive group
        
    Returns:
        dict with censorship statistics and result
    """
    try:
        # Load audio
        audio = AudioSegment.from_file(str(input_audio_path))
        sample_rate = audio.frame_rate
        duration_sec = len(audio) / 1000
        logger.info(f"Loaded audio: {input_audio_path.name}, Duration: {duration_sec:.2f}s, SR: {sample_rate}Hz")
        
        # Transcribe with word timestamps
        segments, info = model.transcribe(
            str(input_audio_path),
            word_timestamps=True,
            language="en"
        )
        
        # Collect bad word timestamps
        bad_timestamps = []
        detected_words = []
        for segment in segments:
            for word_info in segment.words:
                word = word_info.word.strip().lower().rstrip('.,!?')
                if word in bad_words or any(bw in word for bw in bad_words):
                    bad_timestamps.append((word_info.start, word_info.end))
                    detected_words.append(word)
                    logger.info(f"Detected: '{word}' at {word_info.start:.2f}s - {word_info.end:.2f}s")
        
        if not bad_timestamps:
            logger.info("No bad words detected. Returning original audio.")
            audio.export(str(output_audio_path), format="wav")
            return {
                "status": "success",
                "detected_count": 0,
                "detected_words": [],
                "groups_censored": 0,
                "duration_sec": duration_sec
            }
        
        # Sort and merge consecutive timestamps into groups
        bad_timestamps.sort(key=lambda x: x[0])
        merged_groups = []
        current_start = bad_timestamps[0][0]
        current_end = bad_timestamps[0][1]
        
        for start, end in bad_timestamps[1:]:
            if start - current_end <= min_gap_sec:
                current_end = max(current_end, end)
            else:
                merged_groups.append((current_start, current_end))
                current_start = start
                current_end = end
        merged_groups.append((current_start, current_end))
        
        # Load beep sound
        if not beep_path.exists():
            logger.warning(f"Beep file not found at {beep_path}, creating silence beep")
            beep = AudioSegment.silent(duration=200, frame_rate=sample_rate)
        else:
            beep = AudioSegment.from_file(str(beep_path))
        
        beep_duration_ms = len(beep)
        logger.info(f"Beep duration: {beep_duration_ms / 1000:.2f}s, Groups to censor: {len(merged_groups)}")
        
        # Apply beep censorship
        censored_audio = audio
        offset_ms = 0
        
        for group_start_sec, group_end_sec in sorted(merged_groups, reverse=True):
            group_start_ms = int(group_start_sec * 1000) + offset_ms
            group_end_ms = int(group_end_sec * 1000) + offset_ms
            group_duration_ms = group_end_ms - group_start_ms
            
            if group_duration_ms <= beep_duration_ms:
                beep_segment = beep[:group_duration_ms]
            else:
                repeats = group_duration_ms // beep_duration_ms
                remainder_ms = group_duration_ms % beep_duration_ms
                beep_segment = beep * repeats
                if remainder_ms > 0:
                    beep_segment += beep[:remainder_ms]
            
            before = censored_audio[:group_start_ms]
            after = censored_audio[group_start_ms + len(beep_segment):]
            censored_audio = before + beep_segment + after
            offset_ms += len(beep_segment) - group_duration_ms
        
        # Export result
        censored_audio.export(str(output_audio_path), format="wav")
        logger.info(f"Censored audio saved: {output_audio_path.name}")
        
        return {
            "status": "success",
            "detected_count": len(bad_timestamps),
            "detected_words": list(set(detected_words)),
            "groups_censored": len(merged_groups),
            "duration_sec": duration_sec,
            "output_duration_sec": len(censored_audio) / 1000
        }
        
    except Exception as e:
        logger.error(f"Error during censorship: {e}", exc_info=True)
        raise


# --- FastAPI Application ---
app = FastAPI(
    title="Beep Sync Server",
    description="Audio censorship service using Whisper ASR + pydub",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (UI assets)
ui_path = Path(__file__).parent
if ui_path.is_dir():
    app.mount("/static", StaticFiles(directory=str(ui_path)), name="static")
    # Also serve vendor assets (e.g. wavesurfer) at /vendor
    vendor_path = ui_path / "vendor"
    if vendor_path.is_dir():
        app.mount("/vendor", StaticFiles(directory=str(vendor_path)), name="vendor_files")
    else:
        logger.warning(f"Vendor directory not found at '{vendor_path}' - /vendor routes will 404")


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the beep sync UI."""
    index_beep = ui_path / "index-beep.html"
    if index_beep.exists():
        return FileResponse(index_beep)
    return HTMLResponse("<h1>Beep Sync Server</h1><p>UI not found. Check index-beep.html.</p>", status_code=404)


@app.get("/styles.css")
async def serve_styles():
    """Serve CSS file."""
    styles_file = ui_path / "styles.css"
    if styles_file.exists():
        return FileResponse(styles_file, media_type="text/css")
    raise HTTPException(status_code=404, detail="styles.css not found")


@app.get("/script-beep.js")
async def serve_script():
    """Serve JavaScript file."""
    script_file = ui_path / "script-beep.js"
    if script_file.exists():
        return FileResponse(script_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="script-beep.js not found")


@app.post("/api/censor")
async def censor_audio_endpoint(
    audio_file: UploadFile = File(...),
    bad_words: str = Form(...)
):
    """
    Censor profanity in uploaded audio file.
    
    Args:
        audio_file: Audio file to censor (.wav, .mp3, etc.)
        bad_words: Comma-separated list of words to censor
        
    Returns:
        Censored audio file (WAV format)
    """
    logger.info(f"Received censor request: file={audio_file.filename}")
    
    # Parse bad words
    words_list = [w.strip().lower() for w in bad_words.split(",") if w.strip()]
    if not words_list:
        words_list = DEFAULT_BAD_WORDS
    logger.info(f"Bad words list ({len(words_list)} words): {words_list[:5]}...")
    
    # Validate file
    if not audio_file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    allowed_extensions = [".wav", ".mp3", ".m4a", ".flac", ".ogg"]
    file_ext = Path(audio_file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Create temp files
    temp_dir = Path(tempfile.mkdtemp(prefix="beep_sync_"))
    try:
        input_path = temp_dir / f"input{file_ext}"
        output_path = temp_dir / "censored_output.wav"
        
        # Save uploaded file
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        logger.info(f"Saved uploaded file to: {input_path}")
        
        # Perform censorship
        result = censor_audio_with_beep(
            input_audio_path=input_path,
            output_audio_path=output_path,
            bad_words=words_list,
            min_gap_sec=DEFAULT_MIN_GAP_SEC
        )
        
        if not output_path.exists():
            raise HTTPException(status_code=500, detail="Censorship failed: output not generated")
        
        logger.info(f"Censorship complete: {result}")
        
        # Return censored audio
        return FileResponse(
            path=str(output_path),
            media_type="audio/wav",
            filename=f"censored_{audio_file.filename.rsplit('.', 1)[0]}.wav",
            headers={
                "X-Detected-Count": str(result["detected_count"]),
                "X-Groups-Censored": str(result["groups_censored"]),
                "X-Detected-Words": ",".join(result["detected_words"])
            },
            background=lambda: shutil.rmtree(temp_dir, ignore_errors=True)
        )
        
    except HTTPException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.error(f"Error processing audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "model": DEFAULT_MODEL_SIZE
    }


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8005
    
    logger.info(f"Starting Beep Sync Server on http://{host}:{port}")
    logger.info(f"Web UI: http://localhost:{port}/")
    logger.info(f"API Docs: http://localhost:{port}/docs")
    
    uvicorn.run(
        "beep-server:app",
        host=host,
        port=port,
        log_level="info",
        reload=False
    )