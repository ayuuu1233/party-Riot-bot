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

# 3. Gemini Setup (Using Flash model for long videos)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash') # 1.5-flash lambi videos handle karta hai

# 4. Extract Video ID (Works for Reels, Shorts, and Links)
def get_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', # Normal links
        r'shorts\/([0-9A-Za-z_-]{11})',     # Shorts links
        r'youtu\.be\/([0-9A-Za-z_-]{11})'   # Shortened links
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# 5. Get Full Transcript (Including Auto-Generated)
def get_full_transcript(video_id):
    try:
        # Isme humne 'hi' (Hindi) aur 'en' (English) dono auto-captions on kar diye hain
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi', 'en', 'en-GB'])
        return " ".join([t['text'] for t in transcript_list])
    except:
        try:
            # Agar primary nahi mila toh auto-generated dhundega
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_generated_transcript(['hi', 'en'])
            return " ".join([t['text'] for t in transcript.fetch()])
        except Exception as e:
            return None

# 6. Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = "🔥 *AI Multi-Summarizer Bot*\n\nMain Shorts, Reels aur Long Videos (Bina Subtitles wali bhi) summarize kar sakta hoon!"
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    video_id = get_video_id(text)
    
    if video_id:
        status_msg = await update.message.reply_text("🔎 *AI Is Analyzing the video...*")
        
        transcript = get_full_transcript(video_id)
        
        if transcript:
            await status_msg.edit_text("✍️ *Nichod nikaal raha hoon...*")
            
            # Pura video summarize karne ke liye lamba prompt
            prompt = (
                f"Identify all key points from this video transcript. "
                f"Provide a detailed summary in Hinglish that covers the entire video from start to end. "
                f"Transcript: {transcript[:50000]}" # 50k characters handle karega
            )
            
            response = model.generate_content(prompt)
            await status_msg.edit_text(f"📝 *DETAILED SUMMARY:*\n\n{response.text}", parse_mode='Markdown')
        else:
            await status_msg.edit_text("❌ Is video par Captions/Subtitles disable hain. AI ise read nahi kar paa raha.")
    else:
        await update.message.reply_text("⚠️ Sahi YouTube, Shorts ya Reel link bhein!")

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
