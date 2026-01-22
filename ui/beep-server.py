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
elif getattr(torch.backends, 'mps', None) is not None and torch.backends.mps.is_available():
    DEVICE = "mps"
else:
    DEVICE = "cpu"

COMPUTE_TYPE = "float16" if DEVICE in ("cuda", "mps") else "int8"

logger.info(f"Beep Sync Server initializing: device={DEVICE}, compute_type={COMPUTE_TYPE}")

# Load Whisper model globally
model = WhisperModel(DEFAULT_MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
logger.info(f"Whisper model '{DEFAULT_MODEL_SIZE}' loaded successfully.")

BAD_WORDS = [
    "fuck", "fucking", "fucked", "fucker", "shit", "shitting", "asshole", "bitch",
    "damn", "cunt", "dick", "pussy", "motherfucker", "bastard", "cock", "twat",
    # Thêm từ tiếng Việt nếu cần: "đm", "địt", "cặc", "lồn",...
]

def censor_audio_with_beep(
    input_audio_path,
    output_audio_path,
    bad_words=BAD_WORDS,
    beep_path="beep.wav",
    min_gap_sec=0.1                 # Khoảng cách nhỏ để coi là liên tiếp
):
    """
    - Detect bad words bằng faster-whisper.
    - Gộp các từ xấu liên tiếp thành nhóm.
    - Nếu group <= beep_duration → cắt beep để vừa khít group.
    - Nếu group > beep_duration → lặp beep nhiều lần để che hết group.
    """
    # Load audio bằng pydub
    audio = AudioSegment.from_file(input_audio_path)
    sample_rate = audio.frame_rate
    print(f"Loaded audio: {input_audio_path}, Duration: {len(audio)/1000:.2f}s, Sample Rate: {sample_rate}Hz")
    # Transcribe với word timestamps
    segments, info = model.transcribe(
        input_audio_path,
        word_timestamps=True,
        language="en"  # Thay "vi" nếu cần
    )
    
    # Thu thập tất cả bad word timestamps (start, end)
    bad_timestamps = []
    for segment in segments:
        for word_info in segment.words:
            word = word_info.word.strip().lower().rstrip('.,!?')
            print(f"Word: '{word}' at {word_info.start:.2f}s - {word_info.end:.2f}s")
            if word in bad_words or any(bw in word for bw in bad_words):
                bad_timestamps.append((word_info.start, word_info.end))
                print(f"Detected: '{word}' at {word_info.start:.2f}s - {word_info.end:.2f}s")

    if not bad_timestamps:
        print("No bad words detected.")
        audio.export(output_audio_path, format="wav")
        return

    # Sắp xếp timestamps
    bad_timestamps.sort(key=lambda x: x[0])

    # Gộp các từ liên tiếp thành nhóm
    merged_groups = []
    current_start = bad_timestamps[0][0]
    current_end = bad_timestamps[0][1]

    for start, end in bad_timestamps[1:]:
        if start - current_end <= min_gap_sec:  # Liên tiếp hoặc gần liên tiếp
            current_end = max(current_end, end)
        else:
            merged_groups.append((current_start, current_end))
            current_start = start
            current_end = end

    merged_groups.append((current_start, current_end))

    # Load beep
    beep = AudioSegment.from_file(beep_path)
    beep_duration_ms = len(beep)  # Độ dài file beep gốc (ms)

    print(f"Beep file duration: {beep_duration_ms / 1000:.2f} seconds")

    # Chèn beep vào audio
    censored_audio = audio
    offset_ms = 0

    for group_start_sec, group_end_sec in sorted(merged_groups, reverse=True):
        group_start_ms = int(group_start_sec * 1000) + offset_ms
        group_end_ms = int(group_end_sec * 1000) + offset_ms

        group_duration_ms = group_end_ms - group_start_ms

        if group_duration_ms <= beep_duration_ms:
            # Nhóm ngắn hơn hoặc bằng → cắt beep để vừa khít
            beep_segment = beep[:group_duration_ms]
        else:
            # Nhóm dài hơn → lặp beep đủ để che hết (hoặc gần hết)
            repeats = group_duration_ms // beep_duration_ms
            remainder_ms = group_duration_ms % beep_duration_ms

            beep_segment = beep * repeats

            if remainder_ms > 0:
                # Thêm phần dư để che gần hết group
                beep_segment += beep[:remainder_ms]

        # Thay thế phần audio bằng beep_segment
        before = censored_audio[:group_start_ms]
        after = censored_audio[group_start_ms + len(beep_segment):]

        censored_audio = before + beep_segment + after

        # Cập nhật offset
        offset_ms += len(beep_segment) - group_duration_ms

    # Export
    censored_audio.export(output_audio_path, format="wav")
    print(f"Censored audio saved to: {output_audio_path}")

# Ví dụ sử dụng
input_file = "your_audio.wav"
output_file = "censored_output.wav"
beep_file = "beep.wav"  # File beep của bạn

censor_audio_with_beep(
    input_file,
    output_file,
    beep_path=beep_file,
    min_gap_sec=0.1
)