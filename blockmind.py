# blockmind_fixed.py

import os
import asyncio
import feedparser
import re
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot
from telegram import ParseMode
import html
from urllib.parse import urlparse, urlunparse
import hashlib
import logging
import json
import openai
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL = os.getenv("TARGET_CHANNEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print("👉 OPENAI KEY:", OPENAI_API_KEY)  # ✅ Սա գալիս ա ՀԵՏՈ


if not BOT_TOKEN or not TARGET_CHANNEL or not OPENAI_API_KEY:
    raise ValueError("❌ Missing environment variables")

bot = Bot(token=BOT_TOKEN)
openai.api_key = OPENAI_API_KEY
logging.basicConfig(level=logging.INFO)
UIDS_FILE = "sent_ids_blockmind.json"

TERMINOLOGY = {
    "Bitcoin": "Bitcoin",
    "Ethereum": "Ethereum",
    "Solana": "Solana",
    "BNB": "BNB",
    "XRP": "XRP",
    "DeFi": "DeFi",
    "NFT": "NFT",
    "Altcoin": "Ալտքոին",
    "Stablecoin": "Սթեյբլքոին",
    "Wallet": "Դրամապանակ",
    "Token": "Տոկեն",
    "Gas fee": "Gas fee",
    "Staking": "Սթեյքինգ",
    "Mining": "Մայնինք",
    "Airdrop": "Airdrop",
    "Smart Contract": "Smart Contract",
    "Layer 2": "Layer 2",
    "DEX": "DEX",
    "CEX": "CEX",
    "DAO": "DAO",
    "Metamask": "Metamask",
    "EVM": "EVM",
    "Halving": "Հալվինգ",
    "Machine Learning": "Մեքենայական ուսուցում",
    "Neural Network": "Neural Network",
    "Web3": "Web3",
    "Dapp": "Dapp",
    "Node": "Node",
    "Protocol": "Protocol",
    "AI": "AI",
    "blockchain": "Բլոկչեյն",
    "market": "շուկա",
    "Phantom": "Phantom",
    "Ether": "Ethereum",
    "Ethereum" : "Ethereum",
    "Ripple" : "Ripple",
    "Cardano" : "Cardano",
    "Solana" : "Solana" ,
    "Hyperliquid" :"Hyperliquid",
    "Ripple" :"Ripple",
    "Short" :"Short",   
    "Long" :"Long",
}

def apply_terminology(text):
    for term, translated in TERMINOLOGY.items():
        text = re.sub(rf"\b{term}\b", translated, text, flags=re.IGNORECASE)
    return text

def load_sent_ids():
    if os.path.exists(UIDS_FILE):
        try:
            with open(UIDS_FILE, "r", encoding="utf-8") as f:
                data = f.read().strip()
                return set(json.loads(data)) if data else set()
        except Exception as e:
            logging.warning(f"⚠️ Could not load sent IDs: {e}")
            return set()
    return set()

def save_sent_ids(sent_ids):
    try:
        with open(UIDS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(sent_ids), f, ensure_ascii=False, indent=2)
        logging.info("✅ UID list saved")
    except Exception as e:
        logging.error(f"❌ Could not save sent IDs: {e}")

sent_ids = load_sent_ids()

RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://blockworks.co/feed",
    "https://cryptoslate.com/feed/",
    "https://www.newsbtc.com/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://the-decoder.com/feed/",
    "https://bitcoinmagazine.com/.rss/full/",
    "https://blog.coinmarketcap.com/feed/",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cryptopotato.com/feed/",  
]

def detect_emoji(text):
    text = text.lower()
    if "bitcoin" in text or "btc" in text:
        return "₿"
    elif "ethereum" in text or "eth" in text:
        return "⬨"
    elif "solana" in text or "sol" in text:
        return "🔮"
    elif "toncoin" in text or "ton" in text:
        return "💎"
    elif "bnb" in text or "binance" in text:
        return "🔶"
    elif "xrp" in text or "ripple" in text:
        return "🌊"
    elif "dogecoin" in text or "doge" in text:
        return "🐶"
    elif "cardano" in text or "ada" in text:
        return "🧬"
    elif "polkadot" in text or "dot" in text:
        return "🎯"
    elif "avalanche" in text or "avax" in text:
        return "🏔️"
    elif "shiba" in text or "shib" in text:
        return "🐕"
    elif "ai" in text or "artificial intelligence" in text:
        return "🧠"
    elif "machine learning" in text or "ml" in text:
        return "🤖"
    elif "blockchain" in text:
        return "🔗"
    elif "nft" in text:
        return "🖼️"
    elif "defi" in text:
        return "🏦"
    elif "wallet" in text:
        return "👛"
    elif "staking" in text:
        return "📥"
    elif "mining" in text:
        return "⛏️"
    elif "airdrop" in text:
        return "🎁"
    elif "smart contract" in text:
        return "📜"
    elif "market" in text or "price" in text:
        return "📊"
    elif "vitalik" in text or "buterin" in text:
        return "🧙‍♂️"
    elif "web3" in text:
        return "🌐"
    elif "halving" in text:
        return "✂️"
    else:
        return "📰"

