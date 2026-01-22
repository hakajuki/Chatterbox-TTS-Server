# Beep Sync Server

Audio censorship service using Whisper ASR and pydub to detect and beep out profanity in audio files.

## Features

- **Automatic profanity detection** using OpenAI's Whisper model
- **Smart word grouping** to censor consecutive bad words as a single region
- **Web UI** with drag-and-drop file upload
- **REST API** for programmatic access
- **Customizable bad words list** via UI or API
- **Multi-platform support** (CUDA, Apple MPS, CPU)

## Quick Start

### 1. Install Dependencies

```bash
pip install fastapi uvicorn faster-whisper pydub torch
```

For macOS with Apple Silicon:
```bash
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cpu
```

### 2. Generate Beep Sound

```bash
cd ui
python generate_beep.py
```

### 3. Run Server

```bash
cd ui
python beep-server.py
```

Server will start on `http://localhost:8005`

## Usage

### Web UI

1. Open `http://localhost:8005` in your browser
2. (Optional) Enter bad words to censor (comma-separated)
3. Upload or drag-and-drop an audio file
4. Click "Censor Audio"
5. Download the censored result

### API

**Endpoint:** `POST /api/censor`

**Parameters:**
- `audio_file` (file): Audio file to censor (.wav, .mp3, .m4a, .flac, .ogg)
- `bad_words` (form field): Comma-separated list of words to censor

**Example with curl:**

```bash
curl -X POST http://localhost:8005/api/censor \
  -F "audio_file=@your_audio.wav" \
  -F "bad_words=fuck,shit,damn" \
  -o censored_output.wav
```

**Response:** Censored audio file (WAV format) with headers:
- `X-Detected-Count`: Number of bad words detected
- `X-Groups-Censored`: Number of audio regions censored
- `X-Detected-Words`: Comma-separated list of detected words

### Python API Client

```python
import requests

url = "http://localhost:8005/api/censor"

with open("your_audio.wav", "rb") as f:
    files = {"audio_file": f}
    data = {"bad_words": "fuck,shit,damn,bitch"}
    
    response = requests.post(url, files=files, data=data)
    
    if response.ok:
        with open("censored.wav", "wb") as out:
            out.write(response.content)
        print(f"Detected: {response.headers.get('X-Detected-Count')} bad words")
    else:
        print(f"Error: {response.status_code}")
```

## Configuration

### Default Bad Words

The server includes a default list of English profanity. You can:
- Override via UI textarea
- Override via API `bad_words` parameter
- Edit `DEFAULT_BAD_WORDS` in `beep-server.py`

### Whisper Model

Default: `small.en` (fast, English-only)

To change model, edit `DEFAULT_MODEL_SIZE` in `beep-server.py`:
- `tiny.en`, `base.en`, `small.en` - Fast, English-only
- `medium`, `large-v3` - Slower, multilingual

### Beep Sound

Default beep: `ui/beep.wav` (1kHz sine wave, 200ms)

To customize:
- Replace `ui/beep.wav` with your own beep sound
- Or edit `generate_beep.py` and regenerate

### Server Port

Default: `8005`

To change, edit `port` in the `if __name__ == "__main__"` block of `beep-server.py`.

## How It Works

1. **Transcription**: Whisper ASR transcribes audio with word-level timestamps
2. **Detection**: Compares transcribed words against bad words list
3. **Grouping**: Merges consecutive bad words (< 100ms apart) into regions
4. **Replacement**: Replaces each region with beep audio (repeated if necessary)
5. **Export**: Returns censored audio as WAV file

## Troubleshooting

### "Beep file not found"
Run `python ui/generate_beep.py` to create the beep sound.

### "No module named 'faster_whisper'"
Install dependencies: `pip install faster-whisper pydub torch`

### Slow performance
- Use a smaller Whisper model (`tiny.en` or `base.en`)
- Ensure GPU acceleration is working (check server logs for `device=cuda` or `device=mps`)

### GPU not detected
- **NVIDIA**: Install CUDA toolkit and `torch` with CUDA support
- **Apple Silicon**: Install PyTorch nightly with MPS support
- Fallback to CPU (slower but works everywhere)

## API Documentation

Full interactive API docs available at `http://localhost:8005/docs` when server is running.

## License

MIT License - see parent project LICENSE file.

## Credits

- Powered by [faster-whisper](https://github.com/guillaumekln/faster-whisper)
- Uses [pydub](https://github.com/jiaaro/pydub) for audio manipulation
- Based on [Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server) architecture
