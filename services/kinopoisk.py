"""Kinopoisk API client: search by keyword and convert Kinopoisk film/series
URLs into fbfind watch links. Degrades gracefully to "no results" on any
error or missing API key — search is a bonus feature, not a hard dependency."""

import logging
import os
import re

import requests

from config.settings import KINOPOISK_API_KEY

logger = logging.getLogger(__name__)

FBFIND_URL = "https://fbfind.top"
KINOPOISK_API_URL = "https://kinopoiskapiunofficial.tech/api/v2.1"


def search_kinopoisk(query: str, max_results: int = 5):
    if not KINOPOISK_API_KEY:
        logger.warning("KINOPOISK_API_KEY is not set, Kinopoisk search disabled")
        return []

    try:
        headers = {
            'X-API-KEY': KINOPOISK_API_KEY,
            'Content-Type': 'application/json',
        }

        params = {
            'keyword': query,
            'page': 1
        }

        response = requests.get(
            f"{KINOPOISK_API_URL}/films/search-by-keyword",
            headers=headers,
            params=params,
            timeout=15
        )

        if response.status_code != 200:
            logger.error(f"Kinopoisk API error: {response.status_code} - {response.text[:200]}")
            return []

        data = response.json()
        films = data.get('films', [])

        results = []
        seen = set()

        for film in films[:max_results]:
            kp_id = film.get('filmId')
            if not kp_id or kp_id in seen:
                continue
            seen.add(kp_id)

            film_type = film.get('type', 'FILM')
            content_type = 'series' if film_type == 'TV_SERIES' else 'film'

            title = film.get('nameRu') or film.get('nameEn', 'Без названия')
            year = str(film.get('year', '')) if film.get('year') else ''
            rating = film.get('rating', '')
            rating_str = f"⭐ {rating}" if rating else ''

            genres = film.get('genres', [])
            genres_str = ', '.join([g.get('genre', '') for g in genres[:3]]) if genres else ''

            kp_url = f"https://www.kinopoisk.ru/{content_type}/{kp_id}/"
            fbfind_url = f"{FBFIND_URL}/{content_type}/{kp_id}/"

            results.append({
                'id': str(kp_id),
                'title': title,
                'type': content_type,
                'year': year,
                'rating': rating_str,
                'genres': genres_str,
                'kp_url': kp_url,
                'url': fbfind_url
            })

        return results

    except requests.Timeout:
        logger.error("Kinopoisk API timeout")
        return []
    except Exception as e:
        logger.error(f"Kinopoisk search error: {e}")
        return []


def get_fbfind_url(kinopoisk_url: str) -> str:
    film_match = re.search(r'kinopoisk\.ru/film/(\d+)', kinopoisk_url)
    series_match = re.search(r'kinopoisk\.ru/series/(\d+)', kinopoisk_url)

    if film_match:
        return f"{FBFIND_URL}/film/{film_match.group(1)}/"

    if series_match:
        return f"{FBFIND_URL}/series/{series_match.group(1)}/"

    return None


def is_kinopoisk_url(url: str) -> bool:
    return 'kinopoisk.ru' in url and ('/film/' in url or '/series/' in url)
