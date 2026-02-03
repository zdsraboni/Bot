# 1. Use Python 3.10 slim as base
FROM python:3.10-slim

# আউটপুট বাফারিং বন্ধ করা (লগ সাথে সাথে দেখার জন্য)
ENV PYTHONUNBUFFERED=1

# 2. Install system-level dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    libmagic1 \
    build-essential \
    python3-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. Set working directory
WORKDIR /app

# 4. Copy requirements file FIRST
COPY requirements.txt .

# 5. Force Install Dependencies (Cache Breaking)
# --force-reinstall ফ্ল্যাগ ব্যবহার করা হয়েছে যাতে সে ক্যাশ ব্যবহার না করে নতুন করে নামায়
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --force-reinstall -r requirements.txt

# 6. DEBUG: বিল্ড লগে চেক করা যে Telethon আসলে ইনস্টল হয়েছে কি না
RUN pip list | grep telethon || echo "❌ Telethon NOT installed!"

# 7. Copy the rest of your project files
COPY . .

# 8. Set FFmpeg path
ENV IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg

# 9. Start the bot
CMD ["python", "main.py"]
