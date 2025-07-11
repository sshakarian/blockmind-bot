import feedparser
import hashlib
import json
import os
import re
import time
from datetime import datetime

import openai
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- CONFIG ---
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("TARGET_CHANNEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.MARKDOWN)
dp = Dispatcher(bot)

openai.api_key = OPENAI_API_KEY

# --- FUNCTIONS ---

async def translate_text(text, target_lang="hy"):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Translate the following text to {target_lang}. Return only the translated text."},
                {"role": "user", "content": text}
            ]
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("Translation error:", e)
        return text

def load_sent_ids():
    try:
        with open("sent_ids_blockmind.json", "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_sent_ids(sent_ids):
    with open("sent_ids_blockmind.json", "w") as f:
        json.dump(list(sent_ids), f)

def clean_html(text):
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', text)

def generate_id(entry):
    h = hashlib.sha256()
    h.update(entry.title.encode('utf-8'))
    return h.hexdigest()

async def process_feed(url, sent_ids):
    print("\n🔄 Checking:", url)
    feed = feedparser.parse(url)

    for entry in feed.entries:
        entry_id = generate_id(entry)
        if entry_id in sent_ids:
            continue

        title = clean_html(entry.title)
        link = entry.link
        content = clean_html(entry.summary) if hasattr(entry, 'summary') else ''

        translated_title = await translate_text(title)
        translated_content = await translate_text(content)

        text = f"*{translated_title}*\n"
        text += f"{translated_content}\n"
        text += f"[Աղբյուրում դիտել]({link})"

        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=text, disable_web_page_preview=True)
            print("✅ Published:", translated_title)
            sent_ids.add(entry_id)
            save_sent_ids(sent_ids)
            time.sleep(1.5)
        except Exception as e:
            print("❌ Error sending message:", e)

# --- MAIN LOOP ---

async def main_loop():
    rss_urls = [
        "https://cointelegraph.com/rss",
        "https://cryptopotato.com/feed/",
        "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"
    ]

    sent_ids = load_sent_ids()

    while True:
        for url in rss_urls:
            await process_feed(url, sent_ids)
        await asyncio.sleep(60)

# --- STARTUP ---
import asyncio
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(main_loop())
    executor.start_polling(dp, skip_updates=True)
