"""Telegram handlers: commands, inline keyboards, search flows and downloads.

User-facing strings intentionally stay in Russian (the bot's audience is the
author's family); docstrings and comments are English for maintainers.

Conversation state between callbacks lives in `context.user_data` — PTB gives
each chat its own dict, so keys like 'url' / 'search_results' are per-user."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.database import is_user_allowed, log_download, get_download_logs, get_user_download_logs
from core.utils import is_valid_url, get_platform
from services.downloader import (
    build_video_cmd, build_audio_cmd, run_yt_dlp, get_error_message,
    find_downloaded_file, check_file_size, search_youtube, format_duration
)
from services.kinopoisk import search_kinopoisk
from config.settings import DOWNLOAD_DIR, ADMIN_ID
import tempfile
import os
import subprocess
import logging
from logging.handlers import RotatingFileHandler

# File + console logging. The file rotates at 5 MB (keeps 3 backups) — a plain
# FileHandler let bot.log grow past 30 MB on the production server.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('bot.log', maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ========== КОМАНДЫ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Проверяем доступ
    if not is_user_allowed(user.id):
        await update.message.reply_text(
            "⛔ У тебя нет доступа к этому боту.\n\n"
            "🔑 Обратись к администратору, чтобы получить разрешение."
        )
        return
    
    await update.message.reply_text(
        "👋 Привет! Я бот для скачивания видео.\n\n"
        "🎬 *Как пользоваться — пошагово:*\n\n"
        "1️⃣ *Найди видео*, которое хочешь скачать\n"
        "   • В YouTube или TikTok\n\n"
        "2️⃣ *Скопируй ссылку* на это видео\n"
        "   • В YouTube: нажми «Поделиться» → «Копировать ссылку»\n"
        "   • В TikTok: нажми «Поделиться» → «Копировать ссылку»\n\n"
        "3️⃣ *Отправь ссылку* мне в этот чат\n\n"
        "4️⃣ *Выбери*, что скачать:\n"
        "   • 🎬 Видео — смотреть офлайн\n"
        "   • 🎵 Только звук (MP3) — слушать музыку\n\n"
        "5️⃣ Если выбрал видео — *выбери качество*:\n"
        "   • 🔥 Лучшее — максимальное качество\n"
        "   • 📺 1080p — очень чёткое\n"
        "   • 📺 720p — хорошее (рекомендую)\n"
        "   • 📺 480p — среднее\n"
        "   • 📺 360p — компактное, быстрее грузится\n\n"
        "6️⃣ *Жди* — бот скачает и пришлёт файл\n\n"
        "⚠️ *Важно:*\n"
        "• TikTok видео приходят *без водяного знака*\n"
        "• Очень большие видео могут не отправиться\n"
        "• Некоторые приватные видео недоступны\n\n"
        "📖 Команды:\n"
        "/help — подробная помощь\n"
        "/status — мой статус\n"
        "🎬 Или просто напиши название фильма — я найду ссылку для просмотра!",
        parse_mode='Markdown'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_user_allowed(user.id):
        await update.message.reply_text(
            "⛔ У тебя нет доступа к этому боту.\n\n"
            "🔑 Обратись к администратору, чтобы получить разрешение."
        )
        return
    
    await update.message.reply_text(
        "📖 *ПОДРОБНАЯ ИНСТРУКЦИЯ*\n\n"
        "*Как скопировать ссылку в YouTube:*\n"
        "1. Открой приложение YouTube или сайт youtube.com\n"
        "2. Найди нужное видео\n"
        "3. Нажми на кнопку «Поделиться» (стрелочка внизу)\n"
        "4. Выбери «Копировать ссылку»\n"
        "5. Вернись в Telegram и вставь ссылку сюда\n\n"
        "*Как скопировать ссылку в TikTok:*\n"
        "1. Открой приложение TikTok\n"
        "2. Найди нужное видео\n"
        "3. Нажми на кнопку «Поделиться» (стрелочка справа)\n"
        "4. Нажми «Копировать ссылку»\n"
        "5. Вернись в Telegram и вставь ссылку сюда\n\n"
        "*Что делать, если бот не отвечает:*\n"
        "• Проверь, правильная ли ссылка\n"
        "• Подожди 1-2 минуты — скачивание может занять время\n"
        "• Если долго ничего не происходит — напиши /start и попробуй снова\n\n"
        "*Поиск фильмов и сериалов:*\n"
        "• Просто напиши название фильма — бот найдёт ссылку для просмотра\n"
        "• Работает через Кинопоиск — показывает рейтинг и год\n"
        "• Ссылка ведёт на сайт для онлайн-просмотра\n\n"
        "*Ограничения:*\n"
        "• Максимальный размер видео: ~2 ГБ\n"
        "• Видео с возрастным ограничением не скачиваются\n"
        "• Приватные видео недоступны\n"
        "• Некоторые музыкальные клипы могут быть заблокированы\n\n"
        "*Совет:* Для экономии трафика выбирай качество 720p или ниже.",
        parse_mode='Markdown'
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_user_allowed(user.id):
        await update.message.reply_text(
            "⛔ У тебя нет доступа к этому боту.\n\n"
            "🔑 Обратись к администратору, чтобы получить разрешение."
        )
        return
    
    is_admin = user.id == ADMIN_ID
    
    if is_admin:
        from core.database import get_stats
        stats = get_stats()
        
        platform_text = "\n".join([f"• {p}: {c}" for p, c in stats['platform_stats']]) if stats['platform_stats'] else "• Нет данных"
        type_text = "\n".join([f"• {t}: {c}" for t, c in stats['type_stats']]) if stats['type_stats'] else "• Нет данных"
        
        await update.message.reply_text(
            f"📊 *Статус бота*\n\n"
            f"👤 Пользователей: {stats['total_users']}\n"
            f"📥 Всего скачиваний: {stats['total_downloads']}\n\n"
            f"📱 По платформам:\n{platform_text}\n\n"
            f"📦 По типу:\n{type_text}\n\n"
            f"🔑 Ты — администратор\n"
            f"⚙️ Команды админа: /adduser, /removeuser, /users",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "✅ Бот работает нормально.\n\n"
            "🎬 Просто отправь ссылку на видео, и я его скачаю!"
        )


# ========== АДМИН КОМАНДЫ ==========

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ Только администратор может добавлять пользователей.\n\n"
            "🔑 У тебя нет прав."
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "ℹ️ Использование: /adduser <user_id> [имя]\n\n"
            "🆔 Как узнать ID пользователя:\n"
            "1. Попроси человека написать боту @userinfobot\n"
            "2. Он пришлёт тебе свой ID\n"
            "3. Используй команду: /adduser 123456789 Иван"
        )
        return
    
    try:
        new_user_id = int(context.args[0])
        name = context.args[1] if len(context.args) > 1 else None
        
        from core.database import add_user
        add_user(new_user_id, name, name, user.id)
        
        await update.message.reply_text(
            f"✅ Пользователь добавлен!\n"
            f"🆔 ID: {new_user_id}\n"
            f"👤 Имя: {name or 'Не указано'}\n\n"
            f"🎉 Теперь он может пользоваться ботом."
        )
    except ValueError:
        await update.message.reply_text(
            "❌ ID должен быть числом.\n\n"
            "💡 Пример: /adduser 123456789"
        )


async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ Только администратор может удалять пользователей.\n\n"
            "🔑 У тебя нет прав."
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "ℹ️ Использование: /removeuser <user_id>\n\n"
            "🆔 ID можно узнать командой /users"
        )
        return
    
    try:
        remove_id = int(context.args[0])
        
        if remove_id == ADMIN_ID:
            await update.message.reply_text(
                "❌ Нельзя удалить самого себя!\n\n"
                "🛡️ Это защита от случайного удаления."
            )
            return
        
        from core.database import remove_user
        remove_user(remove_id)
        
        await update.message.reply_text(
            f"✅ Пользователь {remove_id} удалён.\n\n"
            f"🗑️ Он больше не может пользоваться ботом."
        )
    except ValueError:
        await update.message.reply_text(
            "❌ ID должен быть числом.\n\n"
            "💡 Пример: /removeuser 123456789"
        )


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ Только администратор может смотреть список пользователей.\n\n"
            "🔑 У тебя нет прав."
        )
        return
    
    from core.database import get_all_users
    users = get_all_users()
    
    if not users:
        await update.message.reply_text(
            "📋 Список пользователей пуст.\n\n"
            "💡 Добавь первого: /adduser <id> [имя]"
        )
        return
    
    text = "📋 Список пользователей:\n\n"
    for uid, username, first_name, added_at in users:
        name = first_name or username or "Без имени"
        # plain text on purpose: names are user-controlled and would break
        # (or inject into) Markdown formatting
        text += f"• {uid} — {name}\n"

    text += f"\n👥 Всего: {len(users)} пользователей"

    await update.message.reply_text(text)


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает логи скачиваний (только админ)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ Только администратор может смотреть логи.\n\n"
            "🔑 У тебя нет прав."
        )
        return
    
    limit = 20
    if context.args and context.args[0].isdigit():
        limit = min(int(context.args[0]), 50)
    
    logs = get_download_logs(limit=limit)
    
    if not logs:
        await update.message.reply_text("📋 Логи пусты. Пока никто ничего не качал.")
        return
    
    text = f"📊 *Последние {len(logs)} скачиваний:*\n\n"
    
    for log in logs:
        log_id, uid, username, first_name, url, platform, dl_type, quality, status, error, created_at = log
        name = first_name or username or f"ID:{uid}"
        status_emoji = "✅" if status == "success" else "❌"

        # keep the message well under Telegram's 4096-char limit
        short_url = url if len(url) <= 80 else url[:77] + "..."
        
        text += (
            f"{status_emoji} *{name}*\n"
            f"   📎 `{short_url}`\n"
            f"   📱 {platform} | 🎬 {dl_type} | ⚙️ {quality}\n"
            f"   🕐 {created_at}\n\n"
        )
    
    await update.message.reply_text(text, parse_mode='Markdown')


async def userlogs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает логи конкретного пользователя (только админ)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ Только администратор может смотреть логи.\n\n"
            "🔑 У тебя нет прав."
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "ℹ️ Использование: /userlogs <user_id>\n\n"
            "💡 ID можно узнать командой /users"
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом.")
        return
    
    logs = get_user_download_logs(target_id, limit=20)
    
    if not logs:
        await update.message.reply_text(f"📋 Пользователь `{target_id}` пока ничего не качал.", parse_mode='Markdown')
        return
    
    text = f"📊 *Скачивания пользователя `{target_id}`:*\n\n"
    
    for log in logs:
        log_id, url, platform, dl_type, quality, status, created_at = log
        status_emoji = "✅" if status == "success" else "❌"
        short_url = url
        
        text += (
            f"{status_emoji} `{short_url}`\n"
            f"   📱 {platform} | 🎬 {dl_type} | ⚙️ {quality}\n"
            f"   🕐 {created_at}\n\n"
        )
    
    await update.message.reply_text(text, parse_mode='Markdown')


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение всем пользователям (только админ)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ Только администратор может отправлять уведомления.\n\n"
            "🔑 У тебя нет прав."
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            "ℹ️ Использование: /broadcast <текст сообщения>\n\n"
            "💡 Пример: /broadcast Привет всем! Бот обновлён.\n\n"
            "📢 Сообщение отправится всем пользователям из базы."
        )
        return
    
    message = ' '.join(context.args)
    
    from core.database import get_all_users
    users = get_all_users()
    
    if not users:
        await update.message.reply_text("📋 Нет пользователей для отправки.")
        return
    
    sent = 0
    failed = 0
    
    await update.message.reply_text(
        f"📢 Начинаю отправку сообщения {len(users)} пользователям...\n\n"
        f"💬 Текст: {message[:100]}"
    )
    
    for uid, username, first_name, added_at in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 *Сообщение от администратора:*\n\n{message}",
                parse_mode='Markdown'
            )
            sent += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {uid}: {e}")
            failed += 1
    
    await update.message.reply_text(
        f"✅ Рассылка завершена!\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}\n"
        f"👥 Всего: {len(users)}"
    )


# ========== ОБРАБОТКА ССЫЛОК ==========

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_user_allowed(user.id):
        await update.message.reply_text(
            "⛔ У тебя нет доступа к этому боту.\n\n"
            "🔑 Обратись к администратору, чтобы получить разрешение."
        )
        return
    
    text = update.message.text.strip()
    
    # Если это ссылка на Кинопоиск — конвертируем в fbfind
    from services.kinopoisk import is_kinopoisk_url, get_fbfind_url
    if is_kinopoisk_url(text):
        fbfind_url = get_fbfind_url(text)
        if fbfind_url:
            keyboard = [
                [InlineKeyboardButton("🎬 Открыть фильм", url=fbfind_url)],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🎬 Найден фильм на Кинопоиске!\n\n"
                f"🔗 Ссылка для просмотра:\n{fbfind_url}\n\n"
                f"👆 Нажми кнопку ниже или открой ссылку",
                reply_markup=reply_markup
            )
            return
    
    # Если это ссылка YouTube/TikTok — обрабатываем как раньше
    if is_valid_url(text):
        context.user_data['url'] = text
        platform = get_platform(text)
        
        keyboard = [
            [InlineKeyboardButton("🎬 Видео", callback_data='video')],
            [InlineKeyboardButton("🎵 Только звук (MP3)", callback_data='audio')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Найдено видео с *{platform}*!\n\n"
            f"🤔 Что хочешь скачать?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Если текст содержит любой URL (не YouTube/TikTok) — предупреждаем
    from core.utils import contains_url
    if contains_url(text):
        await update.message.reply_text(
            "⚠️ Это ссылка, но я пока умею скачивать только с *YouTube* и *TikTok*.\n\n"
            "💡 Попробуй отправить ссылку с этих платформ.",
            parse_mode='Markdown'
        )
        return
    
    # Если это текст (не ссылка) — показываем меню выбора поиска
    await show_search_menu(update, context, text)


async def show_search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Показывает меню выбора: искать на YouTube или Кинопоиске."""
    user = update.effective_user
    
    context.user_data['search_query'] = query
    
    keyboard = [
        [InlineKeyboardButton("🎵 YouTube (музыка/видео)", callback_data='search_youtube')],
        [InlineKeyboardButton("🎬 Кинопоиск (фильмы/сериалы)", callback_data='search_kinopoisk')],
        [InlineKeyboardButton("❌ Отмена", callback_data='search_cancel')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔍 Что ищем: «{query}»\n\n"
        f"Выбери, где искать:",
        reply_markup=reply_markup
    )


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Обрабатывает поиск по названию песни/видео."""
    user = update.effective_user
    
    # Ищем 10 результатов для большего выбора
    results = search_youtube(query, max_results=10)
    
    if not results:
        text = (
            "❌ Ничего не найдено.\n\n"
            "💡 Попробуй:\n"
            "• Уточнить название\n"
            "• Добавить исполнителя\n"
            "• Использовать английское название\n"
            "• Проверить правописание"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return
    
    # Сохраняем результаты поиска
    context.user_data['search_results'] = results
    context.user_data['search_query'] = query  # Сохраняем запрос для повторного поиска
    context.user_data['search_type'] = 'youtube'
    
    # Показываем первые 5 результатов на первой странице
    await show_search_results(update, context, page=0)


async def handle_kinopoisk_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Обрабатывает поиск фильмов/сериалов на Кинопоиске."""
    # Определяем, это callback или сообщение
    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"🎬 Ищу «{query}» на Кинопоиске...\n"
            f"⏳ Это займёт секунду..."
        )
    else:
        await update.message.reply_text(
            f"🎬 Ищу «{query}» на Кинопоиске...\n"
            f"⏳ Это займёт секунду..."
        )
    
    results = search_kinopoisk(query, max_results=10)
    
    if not results:
        text = (
            "❌ Ничего не найдено на Кинопоиске.\n\n"
            "💡 Попробуй:\n"
            "• Уточнить название фильма\n"
            "• Добавить год (например: мстители 2012)\n"
            "• Использовать оригинальное название\n"
            "• Проверить правописание"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return
    
    # Сохраняем результаты
    context.user_data['search_results'] = results
    context.user_data['search_query'] = query
    context.user_data['search_type'] = 'kinopoisk'
    
    # Показываем результаты
    await show_kinopoisk_results(update, context, page=0)


async def show_kinopoisk_results(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Показывает страницу результатов поиска Кинопоиска."""
    results = context.user_data.get('search_results', [])
    query = context.user_data.get('search_query', '')
    
    if not results:
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Результаты поиска устарели. Попробуй найти заново.")
        else:
            await update.message.reply_text("❌ Результаты поиска устарели. Попробуй найти заново.")
        return
    
    # Пагинация: 5 результатов на страницу
    per_page = 5
    total_pages = (len(results) + per_page - 1) // per_page
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(results))
    page_results = results[start_idx:end_idx]
    
    # Формируем клавиатуру с результатами
    keyboard = []
    for i, result in enumerate(page_results):
        idx = start_idx + i
        year = f" ({result['year']})" if result['year'] else ''
        rating = f" {result['rating']}" if result['rating'] else ''
        title = result['title'][:30] + '...' if len(result['title']) > 30 else result['title']
        keyboard.append([
            InlineKeyboardButton(
                f"{idx+1}. {title}{year}{rating}",
                callback_data=f'kinopoisk_{idx}'
            )
        ])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f'kinopoisk_page_{page-1}'))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f'kinopoisk_page_{page+1}'))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопки действий
    keyboard.append([
        InlineKeyboardButton("🔍 Искать другое", callback_data='search_new'),
        InlineKeyboardButton("🎵 Искать на YouTube", callback_data='search_youtube_again')
    ])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data='search_cancel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🎬 Результаты поиска «{query}»\n"
        f"📄 Страница {page+1} из {total_pages} (всего {len(results)})\n\n"
        f"Выбери фильм или сериал:"
    )
    
    # Если это callback (перелистывание), редактируем сообщение
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)



async def show_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Показывает страницу результатов поиска."""
    results = context.user_data.get('search_results', [])
    query = context.user_data.get('search_query', '')
    
    if not results:
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Результаты поиска устарели. Попробуй найти заново.")
        else:
            await update.message.reply_text("❌ Результаты поиска устарели. Попробуй найти заново.")
        return
    
    # Пагинация: 5 результатов на страницу
    per_page = 5
    total_pages = (len(results) + per_page - 1) // per_page
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(results))
    page_results = results[start_idx:end_idx]
    
    # Формируем клавиатуру с результатами
    keyboard = []
    for i, result in enumerate(page_results):
        idx = start_idx + i
        duration = format_duration(result['duration'])
        title = result['title'][:35] + '...' if len(result['title']) > 35 else result['title']
        keyboard.append([
            InlineKeyboardButton(
                f"{idx+1}. {title} ({duration})",
                callback_data=f'search_{idx}'
            )
        ])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f'search_page_{page-1}'))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f'search_page_{page+1}'))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопка нового поиска и отмены
    keyboard.append([
        InlineKeyboardButton("🔍 Искать другое", callback_data='search_new'),
        InlineKeyboardButton("❌ Отмена", callback_data='search_cancel')
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🎵 Результаты поиска «{query}»\n"
        f"📄 Страница {page+1} из {total_pages} (всего {len(results)})\n\n"
        f"Выбери, что скачать:"
    )
    
    # Если это callback (перелистывание), редактируем сообщение
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        # Редактируем сообщение "Ищу..." вместо отправки нового
        msg_id = context.user_data.get('search_message_id')
        if msg_id:
            try:
                await context.bot.edit_message_text(
                    text,
                    chat_id=update.effective_chat.id,
                    message_id=msg_id,
                    reply_markup=reply_markup
                )
            except Exception:
                await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)



