# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| main    | ✅        |

## Reporting a vulnerability

This is a personal portfolio / family-use project. If you discover a security issue:

1. **Do not** open a public issue for sensitive vulnerabilities
2. Contact the maintainer via GitHub: [@angereichert](https://github.com/angereichert)

## Security practices in this project

- Secrets loaded from environment variables (`.env`), never committed
- `.gitignore` blocks `.env`, databases, logs, and media files
- User allowlist enforced on every handler
- Admin commands restricted to `ADMIN_ID`

## If you fork this project

- Generate your own bot token via [@BotFather](https://t.me/BotFather)
- Never reuse tokens or API keys from examples
- Keep the bot private — it is not designed for public multi-tenant use
