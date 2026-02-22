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
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment Variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Validate ADMIN_ID
ADMIN_ID_STR = os.getenv("ADMIN_ID")
if not ADMIN_ID_STR:
    raise ValueError("❌ ADMIN_ID environment variable is required!")
ADMIN_ID = int(ADMIN_ID_STR)

# Gemini Setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# ================== 2. DATA MANAGEMENT ==================
user_data = {}
user_cooldown = defaultdict(lambda: datetime.min)
user_history = defaultdict(list)
request_counts = defaultdict(int)
last_reset_time = datetime.now()

COOLDOWN_SECONDS = 5
MAX_REQUESTS_PER_HOUR = 50
STATS_FILE = "bot_stats.json"

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"total_summaries": 0, "total_users": 0, "errors": 0}
    return {"total_summaries": 0, "total_users": 0, "errors": 0}

def save_stats(stats):
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving stats: {e}")

def update_stats(stat_name, value=1):
    stats = load_stats()
    stats[stat_name] = stats.get(stat_name, 0) + value
    save_stats(stats)

# ================== 3. UTILITY FUNCTIONS ==================
def get_video_id(url):
    if not url or not isinstance(url, str):
        return None
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
            try:
                transcript = transcript_list.find_generated_transcript(['hi', 'en'])
            except:
                return None
        return " ".join([t['text'] for t in transcript.fetch()])
    except:
        return None

def check_rate_limit(user_id):
    current_time = datetime.now()
    last_request = user_cooldown[user_id]
    if current_time - last_request < timedelta(seconds=COOLDOWN_SECONDS):
        remaining = COOLDOWN_SECONDS - int((current_time - last_request).total_seconds())
        return False, f"⏳ Thoda wait kar bhai! {remaining}s mein request kar."
    if request_counts[user_id] >= MAX_REQUESTS_PER_HOUR:
        return False, f"⚠️ Bhai, tune limit exceed kar di! 1 ghante baad try kar."
    return True, "OK"

# CRITICAL FIX: Custom Async Reset Loop (No more APScheduler crash)
async def reset_hourly_limits_task():
    global request_counts, last_reset_time
    while True:
        await asyncio.sleep(3600)
        request_counts.clear()
        last_reset_time = datetime.now()
        logger.info("🔄 Hourly limits reset!")

# ================== 4. COMMAND HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        user_name = update.message.from_user.first_name
        if user_id not in user_data:
            user_data[user_id] = {"first_name": user_name, "joined_date": datetime.now().isoformat(), "total_requests": 0}
            update_stats("total_users")
        
        bot_obj = await context.bot.get_me()
        share_url = f"https://t.me/share/url?url=t.me/{bot_obj.username}&text=Check this AI Summarizer!"
        
        welcome_text = (
            "👋 *Ram Ram Bhai! Welcome to AI YouTube Summarizer* 🎬\n\n"
            f"Shukriya {user_name}! Main kisi bhi YouTube video ka nichod nikaal sakta hoon.\n\n"
            "🚀 *Features:*\n✅ Detailed Hinglish Summary\n✅ Long Video Support\n✅ Smart Rate Limits\n\n"
            "📌 *Kaise Use Karu:*\n1️⃣ Link bhejo 2️⃣ Enjoy kar!\n\n"
            "⏱️ *Limits:* 50 requests/hour, 5s cooldown"
        )
        
        keyboard = [
            [InlineKeyboardButton("Help ❓", callback_data='help'), InlineKeyboardButton("Status ✅", callback_data='status')],
            [InlineKeyboardButton("My Stats 📊", callback_data='mystats'), InlineKeyboardButton("Support 🆘", callback_data='support')],
            [InlineKeyboardButton("Share with Friends 📢", url=share_url)]
        ]
        
        image_url = "https://i.ibb.co/6R0D5fT/gojo-static.jpg"
        try:
            await update.message.reply_photo(photo=image_url, caption=welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except:
            await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Start error: {e}")

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 *Feedback Bhej De Bhai!* Bas message type karke bhej do.")
    return "WAITING_FOR_FEEDBACK"

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    feedback = update.message.text
    logger.info(f"Feedback from {user_id}: {feedback}")
    await update.message.reply_text("✅ Feedback mil gaya! Shukriya.")
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"📝 *New Feedback:* {feedback}")
    except: pass
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Process cancel kar diya.")
    return ConversationHandler.END

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Permission nahi hai.")
        return
    stats = load_stats()
    await update.message.reply_text(f"🔐 *Admin Panel*\n\nUsers: {stats['total_users']}\nSummaries: {stats['total_summaries']}\nErrors: {stats['errors']}", parse_mode='Markdown')

# ================== 5. MESSAGE HANDLER ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        text = update.message.text.strip()
        is_allowed, msg = check_rate_limit(user_id)
        if not is_allowed:
            await update.message.reply_text(msg)
            return
        
        video_id = get_video_id(text)
        if not video_id:
            await update.message.reply_text("⚠️ Sahi link bhej bhai!")
            return
        
        user_cooldown[user_id] = datetime.now()
        request_counts[user_id] += 1
        status_msg = await update.message.reply_text("🔎 *Analysing...*")
        
        transcript = get_full_transcript(video_id)
        if not transcript:
            await status_msg.edit_text("❌ Captions off hain.")
            update_stats("errors")
            return

        await status_msg.edit_text("✍️ *Writing Summary...*")
        prompt = f"Provide a long, detailed Hinglish summary of: {transcript[:50000]}"
        response = model.generate_content(prompt)
        summary = response.text
        
        if len(summary) > 4000:
            parts = [summary[i:i+4000] for i in range(0, len(summary), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await status_msg.edit_text(f"📝 *SUMMARY:*\n\n{summary}")
        update_stats("total_summaries")
    except Exception as e:
        logger.error(f"Error: {e}")
        update_stats("errors")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'status':
        await query.edit_message_text("🚀 Bot is LIVE!")
    elif query.data == 'mystats':
        await query.edit_message_text(f"📊 Used: {request_counts[query.from_user.id]}/50 today.")

# ================== 6. MAIN ==================
def main():
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Conv Handler for Feedback
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('feedback', feedback_command)],
        states={"WAITING_FOR_FEEDBACK": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback)]},
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_stats))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # Start reset loop
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(reset_hourly_limits_task())
    except: pass

    app.run_polling()

if __name__ == '__main__':
    main()
