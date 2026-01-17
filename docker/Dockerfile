FROM python:3.11-slim

WORKDIR /app

# System dependencies for OpenCV and video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code and tools
COPY app/ app/
COPY tools/ tools/

# Create data directories
RUN mkdir -p data/weights data/videos data/config data/output data/db data/thumbnails

# Copy default config
COPY data/config/ data/config/

# Pre-download assets during build (turnkey!)
RUN python tools/download_assets.py

# Set environment
ENV PYTHONUNBUFFERED=1
ENV DOCKER_CONTAINER=1

EXPOSE 8123

# Use uvicorn for FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8123"]
