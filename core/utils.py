import re

YOUTUBE_PATTERN = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+')
TIKTOK_PATTERN = re.compile(r'(https?://)?(www\.)?(tiktok|vt\.tiktok|vm\.tiktok)\.(com)/.+')


def is_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_PATTERN.match(url))


def is_tiktok_url(url: str) -> bool:
    return bool(TIKTOK_PATTERN.match(url))


def is_valid_url(url: str) -> bool:
    return is_youtube_url(url) or is_tiktok_url(url)


def get_platform(url: str) -> str:
    if is_youtube_url(url):
        return "YouTube"
    elif is_tiktok_url(url):
        return "TikTok"
    return "Unknown"


URL_PATTERN = re.compile(r'https?://\S+')


def contains_url(text: str) -> bool:
    return bool(URL_PATTERN.search(text))
