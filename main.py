import os
import re
import logging
import json
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
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Gemini Setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# ================== 2. DATA MANAGEMENT ==================
# User tracking
user_data = {}
user_cooldown = defaultdict(lambda: datetime.min)
user_history = defaultdict(list)
request_counts = defaultdict(int)

# Cooldown settings (seconds)
COOLDOWN_SECONDS = 5
MAX_REQUESTS_PER_HOUR = 50

# Stats file
STATS_FILE = "bot_stats.json"

def load_stats():
    """Load stats from file"""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"total_summaries": 0, "total_users": 0, "errors": 0}
    return {"total_summaries": 0, "total_users": 0, "errors": 0}

def save_stats(stats):
    """Save stats to file"""
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving stats: {e}")

def update_stats(stat_name, value=1):
    """Update bot statistics"""
    stats = load_stats()
    stats[stat_name] = stats.get(stat_name, 0) + value
    save_stats(stats)

# ================== 3. UTILITY FUNCTIONS ==================
def get_video_id(url):
    """Extract YouTube video ID from various URL formats"""
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
        if match:
            return match.group(1)
    return None

def get_full_transcript(video_id):
    """Fetch transcript with error handling"""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to find manually created transcript first
        try:
            transcript = transcript_list.find_transcript(['hi', 'en'])
        except:
            try:
                # Fallback to auto-generated
                transcript = transcript_list.find_generated_transcript(['hi', 'en'])
            except Exception as e:
                logger.error(f"No transcript found for {video_id}: {e}")
                return None
        
        full_text = " ".join([t['text'] for t in transcript.fetch()])
        return full_text if full_text.strip() else None
        
    except Exception as e:
        logger.error(f"Transcript fetch error for {video_id}: {e}")
        return None

def check_rate_limit(user_id):
    """Check if user is rate limited"""
    current_time = datetime.now()
    last_request = user_cooldown[user_id]
    
    # Check cooldown
    if current_time - last_request < timedelta(seconds=COOLDOWN_SECONDS):
        return False, f"⏳ Thoda wait kar bhai! {COOLDOWN_SECONDS}s mein ek request."
    
    # Check hourly limit
    if request_counts[user_id] >= MAX_REQUESTS_PER_HOUR:
        return False, f"⚠️ Bhai, tune {MAX_REQUESTS_PER_HOUR} requests kar diye! 1 ghante baad try kar."
    
    return True, "OK"

def reset_daily_limits():
    """Reset daily request counts (call this daily)"""
    global request_counts
    request_counts.clear()
    logger.info("Daily limits reset!")

