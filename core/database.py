"""SQLite persistence: access-control allowlist, download logs and stats.

Every query is parameterized — never build SQL with f-strings here. One
connection per call keeps things simple and is plenty at family scale."""

import sqlite3

from config.settings import DB_PATH


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS allowed_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS download_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            url TEXT,
            platform TEXT,
            download_type TEXT,
            quality TEXT,
            status TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES allowed_users(user_id)
        )
    ''')

    conn.commit()
    conn.close()


def add_user(user_id: int, username: str = None, first_name: str = None, added_by: int = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO allowed_users (user_id, username, first_name, added_by)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, added_by))
    conn.commit()
    conn.close()


def remove_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM allowed_users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()


def is_user_allowed(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM allowed_users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone() is not None
    conn.close()
    return result


def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name, added_at FROM allowed_users')
    users = cursor.fetchall()
    conn.close()
    return users


def log_download(user_id: int, url: str, platform: str, download_type: str, quality: str, status: str, error_message: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO download_logs (user_id, url, platform, download_type, quality, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, url, platform, download_type, quality, status, error_message))
    conn.commit()
    conn.close()


def get_download_logs(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            dl.id,
            dl.user_id,
            u.username,
            u.first_name,
            dl.url,
            dl.platform,
            dl.download_type,
            dl.quality,
            dl.status,
            dl.error_message,
            dl.created_at
        FROM download_logs dl
        LEFT JOIN allowed_users u ON dl.user_id = u.user_id
        ORDER BY dl.created_at DESC
        LIMIT ?
    ''', (limit,))
    logs = cursor.fetchall()
    conn.close()
    return logs


def get_user_download_logs(user_id: int, limit: int = 20):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            id,
            url,
            platform,
            download_type,
            quality,
            status,
            created_at
        FROM download_logs
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    ''', (user_id, limit))
    logs = cursor.fetchall()
    conn.close()
    return logs


def get_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM allowed_users')
    total_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM download_logs')
    total_downloads = cursor.fetchone()[0]

    cursor.execute('''
        SELECT platform, COUNT(*) as count
        FROM download_logs
        GROUP BY platform
        ORDER BY count DESC
    ''')
    platform_stats = cursor.fetchall()

    cursor.execute('''
        SELECT download_type, COUNT(*) as count
        FROM download_logs
        GROUP BY download_type
        ORDER BY count DESC
    ''')
    type_stats = cursor.fetchall()

    conn.close()
    return {
        'total_users': total_users,
        'total_downloads': total_downloads,
        'platform_stats': platform_stats,
        'type_stats': type_stats
    }