# ========== CALLBACKS ==========

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    url = context.user_data.get('url')
    user = update.effective_user
    
    # Обработка поиска (search_* callback) — url может быть только что сохранён
    if choice.startswith('search_'):
        if choice == 'search_cancel':
            await query.edit_message_text("❌ Поиск отменён.")
            return
        
        if choice == 'search_new':
            # Запрашиваем новый поиск
            await query.edit_message_text(
                "🔍 Введи новый запрос для поиска:\n\n"
                "💡 Напиши название песни, видео или фильма"
            )
            return
        
        if choice == 'search_youtube':
            # Поиск на YouTube
            search_query = context.user_data.get('search_query', '')
            if not search_query:
                await query.edit_message_text("❌ Ошибка: запрос не найден.")
                return
            # handle_search вызывает update.message.reply_text, но у нас callback_query
            # Отправляем новое сообщение через effective_chat
            await update.effective_chat.send_message(
                f"🔍 Ищу «{search_query}» на YouTube...\n"
                f"⏳ Это займёт секунду..."
            )
            # Ищем результаты
            results = search_youtube(search_query, max_results=10)
            if not results:
                await update.effective_chat.send_message(
                    "❌ Ничего не найдено.\n\n"
                    "💡 Попробуй:\n"
                    "• Уточнить название\n"
                    "• Добавить исполнителя\n"
                    "• Использовать английское название\n"
                    "• Проверить правописание"
                )
                return
            context.user_data['search_results'] = results
            context.user_data['search_query'] = search_query
            context.user_data['search_type'] = 'youtube'
            await show_search_results(update, context, page=0)
            return
        
        if choice == 'search_youtube_again':
            # Поиск на YouTube (из Кинопоиска)
            search_query = context.user_data.get('search_query', '')
            if not search_query:
                await query.edit_message_text("❌ Ошибка: запрос не найден.")
                return
            await query.edit_message_text(
                f"🔍 Ищу «{search_query}» на YouTube...\n"
                f"⏳ Это займёт секунду..."
            )
            results = search_youtube(search_query, max_results=10)
            if not results:
                await query.edit_message_text(
                    "❌ Ничего не найдено.\n\n"
                    "💡 Попробуй:\n"
                    "• Уточнить название\n"
                    "• Добавить исполнителя\n"
                    "• Использовать английское название\n"
                    "• Проверить правописание"
                )
                return
            context.user_data['search_results'] = results
            context.user_data['search_query'] = search_query
            context.user_data['search_type'] = 'youtube'
            await show_search_results(update, context, page=0)
            return
        
        if choice == 'search_kinopoisk':
            # Поиск на Кинопоиске
            search_query = context.user_data.get('search_query', '')
            if not search_query:
                await query.edit_message_text("❌ Ошибка: запрос не найден.")
                return
            await handle_kinopoisk_search(update, context, search_query)
            return
        
        # Обработка перелистывания страниц
        if choice.startswith('search_page_'):
            page = int(choice.split('_')[-1])
            await show_search_results(update, context, page=page)
            return
        
        # Получаем индекс выбранного результата
        idx = int(choice.split('_')[1])
        results = context.user_data.get('search_results', [])
        
        if not results or idx >= len(results):
            await query.edit_message_text("❌ Ошибка: результат не найден.")
            return
        
        selected = results[idx]
        context.user_data['url'] = selected['url']
        url = selected['url']  # Обновляем url для дальнейшей обработки
        
        keyboard = [
            [InlineKeyboardButton("🎬 Видео", callback_data='video')],
            [InlineKeyboardButton("🎵 Только звук (MP3)", callback_data='audio')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ Выбрано: *{selected['title']}*\n"
            f"👤 Исполнитель: {selected['uploader']}\n"
            f"⏱ Длительность: {format_duration(selected['duration'])}\n\n"
            f"🤔 Что скачать?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Обработка Кинопоиска (kinopoisk_* callback)
    if choice.startswith('kinopoisk_'):
        if choice == 'kinopoisk_cancel':
            await query.edit_message_text("❌ Поиск отменён.")
            return
        
        # Обработка перелистывания страниц Кинопоиска
        if choice.startswith('kinopoisk_page_'):
            page = int(choice.split('_')[-1])
            await show_kinopoisk_results(update, context, page=page)
            return
        
        # Получаем индекс выбранного результата
        idx = int(choice.split('_')[1])
        results = context.user_data.get('search_results', [])
        
        if not results or idx >= len(results):
            await query.edit_message_text("❌ Ошибка: результат не найден.")
            return
        
        selected = results[idx]
        fbfind_url = selected['url']
        
        type_emoji = "🎬" if selected['type'] == 'film' else "📺"
        type_name = "Фильм" if selected['type'] == 'film' else "Сериал"
        year = f" ({selected['year']})" if selected['year'] else ''
        rating = f"\n⭐ Рейтинг: {selected['rating']}" if selected['rating'] else ''
        
        keyboard = [
            [InlineKeyboardButton("🔗 Открыть для просмотра", url=fbfind_url)],
            [InlineKeyboardButton("🔍 Искать другое", callback_data='search_new')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"{type_emoji} *{type_name}:* {selected['title']}{year}\n"
            f"{rating}\n\n"
            f"💡 Нажми кнопку ниже, чтобы открыть ссылку для просмотра:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    if not url:
        await query.edit_message_text("❌ Ошибка: ссылка не найдена. Отправь ссылку заново.")
        return
    
    if choice == 'video':
        keyboard = [
            [InlineKeyboardButton("🔥 Лучшее качество", callback_data='best')],
            [InlineKeyboardButton("📺 1080p (очень чёткое)", callback_data='1080')],
            [InlineKeyboardButton("📺 720p (хорошее)", callback_data='720')],
            [InlineKeyboardButton("📺 480p (среднее)", callback_data='480')],
            [InlineKeyboardButton("📺 360p (компактное)", callback_data='360')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎬 *Выбери качество видео:*\n\n"
            "• 🔥 Лучшее — максимальное качество\n"
            "• 📺 1080p — очень чёткое, но большой файл\n"
            "• 📺 720p — хорошее качество, оптимальный размер\n"
            "• 📺 480p — среднее, быстрее скачивается\n"
            "• 📺 360p — компактное, экономит трафик",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif choice == 'audio':
        await query.edit_message_text(
            "🎵 Скачиваю звук в MP3...\n"
            "⏳ Это может занять минуту..."
        )
        await download_audio(update, context, url)
    
    elif choice in ['best', '1080', '720', '480', '360']:
        quality_names = {'best': 'лучшее', '1080': '1080p', '720': '720p', '480': '480p', '360': '360p'}
        await query.edit_message_text(
            f"🎬 Скачиваю видео ({quality_names.get(choice, choice)})...\n"
            "⏳ Это может занять пару минут..."
        )
        await download_video(update, context, url, choice)
    
    elif choice == 'back':
        keyboard = [
            [InlineKeyboardButton("🎬 Видео", callback_data='video')],
            [InlineKeyboardButton("🎵 Только звук (MP3)", callback_data='audio')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🤔 Что хочешь скачать?",
            reply_markup=reply_markup
        )


# ========== СКАЧИВАНИЕ ==========

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, quality: str):
    query = update.callback_query
    user = update.effective_user
    platform = get_platform(url)
    
    try:
        with tempfile.TemporaryDirectory(dir=DOWNLOAD_DIR) as tmpdir:
            output_template = os.path.join(tmpdir, '%(title)s.%(ext)s')
            cmd = build_video_cmd(url, quality, output_template)
            
            process = run_yt_dlp(cmd)
            
            if process.returncode != 0:
                error_msg = get_error_message(process.stderr)
                log_download(user.id, url, platform, 'video', quality, 'error', process.stderr[:500])
                await query.edit_message_text(error_msg)
                return
            
            video_file = find_downloaded_file(tmpdir)
            if not video_file:
                log_download(user.id, url, platform, 'video', quality, 'error', 'File not found')
                await query.edit_message_text("❌ Ошибка: файл не найден после скачивания.")
                return
            
            if not check_file_size(video_file, 2000):
                log_download(user.id, url, platform, 'video', quality, 'error', 'File too large')
                await query.edit_message_text(
                    "❌ Файл слишком большой (>2 ГБ).\n\n"
                    "💡 Попробуй выбрать меньшее качество (720p или ниже)."
                )
                return
            
            await query.edit_message_text(
                "⏳ Скачиваю видео..."
            )
            
            with open(video_file, 'rb') as f:
                logger.info(f"Sending video to user {user.id}, size: {os.path.getsize(video_file)} bytes")
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=f,
                    supports_streaming=True,
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=60
                )
            
            log_download(user.id, url, platform, 'video', quality, 'success')
    
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout downloading video for user {user.id}: {url}")
        log_download(user.id, url, platform, 'video', quality, 'error', 'Timeout')
        try:
            await query.edit_message_text(
                "⏱️ Скачивание заняло слишком много времени.\n\n"
                "🔄 Попробуй ещё раз или выбери меньшее качество."
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error downloading video for user {user.id}: {url} - {str(e)}", exc_info=True)
        log_download(user.id, url, platform, 'video', quality, 'error', str(e))
        try:
            await query.edit_message_text(f"❌ Произошла ошибка:\n{str(e)}")
        except Exception:
            pass


async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    query = update.callback_query
    user = update.effective_user
    platform = get_platform(url)
    
    try:
        with tempfile.TemporaryDirectory(dir=DOWNLOAD_DIR) as tmpdir:
            output_template = os.path.join(tmpdir, '%(title)s.%(ext)s')
            cmd = build_audio_cmd(url, output_template)
            
            process = run_yt_dlp(cmd)
            
            if process.returncode != 0:
                error_msg = get_error_message(process.stderr)
                log_download(user.id, url, platform, 'audio', 'mp3', 'error', process.stderr[:500])
                await query.edit_message_text(error_msg)
                return
            
            audio_file = find_downloaded_file(tmpdir)
            if not audio_file:
                log_download(user.id, url, platform, 'audio', 'mp3', 'error', 'File not found')
                await query.edit_message_text("❌ Ошибка: файл не найден после скачивания.")
                return
            
            if not check_file_size(audio_file, 50):
                log_download(user.id, url, platform, 'audio', 'mp3', 'error', 'File too large')
                await query.edit_message_text(
                    "❌ Аудио файл слишком большой.\n\n"
                    "💡 Попробуй другое видео."
                )
                return
            
            await query.edit_message_text(
                "⏳ Скачиваю аудио..."
            )
            
            with open(audio_file, 'rb') as f:
                logger.info(f"Sending audio to user {user.id}, size: {os.path.getsize(audio_file)} bytes")
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=f,
                    title=os.path.splitext(os.path.basename(audio_file))[0],
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=60
                )
            
            log_download(user.id, url, platform, 'audio', 'mp3', 'success')
    
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout downloading audio for user {user.id}: {url}")
        log_download(user.id, url, platform, 'audio', 'mp3', 'error', 'Timeout')
        try:
            await query.edit_message_text(
                "⏱️ Скачивание заняло слишком много времени.\n\n"
                "🔄 Попробуй ещё раз или выбери меньшее качество."
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error downloading audio for user {user.id}: {url} - {str(e)}", exc_info=True)
        log_download(user.id, url, platform, 'audio', 'mp3', 'error', str(e))
        try:
            await query.edit_message_text(f"❌ Произошла ошибка:\n{str(e)}")
        except Exception:
            pass
