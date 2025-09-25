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
    import os
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
            "HTTP-Referer": "https://your-app.com",
            "X-Title": "AI Telegram Combine",
            "Content-Type": "application/json"
        },
        json={
            "model": "qwen/qwen-2-72b-instruct",
            "messages": [{"role": "user", "content": f"Напиши короткий пост для Telegram на тему: '{topic}'. Добавь 2 эмодзи и 2 хэштега. Тон: дружелюбный эксперт."}],
            "max_tokens": 500
        },
        timeout=30
    )
    return resp.json()["choices"][0]["message"]["content"]
