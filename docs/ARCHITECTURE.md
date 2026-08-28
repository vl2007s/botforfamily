# Architecture

## Design goals

BotForFamily was built as a maintainable single-process Python application with clear separation of concerns:

- **handlers** — Telegram I/O, user flows, inline keyboards
- **services** — business logic and external tool/API integration
- **core** — persistence and shared utilities
- **config** — environment-driven settings

## Request flow

### URL download flow

```
User sends URL
    → handlers/commands.handle_url()
    → core/utils.is_valid_url() — platform detection
    → Inline keyboard: video / audio
    → User selects quality (video) or MP3 (audio)
    → services/downloader.build_*_cmd()
    → subprocess: yt-dlp
    → File size check → send via Telegram Bot API
    → core/database.log_download()
```

### Text search flow

```
User sends plain text
    → show_search_menu() — YouTube or Kinopoisk
    → YouTube: services/downloader.search_youtube()
    → Kinopoisk: services/kinopoisk.search_kinopoisk()
    → Paginated inline results (5 per page)
    → User picks item → download or open watch link
```

## Database schema

### `allowed_users`

| Column | Type | Purpose |
|--------|------|---------|
| user_id | INTEGER PK | Telegram user ID |
| username | TEXT | Optional username |
| first_name | TEXT | Display name |
| added_by | INTEGER | Admin who granted access |
| added_at | TIMESTAMP | Auto-set on insert |

### `download_logs`

| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | Who downloaded |
| url | TEXT | Source URL |
| platform | TEXT | YouTube / TikTok |
| download_type | TEXT | video / audio |
| quality | TEXT | e.g. 720, mp3 |
| status | TEXT | success / error |
| error_message | TEXT | Truncated stderr on failure |
| created_at | TIMESTAMP | Auto-set |

## Error handling

- **yt-dlp failures** — stderr parsed into user-friendly Russian messages
- **Large files** — rejected before upload (2 GB video, 50 MB audio limits)
- **Timeouts** — 300s subprocess timeout with graceful user notification
- **Bot crashes** — main loop catches exceptions, waits 10s, restarts polling

## Configuration

All secrets and paths load from environment via `config/settings.py`:

- Missing `BOT_TOKEN` or `ADMIN_ID` → startup fails fast with clear error
- Missing `KINOPOISK_API_KEY` → movie search disabled, other features unaffected

## Deployment notes

Current deployment target: a single VPS or home server running `python main.py` under systemd or screen.

Recommended production hardening (see [ROADMAP.md](ROADMAP.md)):

- Docker containerization
- Structured JSON logging
- Health check endpoint or heartbeat
- Secret management (not flat `.env` on disk)
