import os
import tempfile
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import google.generativeai as genai
import whisper
import re
from keep_alive import keep_alive

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Load whisper model globally to save time
# Using base or tiny to ensure it responds within 30 seconds
whisper_model = whisper.load_model("tiny")

def get_youtube_id(url):
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def get_youtube_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        formatter = TextFormatter()
        return formatter.format_transcript(transcript)
    except Exception as e:
        logger.error(f"Error fetching transcript: {e}")
        return None

def summarize_text(text):
    if not GEMINI_API_KEY:
        return "Gemini API key is not configured."
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"Please summarize the following text into exactly 3 concise bullet points:\n\n{text}"
        response = model.generate_content(prompt)
        # Log to DB
        try:
            import requests
            requests.post('http://localhost:5000/api/logs', json={"event": f"Summarized text of length {len(text)}"})
        except Exception as log_e:
            logger.error(f"Failed to log: {log_e}")
            
        return response.text
    except Exception as e:
        logger.error(f"Error calling Gemini: {e}")
        return "Failed to generate summary."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Send me a YouTube link or a voice note, and I will summarize it into exactly 3 concise bullet points.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    video_id = get_youtube_id(text)
    if video_id:
        await update.message.reply_text("Fetching YouTube transcript...")
        transcript = get_youtube_transcript(video_id)
        if transcript:
            await update.message.reply_text("Summarizing...")
            summary = summarize_text(transcript)
            await update.message.reply_text(summary)
        else:
            await update.message.reply_text("Could not fetch transcript for this video. It might not have English subtitles.")
    else:
        await update.message.reply_text("Please send a valid YouTube link or a voice note.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Downloading voice note...")
    file = await update.message.voice.get_file()
    
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
        tmp_path = tmp_file.name
        
    await file.download_to_drive(tmp_path)
    
    await update.message.reply_text("Transcribing...")
    try:
        result = whisper_model.transcribe(tmp_path)
        transcript = result["text"]
        
        await update.message.reply_text("Summarizing...")
        summary = summarize_text(transcript)
        await update.message.reply_text(summary)
    except Exception as e:
        logger.error(f"Error processing voice: {e}")
        await update.message.reply_text("Failed to process voice note.")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN is missing!")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    keep_alive()
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
