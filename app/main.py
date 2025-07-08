import base64
import io
import logging
import wave
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from vosk import Model, KaldiRecognizer
import json
import time

# Initialize FastAPI app
app = FastAPI(title="VOSK Subtitle Service")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load VOSK model (small model for faster processing)
model = Model("model")  # Assumes model is in ./model directory
SAMPLE_RATE = 16000  # Match TTSService output

class AudioInput(BaseModel):
    audio: str  # Base64-encoded WAV audio

def generate_srt(results: list, duration: float) -> str:
    """Convert VOSK results to SRT format."""
    srt_lines = []
    for i, res in enumerate(results, 1):
        if "result" not in res:
            continue
        start = res["result"][0]["start"]
        end = res["result"][-1]["end"]
        text = " ".join(word["word"] for word in res["result"]).capitalize()
        if not text:
            continue
        # Format SRT timestamp: 00:00:01,000 --> 00:00:02,500
        start_srt = f"{int(start // 3600):02d}:{int(start % 3600 // 60):02d}:{int(start % 60):02d},{int((start % 1) * 1000):03d}"
        end_srt = f"{int(end // 3600):02d}:{int(end % 3600 // 60):02d}:{int(end % 60):02d},{int((end % 1) * 1000):03d}"
        srt_lines.append(f"{i}\n{start_srt} --> {end_srt}\n{text}\n")
    return "\n".join(srt_lines) if srt_lines else "1\n00:00:00,000 --> 00:00:01,000\nNo speech detected\n"

@app.post("/subtitles")
async def generate_subtitles(audio_input: AudioInput):
    """Generate SRT subtitles from base64-encoded WAV audio."""
    start_time = time.time()
    logger.info("Received audio for subtitle generation")

    try:
        # Decode base64 audio
        audio_data = base64.b64decode(audio_input.audio)
        audio_io = io.BytesIO(audio_data)

        # Validate WAV format
        with wave.open(audio_io, "rb") as wf:
            if wf.getnchannels() != 1 or wf.getframerate() != SAMPLE_RATE or wf.getsampwidth() != 2:
                logger.error(f"Invalid audio format: channels={wf.getnchannels()}, rate={wf.getframerate()}, width={wf.getsampwidth()}")
                raise HTTPException(status_code=400, detail="Audio must be 16kHz mono WAV with 16-bit samples")
            audio_duration = wf.getnframes() / wf.getframerate()

        # Reset audio_io for VOSK
        audio_io.seek(0)
        recognizer = KaldiRecognizer(model, SAMPLE_RATE)
        recognizer.SetWords(True)  # Enable word-level timestamps

        # Process audio
        results = []
        while True:
            data = audio_io.read(4000)
            if not data:
                break
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                results.append(result)

        # Get final result
        final_result = json.loads(recognizer.FinalResult())
        if final_result.get("text"):
            results.append(final_result)

        # Generate SRT
        srt_content = generate_srt(results, audio_duration)
        logger.info(f"Subtitle generation completed in {time.time() - start_time:.2f}s")
        return {"srt": srt_content}
    except Exception as e:
        logger.error(f"Subtitle generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate subtitles: {str(e)}")