# ================== 4. COMMAND HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command with welcome message"""
    try:
        user_id = update.message.from_user.id
        user_name = update.message.from_user.first_name
        
        # Track user
        if user_id not in user_data:
            user_data[user_id] = {
                "first_name": user_name,
                "joined_date": datetime.now().isoformat(),
                "total_requests": 0
            }
            update_stats("total_users")
        
        bot_obj = await context.bot.get_me()
        bot_username = bot_obj.username
        share_url = f"https://t.me/share/url?url=t.me/{bot_username}&text=Bhai, ye AI bot YouTube video ki puri summary nikaal deta hai! Try kar. 🔥"
        
        welcome_text = (
            "👋 *Ram Ram Bhai! Welcome to AI YouTube Summarizer* 🎬\n\n"
            f"Shukriya {user_name}! Main kisi bhi YouTube video, Shorts ya Reel ka poora summary nikaal sakta hoon.\n\n"
            "🚀 *Features:*\n"
            "✅ Detailed Summary in Hinglish\n"
            "✅ Support for Long Videos & Shorts\n"
            "✅ Auto-generated & Manual Captions\n"
            "✅ Smart Rate Limiting\n"
            "✅ Error Recovery\n\n"
            "📌 *Kaise Use Karu:*\n"
            "1️⃣ YouTube link bhejo\n"
            "2️⃣ Bot summary likhega\n"
            "3️⃣ Apni gaand par baith aur enjoy kar!\n\n"
            "⏱️ *Limits:* 50 requests per hour, 5 second cooldown"
        )
        
        keyboard = [
            [InlineKeyboardButton("Help ❓", callback_data='help'), 
             InlineKeyboardButton("Status ✅", callback_data='status')],
            [InlineKeyboardButton("My Stats 📊", callback_data='mystats'),
             InlineKeyboardButton("Support 🆘", callback_data='support')],
            [InlineKeyboardButton("Share with Friends 📢", url=share_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        image_url = "https://share.google/mZ9td0GQMjSlmDulD"
        
        try:
            await update.message.reply_photo(
                photo=image_url,
                caption=welcome_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Image failed, sending text instead: {e}")
            await update.message.reply_text(
                welcome_text, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Start command error: {e}")
        await update.message.reply_text("❌ Error aaya! Support se contact kar.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == 'help':
            help_text = (
                "📖 *Help Menu:*\n\n"
                "🎬 *Video Summary:*\n"
                "1. YouTube link bhejo\n"
                "2. Bot analyze karega\n"
                "3. Summary mil jayega!\n\n"
                "⚡ *Supported Links:*\n"
                "• youtube.com/watch?v=...\n"
                "• youtu.be/...\n"
                "• youtube.com/shorts/...\n\n"
                "⚠️ *Zaruri Baatein:*\n"
                "• Video ke captions hone zaruri hain\n"
                "• 5 second cooldown hai\n"
                "• 50 requests per hour limit\n\n"
                "❓ Problem ho raha hai?\n"
                "/support command use kar!"
            )
            await query.edit_message_text(help_text, parse_mode='Markdown')
            
        elif query.data == 'status':
            status_text = (
                "🚀 *Bot Status:*\n\n"
                "✅ *Servers:* All Green\n"
                "⚡ *Speed:* Lightning Fast\n"
                "🔧 *API:* Connected\n"
                "👥 *Users:* Active\n\n"
                "Bot mast chal raha hai bhai! 🔥"
            )
            await query.edit_message_text(status_text, parse_mode='Markdown')
            
        elif query.data == 'mystats':
            user_id = query.from_user.id
            if user_id in user_data:
                user_info = user_data[user_id]
                stats_text = (
                    f"📊 *Your Stats:*\n\n"
                    f"👤 Name: {user_info['first_name']}\n"
                    f"📅 Joined: {user_info['joined_date'][:10]}\n"
                    f"🎬 Total Requests: {user_info['total_requests']}\n"
                    f"⏳ Used Today: {request_counts[user_id]}/50\n\n"
                    "Keep using! 🚀"
                )
            else:
                stats_text = "📊 *No stats yet!*\nSend a YouTube link to get started!"
            
            await query.edit_message_text(stats_text, parse_mode='Markdown')
            
        elif query.data == 'support':
            support_text = (
                "🆘 *Support Information:*\n\n"
                "❌ Captions disabled?\n"
                "→ Video owner ne captions off kiye hain\n"
                "→ Dusra video try kar!\n\n"
                "⚠️ Rate limit exceed?\n"
                "→ 1 ghante baad try kar\n\n"
                "🐛 Bug mil gaya?\n"
                "→ /feedback command use kar\n\n"
                "📞 Direct Contact:\n"
                "→ @ayuuu1233 (Creator)"
            )
            await query.edit_message_text(support_text, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Button callback error: {e}")
        await query.edit_message_text("❌ Error! Try again.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_text = (
        "📖 *Help Menu:*\n\n"
        "🎬 YouTube link bhejo aur poora summary mil jayega!\n\n"
        "📌 *Commands:*\n"
        "/start - Start command\n"
        "/help - Ye help menu\n"
        "/stats - Bot ke overall stats\n"
        "/feedback - Apni feedback bhej\n"
        "/support - Support ke liye\n\n"
        "Just send any YouTube link! 🚀"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Status command"""
    stats = load_stats()
    status_text = (
        "🚀 *Bot Status & Statistics:*\n\n"
        f"📊 Total Summaries: {stats['total_summaries']}\n"
        f"👥 Total Users: {stats['total_users']}\n"
        f"⚠️ Errors: {stats['errors']}\n\n"
        "✅ Bot mast chal raha hai! 🔥"
    )
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Feedback handler"""
    feedback_text = (
        "📝 *Feedback Bhej De!*\n\n"
        "Apni feedback likha kar bhej. "
        "Improvements ke liye appreciate karte hain! 🙏"
    )
    await update.message.reply_text(feedback_text, parse_mode='Markdown')

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to view detailed stats"""
    user_id = update.message.from_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Tujhe permission nahi hai bhai!")
        return
    
    stats = load_stats()
    admin_text = (
        f"🔐 *Admin Dashboard*\n\n"
        f"📊 Total Summaries Generated: {stats['total_summaries']}\n"
        f"👥 Total Active Users: {stats['total_users']}\n"
        f"⚠️ Total Errors: {stats['errors']}\n"
        f"👤 Unique Users Tracked: {len(user_data)}\n"
        f"🔄 Active Sessions: {len([u for u in request_counts if request_counts[u] > 0])}\n\n"
        f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await update.message.reply_text(admin_text, parse_mode='Markdown')

# ================== 5. MESSAGE HANDLER ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler for YouTube links"""
    try:
        user_id = update.message.from_user.id
        text = update.message.text.strip()
        
        # Check rate limit
        is_allowed, message = check_rate_limit(user_id)
        if not is_allowed:
            await update.message.reply_text(f"⏳ {message}")
            return
        
        # Extract video ID
        video_id = get_video_id(text)
        if not video_id:
            await update.message.reply_text(
                "⚠️ *Invalid Link!* 🤔\n\n"
                "Sahi YouTube link bhej bhai!\n"
                "Examples:\n"
                "• youtube.com/watch?v=...\n"
                "• youtu.be/...\n"
                "• youtube.com/shorts/...",
                parse_mode='Markdown'
            )
            return
        
        # Update cooldown and request count
        user_cooldown[user_id] = datetime.now()
        request_counts[user_id] += 1
        
        # Update user data
        if user_id in user_data:
            user_data[user_id]['total_requests'] += 1
        
        # Show analyzing status
        status_msg = await update.message.reply_text(
            "🔎 *AI Analysing Video...*\n"
            "Thoda wait kar bhai! 🤖"
        )
        
        # Fetch transcript
        transcript = get_full_transcript(video_id)
        
        if not transcript:
            await status_msg.edit_text(
                "❌ *Error:* Is video ke subtitles/captions disable hain.\n\n"
                "😓 Dusra video try kar bhai! "
                "(Video ke liye captions zaruri hain)"
            )
            update_stats("errors")
            return
        
        # Warn for long transcripts
        transcript_length = len(transcript)
        if transcript_length > 100000:
            await status_msg.edit_text(
                "⚠️ *Video Bahut Lambi Hai!*\n"
                f"({transcript_length} characters)\n\n"
                "🤔 Summary likh raha hoon... 2-3 minute wait kar! ⏱️"
            )
        elif transcript_length > 50000:
            await status_msg.edit_text(
                "📊 *Big Video Detected!*\n"
                "Summary likh raha hoon... thoda wait kar 🕐"
            )
        else:
            await status_msg.edit_text(
                "✍️ *Detailed summary likh raha hoon...*\n"
                "Bas ek minute! ⏳"
            )
        
        # Generate summary
        prompt = (
            f"Mujhe iss YouTube video ke liye VERY DETAILED SUMMARY "
            f"Hinglish mein chahiye. Sab important points cover kar. "
            f"Heading ke sath acha structure bana. "
            f"Video transcript:\n\n{transcript[:80000]}"
        )
        
        response = model.generate_content(prompt)
        summary = response.text
        
        # Split long summaries
        if len(summary) > 4096:
            # Telegram message limit is 4096 characters
            parts = [summary[i:i+4000] for i in range(0, len(summary), 4000)]
            
            for idx, part in enumerate(parts, 1):
                if idx == 1:
                    await status_msg.edit_text(
                        f"📝 *SUMMARY (Part {idx}/{len(parts)}):*\n\n{part}",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        f"📝 *SUMMARY (Part {idx}/{len(parts)}):*\n\n{part}",
                        parse_mode='Markdown'
                    )
        else:
            await status_msg.edit_text(
                f"📝 *SUMMARY:*\n\n{summary}\n\n"
                f"📢 *Apne doston ko bhi bhej!* 🎉",
                parse_mode='Markdown'
            )
        
        # Update stats
        update_stats("total_summaries")
        
        # Add to user history
        user_history[user_id].append({
            "video_id": video_id,
            "timestamp": datetime.now().isoformat(),
            "transcript_length": transcript_length
        })
        
        logger.info(f"User {user_id} - Summary generated for {video_id}")
        
    except Exception as e:
        logger.error(f"Handle message error: {e}")
        update_stats("errors")
        try:
            await update.message.reply_text(
                f"❌ *Error Aaya!* 🤦\n\n"
                f"Technical Issue: {str(e)[:100]}\n\n"
                f"Retry kar bhai! 🔄"
            )
        except:
            pass

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle feedback messages"""
    try:
        # In production, you'd save this to a database or file
        feedback = update.message.text
        logger.info(f"Feedback from {update.message.from_user.id}: {feedback}")
        await update.message.reply_text(
            "✅ *Feedback mil gaya!*\n\n"
            "Shukriya bhai! Apki feedback zaruri hai. 🙏\n"
            "Jaldi improve karenge! 💪"
        )
    except Exception as e:
        logger.error(f"Feedback handler error: {e}")

# ================== 6. ERROR HANDLER ==================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ Bot Error:\n\n{str(context.error)[:500]}"
        )
    except:
        pass

# ================== 7. MAIN APPLICATION ==================
def main():
    """Start the bot"""
    try:
        logger.info("🚀 Starting AI YouTube Summarizer Bot 2.0...")
        
        app = ApplicationBuilder().token(TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("stats", status_command))
        app.add_handler(CommandHandler("feedback", feedback_command))
        app.add_handler(CommandHandler("admin_stats", admin_stats))
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        # Error handler
        app.add_error_handler(error_handler)
        
        # Keep alive
        keep_alive()
        
        logger.info("✅ Bot started successfully!")
        app.run_polling()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()
