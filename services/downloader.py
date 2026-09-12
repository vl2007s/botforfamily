"""yt-dlp wrapper: locates the binary, builds download/search commands and
post-processes their results.

All commands are argument lists executed without a shell, so user input can
never break out into shell interpretation. Downloads always land inside a
tempfile directory created under DOWNLOAD_DIR by the caller."""

import json
import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


def get_ytdlp_path() -> str:
    """Find a working yt-dlp binary: PATH first, then the current venv, then
    the known production path. Falls back to a bare name and lets the caller
    surface the error."""
    for path in ['yt-dlp', 'yt-dlp.exe']:
        try:
            subprocess.run([path, '--version'], capture_output=True, check=True)
            return path
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    venv_path = os.path.join(os.path.dirname(sys.executable), 'yt-dlp')
    try:
        subprocess.run([venv_path, '--version'], capture_output=True, check=True)
        return venv_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    server_path = '/opt/botforfamily/venv/bin/yt-dlp'
    try:
        subprocess.run([server_path, '--version'], capture_output=True, check=True)
        return server_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return 'yt-dlp'


YTDLP_PATH = get_ytdlp_path()


def search_youtube(query: str, max_results: int = 10):
    """Search YouTube via yt-dlp; return a list of {id,title,duration,uploader,url}."""
    try:
        cmd = [
            YTDLP_PATH,
            '--no-warnings',
            '--dump-json',
            '--flat-playlist',
            '--playlist-end', str(max_results),
            f'ytsearch{max_results}:{query}'
        ]

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if process.returncode != 0:
            logger.error(f"Search error: {process.stderr[:200]}")
            return []

        results = []
        for line in process.stdout.strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                results.append({
                    'id': data.get('id'),
                    'title': data.get('title', 'Без названия'),
                    'duration': data.get('duration', 0),
                    'uploader': data.get('uploader', 'Неизвестно'),
                    'url': f"https://youtube.com/watch?v={data.get('id')}"
                })
            except json.JSONDecodeError:
                continue

        return results
    except subprocess.TimeoutExpired:
        logger.error("Search timeout")
        return []
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


def format_duration(seconds) -> str:
    if not seconds:
        return "?"
    try:
        seconds = int(seconds)
    except (ValueError, TypeError):
        return "?"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes >= 60:
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def build_video_cmd(url: str, quality: str, output_template: str):
    """Assemble the yt-dlp argument list for a video download.

    TikTok needs explicit Referer/User-Agent headers to avoid throttling and
    always uses its single "best" stream (no format merging)."""
    from core.utils import is_tiktok_url

    if quality == 'best':
        format_spec = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    elif quality == '1080':
        format_spec = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]'
    elif quality == '720':
        format_spec = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]'
    elif quality == '480':
        format_spec = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]'
    elif quality == '360':
        format_spec = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]'
    else:
        format_spec = 'best[ext=mp4]/best'

    if is_tiktok_url(url):
        return [
            YTDLP_PATH,
            '--no-warnings',
            '--format', 'best',
            '--output', output_template,
            '--add-header', 'Referer:https://www.tiktok.com/',
            '--add-header', 'User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            url
        ]

    return [
        YTDLP_PATH,
        '--no-warnings',
        '--format', format_spec,
        '--merge-output-format', 'mp4',
        '--output', output_template,
        url
    ]


def build_audio_cmd(url: str, output_template: str):
    """Assemble the yt-dlp argument list for an MP3 (audio-only) download."""
    from core.utils import is_tiktok_url

    cmd = [
        YTDLP_PATH,
        '--no-warnings',
        '--extract-audio',
        '--audio-format', 'mp3',
        '--audio-quality', '0',
        '--output', output_template,
        '--no-post-overwrites',
        '--ignore-errors',
    ]
    if is_tiktok_url(url):
        cmd.extend([
            '--format', 'best[vcodec*=h264]',
            '--add-header', 'Referer:https://www.tiktok.com/',
            '--add-header', 'User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        ])
    cmd.append(url)
    return cmd


def run_yt_dlp(cmd: list, timeout: int = 300):
    """Run a prepared yt-dlp command, capturing output; callers translate errors."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def get_error_message(stderr: str) -> str:
    """Map raw yt-dlp stderr onto short, actionable Russian user messages."""
    if "Sign in to confirm your age" in stderr:
        return "❌ Ошибка: видео имеет возрастное ограничение."
    elif "Private video" in stderr:
        return "❌ Ошибка: это приватное видео."
    elif "Video unavailable" in stderr:
        return "❌ Ошибка: видео недоступно или удалено."
    elif "This video is not available" in stderr:
        return "❌ Ошибка: видео недоступно в твоём регионе."
    elif "HTTP Error 403" in stderr:
        return "❌ Ошибка: доступ запрещён. Попробуй другую ссылку."
    elif "Unable to extract" in stderr:
        return "❌ Ошибка: не удалось извлечь данные. Возможно, ссылка неверная."
    else:
        return f"❌ Ошибка при скачивании:\n{stderr[:500]}"


def find_downloaded_file(tmpdir: str):
    """Return the largest file yt-dlp produced in `tmpdir`, or None.

    Merging formats can leave intermediate fragments behind; the finished
    video/audio is reliably the largest file, so size beats order."""
    candidates = [
        os.path.join(tmpdir, name)
        for name in os.listdir(tmpdir)
        if os.path.isfile(os.path.join(tmpdir, name))
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getsize)


def check_file_size(file_path: str, max_size_mb: int) -> bool:
    file_size = os.path.getsize(file_path)
    max_size = max_size_mb * 1024 * 1024
    return file_size <= max_size
