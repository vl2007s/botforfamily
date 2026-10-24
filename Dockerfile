FROM python:3.12-slim

WORKDIR /app

# Install ffmpeg/ffprobe so yt-dlp can merge video/audio tracks.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Keep the SQLite database and temporary downloads outside the image.
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/data/users.db
ENV DOWNLOAD_DIR=/tmp/downloads

VOLUME ["/data"]

CMD ["python", "main.py"]
