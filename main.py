import os
import sqlite3
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_CHAT_ID = os.getenv("CHANNEL_CHAT_ID")
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
DB_PATH = "/tmp/content.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            published_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_topic(topic: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO content (topic) VALUES (?)", (topic,))
    conn.commit()
    conn.close()

def get_pending_topic():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT id, topic FROM content WHERE status = 'pending' ORDER BY id LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row

def mark_published(topic_id: int, content: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE content SET status = 'published', content = ?, published_at = ? WHERE id = ?", 
                 (content, datetime.utcnow().isoformat(), topic_id))
    conn.commit()
    conn.close()

def generate_text(topic: str) -> str:
    resp = requests.post(
        "https://api.together.xyz/v1/chat/completions",
        headers={"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "Qwen/Qwen2-72B-Instruct",
            "messages": [{"role": "user", "content": f"Напиши короткий пост для Telegram на тему: '{topic}'. Добавь 2 эмодзи и 2 хэштега. Тон: дружелюбный эксперт."}],
            "max_tokens": 500
        },
        timeout=30
    )
    return resp.json()["choices"][0]["message"]["content"]

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /add <тема>")
        return
    topic = " ".join(context.args)
    add_topic(topic)
    await update.message.reply_text(f"✅ Тема добавлена: {topic}")

async def publish_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_pending_topic()
    if not row:
        await update.message.reply_text("Нет тем со статусом 'pending'")
        return

    topic_id, topic = row
    await update.message.reply_text(f"Генерирую пост: {topic}...")

    try:
        text = generate_text(topic)
        await context.bot.send_message(chat_id=CHANNEL_CHAT_ID, text=text, parse_mode="HTML")
        mark_published(topic_id, text)
        await update.message.reply_text("✅ Опубликовано в канал!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT id, topic, status FROM content ORDER BY id DESC LIMIT 10")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("База пуста")
        return
    msg = "📋 Последние темы:\n\n"
    for r in rows:
        msg += f"{r[0]}. {r[1]} — <b>{r[2]}</b>\n"
    await update.message.reply_text(msg, parse_mode="HTML")

def main():
    init_db()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("publish", publish_command))
    app.add_handler(CommandHandler("list", list_command))
    app.run_polling()

if __name__ == "__main__":
    main()
