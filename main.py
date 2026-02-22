import os
import re
import logging
import json
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
from keep_alive import keep_alive

# ================== 1. SETUP & CONFIG ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment Variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ADMIN_ID handle (with fallback to avoid crash)
ADMIN_ID_STR = os.getenv("ADMIN_ID")
if not ADMIN_ID_STR:
    logger.error("❌ ADMIN_ID environment variable is missing!")
    ADMIN_ID = 0 
else:
    ADMIN_ID = int(ADMIN_ID_STR)

# Gemini Setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# ================== 2. DATA MANAGEMENT ==================
user_data = {}
user_cooldown = defaultdict(lambda: datetime.min)
request_counts = defaultdict(int)
STATS_FILE = "bot_stats.json"

def update_stats(stat_name, value=1):
    try:
        stats = {"total_summaries": 0, "total_users": 0, "errors": 0}
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                stats = json.load(f)
        stats[stat_name] = stats.get(stat_name, 0) + value
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Stats error: {e}")

# ================== 3. UTILITY FUNCTIONS ==================
def get_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'shorts\/([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/watch\?v=([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match: return match.group(1)
    return None

def get_full_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(['hi', 'en'])
        except:
            transcript = transcript_list.find_generated_transcript(['hi', 'en'])
        return " ".join([t['text'] for t in transcript.fetch()])
    except Exception as e:
        logger.error(f"Transcript error: {e}")
        return None

# Simple Hourly Reset Task (Replaces APScheduler)
async def reset_limits_periodically():
    global request_counts
    while True:
        await asyncio.sleep(3600) # Wait 1 hour
        request_counts.clear()
        logger.info("🔄 Hourly limits reset!")

# ================== 4. COMMAND HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    welcome_text = (
        f"👋 *Ram Ram Bhai {user_name}!* 🎬\n\n"
        "Main YouTube videos aur Shorts ki poori summary nikaal sakta hoon.\n\n"
        "📌 *Kaise Use Karu:*\n"
        "Bas link bhejo aur enjoy kar!"
    )
    
    keyboard = [[InlineKeyboardButton("Status ✅", callback_data='status'), InlineKeyboardButton("Support 🆘", callback_data='support')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Gojo Direct Image Link
    image_url = "https://i.ibb.co/6R0D5fT/gojo-static.jpg"
    try:
        await update.message.reply_photo(photo=image_url, caption=welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    except:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'status':
        await query.edit_message_text("🚀 Bot mast chal raha hai bhai! All systems green. ✅")
    elif query.data == 'support':
        await query.edit_message_text("🆘 Support: @ayuuu1233 se contact karein.")

# ================== 5. MESSAGE HANDLER ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    video_id = get_video_id(text)
    if not video_id:
        await update.message.reply_text("⚠️ Sahi YouTube link bhej bhai!")
        return
    
    # Rate limit check (5s)
    if datetime.now() - user_cooldown[user_id] < timedelta(seconds=5):
        await update.message.reply_text("⏳ Thoda wait kar bhai! (5s cooldown)")
        return
    
    user_cooldown[user_id] = datetime.now()
    status_msg = await update.message.reply_text("🔎 *AI Analysing Video...*")
    
    transcript = get_full_transcript(video_id)
    if not transcript:
        await status_msg.edit_text("❌ Is video ke captions disable hain. Dusra try kar!")
        update_stats("errors")
        return

    await status_msg.edit_text("✍️ *Summary likh raha hoon...*")
    try:
        prompt = f"Summarize this video transcript in VERY DETAIL and in Hinglish: {transcript[:40000]}"
        response = model.generate_content(prompt)
        summary = response.text
        
        if len(summary) > 4000:
            await status_msg.edit_text(f"📝 *SUMMARY:*\n\n{summary[:4000]}", parse_mode='Markdown')
        else:
            await status_msg.edit_text(f"📝 *SUMMARY:*\n\n{summary}", parse_mode='Markdown')
        update_stats("total_summaries")
    except Exception as e:
        await status_msg.edit_text(f"❌ Gemini Error: {str(e)[:100]}")

# ================== 6. MAIN ==================
def main():
    keep_alive() # Keep-alive starts Flask
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Add Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("✅ Bot starting...")
    
    # Start reset task in background
    loop = asyncio.get_event_loop()
    loop.create_task(reset_limits_periodically())
    
    app.run_polling()

if __name__ == '__main__':
    main()
