"""URL validation and platform detection.

All checks are pure string/parsing operations — nothing here fetches the URL.
Validation is hostname-based (not regex-over-the-whole-string) so lookalike
hosts such as "youtube.com.evil.example" or "notyoutube.com" are rejected
before the URL ever reaches yt-dlp."""

import re
from urllib.parse import urlparse


def _hostname(url: str) -> str:
    """Lowercase hostname of the URL; tolerates URLs written without a scheme."""
    if "://" not in url:
        url = "//" + url  # urlparse only fills .hostname when a netloc marker exists
    host = urlparse(url).hostname
    return host.lower() if host else ""


def is_youtube_url(url: str) -> bool:
    host = _hostname(url)
    return (
        host == "youtube.com" or host.endswith(".youtube.com")
        or host == "youtu.be"
        or host == "youtube-nocookie.com" or host.endswith(".youtube-nocookie.com")
    )


def is_tiktok_url(url: str) -> bool:
    host = _hostname(url)
    return host == "tiktok.com" or host.endswith(".tiktok.com")


def is_valid_url(url: str) -> bool:
    """Only YouTube/TikTok links are downloadable — everything else is search text."""
    return is_youtube_url(url) or is_tiktok_url(url)


def get_platform(url: str) -> str:
    if is_youtube_url(url):
        return "YouTube"
    elif is_tiktok_url(url):
        return "TikTok"
    return "Unknown"


# Matches any absolute http(s) link in free text — used to tell the user
# "I can only download from YouTube/TikTok" instead of treating it as a search query.
URL_PATTERN = re.compile(r'https?://\S+')


def contains_url(text: str) -> bool:
    return bool(URL_PATTERN.search(text))
