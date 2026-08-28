# Roadmap

Planned improvements that would elevate this project for production-grade portfolio presentation.

## Near term

- [ ] **Unit tests** — database layer, URL utils, Kinopoisk response parsing
- [ ] **Docker** — Dockerfile + docker-compose with volume for SQLite
- [ ] **Type hints** — full coverage + mypy in CI
- [ ] **Ruff** — linting and formatting in GitHub Actions

## Medium term

- [ ] **Async yt-dlp** — non-blocking downloads with asyncio subprocess
- [ ] **Download queue** — prevent concurrent heavy jobs from blocking the bot
- [ ] **Rate limiting** — per-user daily download caps
- [ ] **i18n** — English/Russian message bundles

## Long term

- [ ] **PostgreSQL** — migrate from SQLite for multi-instance deployment
- [ ] **Webhook mode** — replace polling for cloud deployment (AWS/GCP)
- [ ] **Admin web dashboard** — FastAPI panel for logs and user management
- [ ] **Observability** — Prometheus metrics, Grafana dashboards

---

Contributions and ideas welcome via [Issues](https://github.com/angereichert/botforfamily/issues).
