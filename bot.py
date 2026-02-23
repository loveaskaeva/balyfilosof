# -*- coding: utf-8 -*-
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from token_config import TOKEN
DATA_PATH = Path(__file__).with_name("scores_philosophy.json")

score_pattern = re.compile(r"^!\s*(-?\d+)\s*$")


def load_scores():
    if not DATA_PATH.exists():
        return {}
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_scores(data):
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_display_name(user):
    if user.full_name:
        return user.full_name
    if user.username:
        return user.username
    return str(user.id)


def ensure_chat(data, chat_id):
    chat_key = str(chat_id)
    if chat_key not in data:
        data[chat_key] = {}
    return data[chat_key]


def add_score(data, chat_id, user, delta):
    chat_data = ensure_chat(data, chat_id)
    user_key = str(user.id)
    entry = chat_data.get(user_key, {"name": get_display_name(user), "score": 0})
    entry["name"] = get_display_name(user)
    entry["score"] = entry.get("score", 0) + delta
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    chat_data[user_key] = entry


def build_table(data, chat_id):
    chat_data = data.get(str(chat_id), {})
    if not chat_data:
        return "Таблица пуста."
    rows = sorted(chat_data.values(), key=lambda x: x.get("score", 0), reverse=True)
    lines = ["Баллы по философии:"]
    for index, row in enumerate(rows, start=1):
        lines.append(f"{index}. {row.get('name')} — {row.get('score')}")
    return "\n".join(lines)


def is_topic_message(update):
    message = update.effective_message
    if not message:
        return False
    return bool(message.is_topic_message)


def topic_id(update):
    message = update.effective_message
    if not message:
        return None
    return message.message_thread_id


async def handle_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return
    if update.effective_chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return
    if not is_topic_message(update):
        return
    text = message.text or ""
    match = score_pattern.match(text)
    if not match:
        return
    delta = int(match.group(1))
    data = load_scores()
    add_score(data, update.effective_chat.id, message.from_user, delta)
    save_scores(data)


async def handle_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return
    if update.effective_chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return
    if not is_topic_message(update):
        return
    data = load_scores()
    table_text = build_table(data, update.effective_chat.id)
    await message.reply_text(table_text, message_thread_id=topic_id(update))


async def handle_table_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return
    text = (message.text or "").strip().lower()
    if text != "!т":
        return
    await handle_table(update, context)


def main():
    if not TOKEN:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", handle_table))
    app.add_handler(CommandHandler("t", handle_table))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!\s*-?\d+\s*$"), handle_score))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^!т$"), handle_table_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
