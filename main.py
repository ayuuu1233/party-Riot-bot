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
    CallbackQueryHandler, filters, ContextTypes, ConversationHandler
)
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
from keep_alive import keep_alive

# ================== 1. SETUP & CONFIG ==================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ADMIN_ID_STR = os.getenv("ADMIN_ID")
if not ADMIN_ID_STR:
    raise ValueError("❌ ADMIN_ID environment variable is required!")
ADMIN_ID = int(ADMIN_ID_STR)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# ================== 2. DATA MANAGEMENT ==================
user_data = {}
user_cooldown = defaultdict(lambda: datetime.min)
request_counts = defaultdict(int)
STATS_FILE = "bot_stats.json"

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f: return json.load(f)
        except: return {"total_summaries": 0, "total_users": 0, "errors": 0}
    return {"total_summaries": 0, "total_users": 0, "errors": 0}

def save_stats(stats):
    try:
        with open(STATS_FILE, 'w') as f: json.dump(stats, f, indent=2)
    except Exception as e: logger.error(f"Error saving stats: {e}")

def update_stats(stat_name, value=1):
    stats = load_stats()
    stats[stat_name] = stats.get(stat_name, 0) + value
    save_stats(stats)

# ================== 3. UTILITY FUNCTIONS ==================
def get_video_id(url):
    patterns = [r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', r'shorts\/([0-9A-Za-z_-]{11})', r'youtu\.be\/([0-9A-Za-z_-]{11})']
    for pattern in patterns:
        match = re.search(pattern, url)
        if match: return match.group(1)
    return None

async def reset_hourly_limits_task():
    global request_counts
    while True:
        await asyncio.sleep(3600)
        request_counts.clear()
        logger.info("🔄 Hourly limits reset successfully!")

# ================== 4. COMMAND HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    if user_id not in user_data:
        user_data[user_id] = {"first_name": user_name, "joined_date": datetime.now().isoformat()}
        update_stats("total_users")
    
    welcome_text = f"👋 *Ram Ram Bhai {user_name}!* 🎬\n\nMain YouTube summary nikaal sakta hoon. Link bhejo!"
    keyboard = [[InlineKeyboardButton("Status ✅", callback_data='status'), InlineKeyboardButton("Support 🆘", callback_data='support')]]
    
    image_url = "https://i.ibb.co/6R0D5fT/gojo-static.jpg"
    try:
        await update.message.reply_photo(photo=image_url, caption=welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 *Feedback Bhej De Bhai!*")
    return "WAITING_FOR_FEEDBACK"

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Feedback mil gaya!")
    return ConversationHandler.END

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    stats = load_stats()
    await update.message.reply_text(f"🔐 *Admin stats:* Users: {stats['total_users']}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    video_id = get_video_id(text)
    if not video_id:
        await update.message.reply_text("⚠️ Sahi link bhej bhai!")
        return
    
    status_msg = await update.message.reply_text("🔎 *Processing...*")
    # ... summary logic here ...
    await status_msg.edit_text("📝 Summary ready!")
    update_stats("total_summaries")

# ================== 5. MAIN ==================
def main():
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin_stats", admin_stats))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("✅ Bot starting...")

    # Yahan humne loop error fix kiya hai
    loop = asyncio.get_event_loop()
    loop.create_task(reset_hourly_limits_task())

    app.run_polling()

if __name__ == '__main__':
    main()
