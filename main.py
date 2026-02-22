import os
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
from keep_alive import keep_alive

# 1. Setup Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# 2. Environment Variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 3. Gemini Setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 4. Video ID Extractor (Supports Normal, Shorts, and Reels)
def get_video_id(url):
    patterns = [r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', r'shorts\/([0-9A-Za-z_-]{11})', r'youtu\.be\/([0-9A-Za-z_-]{11})']
    for pattern in patterns:
        match = re.search(pattern, url)
        if match: return match.group(1)
    return None

# 5. Full Transcript Fetcher (Including Auto-Generated)
def get_full_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi', 'en', 'en-GB'])
        return " ".join([t['text'] for t in transcript_list])
    except:
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_generated_transcript(['hi', 'en'])
            return " ".join([t['text'] for t in transcript.fetch()])
        except: return None

# 6. Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 *Ram Ram Bhai! Welcome to YT Summarizer AI*\n\n"
        "Main Shorts, Reels aur Long Videos ka nichod nikaal sakta hoon.\n\n"
        "🚀 *Use Kaise Karein?*\n"
        "Bas link bhejo aur magic dekho!"
    )
    keyboard = [[InlineKeyboardButton("Help ❓", callback_data='help'), InlineKeyboardButton("Status ✅", callback_data='status')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = "📖 *Help Menu:*\n\n1️⃣ /start - Restart bot\n2️⃣ /help - Support\n3️⃣ /status - Bot health"
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ *System Status:* Mast chal raha hai bhai!", parse_mode='Markdown')

# 7. AI Summarizer Logic
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    video_id = get_video_id(text)
    if video_id:
        status_msg = await update.message.reply_text("🔎 *AI Analysing...*")
        transcript = get_full_transcript(video_id)
        if transcript:
            await status_msg.edit_text("✍️ *Puri video ka nichod likh raha hoon...*")
            prompt = f"Identify all key points and give a long, detailed summary in Hinglish for this video: {transcript[:50000]}"
            response = model.generate_content(prompt)
            await status_msg.edit_text(f"📝 *DETAILED SUMMARY:*\n\n{response.text}", parse_mode='Markdown')
        else:
            await status_msg.edit_text("❌ Is video ke subtitles/captions off hain.")
    else:
        await update.message.reply_text("⚠️ Sahi link bhein bhai!")

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