def clean_description(desc, title=None):
    clean_text = html.unescape(BeautifulSoup(desc, 'html.parser').get_text())
    clean_text = re.sub(r"appeared first on.*", "", clean_text, flags=re.IGNORECASE).strip()
    if title:
        pattern = re.escape(title)
        clean_text = re.sub(f"^{pattern}[:\-․ ]*", "", clean_text)
    return clean_text.strip()

def clean_link(link: str) -> str:
    parsed = urlparse(link)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))

def generate_uid(entry) -> str:
    base = entry.get("id") or entry.get("guid") or clean_link(entry.link)
    return hashlib.md5(base.strip().lower().encode("utf-8")).hexdigest()

def get_source_name(url):
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "").capitalize()

def build_message(title, desc, link, source, emoji):
    return (
        f"<b>{emoji} {html.escape(title).strip()}</b>\n\n"
        f"{html.escape(desc).strip()}\n\n"
        f'<i>📎 Ամբողջ հոդվածը՝  <a href="{link}">{source}</a></i>\n\n'
        f'🧠 <a href="https://t.me/blockmindam">Blockmind | Crypto & AI Digest</a>'
    )

async def translate_text(text):
    models = ["gpt-4o", "gpt-3.5-turbo"]
    for model in models:
        try:
            completion = await openai.ChatCompletion.acreate(
                model=model,
                messages=[
                    {"role": "system", "content": "Translate the following text to Armenian with natural, clear language and correct grammar. Avoid awkward structure."},
                    {"role": "user", "content": text}
                ]
            )
            logging.info(f"✅ Translation done with {model}")
            translated = completion.choices[0].message.content.strip()
            return apply_terminology(translated)
        except Exception as e:
            logging.warning(f"⚠️ Translation with {model} failed: {e}")
    return text

async def extract_image_url(link):
    try:
        headers = { "User-Agent": "Mozilla/5.0" }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(link, timeout=10) as response:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, "html.parser")
                for prop in ["og:image", "twitter:image"]:
                    tag = soup.find("meta", property=prop)
                    if tag and tag.get("content"):
                        return tag["content"]
                img_tag = soup.find("img", src=True)
                if img_tag and img_tag["src"].startswith("http"):
                    return img_tag["src"]
        return None
    except Exception as e:
        logging.warning(f"⚠️ Error fetching image: {e}")
        return None

async def fetch_and_send():
    global sent_ids
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            logging.info(f"🔄 Checking: {feed_url}")
            for entry in feed.entries[:5]:
                title = entry.title.strip()
                link = entry.link
                raw_desc = entry.get("description", "")
                desc = clean_description(raw_desc, title)
                uid = generate_uid(entry)

                if uid in sent_ids:
                    continue

                emoji = detect_emoji(f"{title} {desc}")
                source = get_source_name(link)
                # Try to get image from RSS <media:content> first
                image_url = entry.get("media_content", [{}])[0].get("url")

                # If not found in feed, try scraping from the article page
                if not image_url:
                    image_url = await extract_image_url(link)


                title_translated = await translate_text(title)
                desc_translated = await translate_text(desc)

                message = build_message(title_translated, desc_translated, link, source, emoji)

                try:
                    if image_url:
                        await asyncio.to_thread(
                            bot.send_photo,
                            chat_id=TARGET_CHANNEL,
                            photo=image_url,
                            caption=message,
                            parse_mode=ParseMode.HTML
                        )
                    else:
                        await asyncio.to_thread(
                            bot.send_message,
                            chat_id=TARGET_CHANNEL,
                            text=message,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True
                        )
                except Exception as e:
                    logging.error(f"❌ Telegram error: {e}")

                sent_ids.add(uid)
                save_sent_ids(sent_ids)
                logging.info(f"✅ Published: {title_translated}")
                await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"❌ Feed error ({feed_url}): {e}")

async def scheduler():
    while True:
        await fetch_and_send()
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(scheduler())
