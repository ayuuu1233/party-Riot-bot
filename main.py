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

# 4. Universal Video ID Extractor
def get_video_id(url):
    patterns = [r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', r'shorts\/([0-9A-Za-z_-]{11})', r'youtu\.be\/([0-9A-Za-z_-]{11})']
    for pattern in patterns:
        match = re.search(pattern, url)
        if match: return match.group(1)
    return None

# 5. Advanced Transcript Fetcher
def get_full_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript(['hi', 'en'])
        except:
            transcript = transcript_list.find_generated_transcript(['hi', 'en'])
        return " ".join([t['text'] for t in transcript.fetch()])
    except: return None

# 6. Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_obj = await context.bot.get_me()
    bot_username = bot_obj.username
    share_url = f"https://t.me/share/url?url=t.me/{bot_username}&text=Bhai, ye AI bot YouTube video ki puri summary nikaal deta hai! Try kar. 🔥"
    
    welcome_text = (
        "👋 *Ram Ram Bhai! Welcome to AI YouTube Summarizer*\n\n"
        "Main kisi bhi YouTube video, Shorts ya Reel ka poora nichod nikaal sakta hoon.\n\n"
        "🚀 *Features:*\n"
        "✅ Detailed Summary in Hinglish\n"
        "✅ Support for Long Videos & Shorts\n"
        "✅ Works with Auto-generated captions"
    )
    
    keyboard = [
        [InlineKeyboardButton("Help ❓", callback_data='help'), 
         InlineKeyboardButton("Status ✅", callback_data='status')],
        [InlineKeyboardButton("Share with Friends 📢", url=share_url)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # AAPKA IMAGE LINK YAHAN HAI
    image_url = "https://share.google/mZ9td0GQMjSlmDulD"
    
    try:
        await update.message.reply_photo(
            photo=image_url,
            caption=welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except:
        # Agar image link kaam nahi kare toh normal text bhej dega
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = "📖 *Help Menu:*\n\n1. YouTube link bhejo.\n2. Bot summary likhega.\n3. /status se bot check karo."
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 *Status:* Bot mast chal raha hai!", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    video_id = get_video_id(text)
    if video_id:
        status_msg = await update.message.reply_text("🔎 *AI Analysing Video...*")
        transcript = get_full_transcript(video_id)
        if transcript:
            await status_msg.edit_text("✍️ *Detailed summary likh raha hoon...*")
            prompt = f"Give a very detailed, long summary of this video transcript in Hinglish covering all segments: {transcript[:50000]}"
            response = model.generate_content(prompt)
            await status_msg.edit_text(f"📝 *DETAILED SUMMARY:*\n\n{response.text}\n\n📢 *Doston ko bhi bhein ye bot!*", parse_mode='Markdown')
        else:
            await status_msg.edit_text("❌ Is video ke subtitles/captions disable hain.")
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
