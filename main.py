import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config.settings import BOT_TOKEN, ADMIN_ID
from core.database import init_db, add_user
from handlers.commands import (
    start, help_command, status_command,
    add_user_command, remove_user_command, users_command,
    logs_command, userlogs_command, broadcast_command,
    handle_url, button_callback
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    init_db()
    add_user(ADMIN_ID, 'admin', 'Administrator')
    logger.info(f"Admin added/updated: {ADMIN_ID}")

    try:
        import subprocess
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
        logger.info("yt-dlp found")
    except (subprocess.CalledProcessError, FileNotFoundError):
        venv_ytdlp = os.path.join(os.path.dirname(sys.executable), 'yt-dlp')
        try:
            subprocess.run([venv_ytdlp, '--version'], capture_output=True, check=True)
            logger.info("yt-dlp found in venv")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("ERROR: yt-dlp not found! Install: pip install yt-dlp")
            return

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .get_updates_connect_timeout(30)
        .get_updates_read_timeout(30)
        .build()
    )

    async def error_handler(update, context):
        logger.error(f"Exception while handling an update: {context.error}")

    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("adduser", add_user_command))
    application.add_handler(CommandHandler("removeuser", remove_user_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CommandHandler("userlogs", userlogs_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot started! Press Ctrl+C to stop.")

    while True:
        try:
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                stop_signals=None,
                close_loop=False
            )
        except Exception as e:
            logger.error(f"Bot crashed with error: {e}. Restarting in 10 seconds...")
            time.sleep(10)
            continue


if __name__ == "__main__":
    main()
