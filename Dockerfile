FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download and extract VOSK model
RUN mkdir -p model && \
    wget -q https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip || \
    { echo "Failed to download VOSK model"; exit 1; } && \
    unzip vosk-model-small-en-us-0.15.zip && \
    mv vosk-model-small-en-us-0.15 model && \
    rm vosk-model-small-en-us-0.15.zip || \
    { echo "Failed to process VOSK model"; exit 1; }

# Copy application code
COPY app /app

# Run FastAPI with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
