# 1. Use Python 3.10 slim as base
FROM python:3.10-slim

# 2. Install system-level dependencies
# Added libmagic1 and ffmpeg which are required for media processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    libmagic1 \
    build-essential \
    python3-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. Set working directory
WORKDIR /app

# 4. Copy and install Python dependencies
COPY requirements.txt .

# Upgrade pip and install requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your project files
COPY . .

# 6. CRITICAL: Force moviepy/imageio to use the system FFmpeg
# This removes the "Warning: imageio-ffmpeg not installed" message
ENV IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg

# 7. Start the bot
CMD ["python", "main.py"]
