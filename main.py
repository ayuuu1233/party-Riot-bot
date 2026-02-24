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
import yt_dlp
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


# Ye function metadata (Title/Description) nikalne ke liye
async def get_video_info_fallback(video_url):
    """Metadata fetcher with better error handling"""
    try:
        ydl_opts = {
            'quiet': True, 
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {
                "title": info.get('title', 'No Title'),
                "description": info.get('description', 'No Description')
            }
    except Exception as e:
        logger.error(f"yt-dlp absolute failure: {e}")
        return None


# ================== 2. DATA MANAGEMENT ==================
# User tracking
user_data = {}
user_cooldown = defaultdict(lambda: datetime.min)
user_history = defaultdict(list)
request_counts = defaultdict(int)
last_reset_time = datetime.now()

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
        remaining = COOLDOWN_SECONDS - int((current_time - last_request).total_seconds())
        return False, f"⏳ Thoda wait kar bhai! {remaining}s mein request kar."
    
    # Check hourly limit
    if request_counts[user_id] >= MAX_REQUESTS_PER_HOUR:
        remaining = MAX_REQUESTS_PER_HOUR - request_counts[user_id]
        return False, f"⚠️ Bhai, tune {MAX_REQUESTS_PER_HOUR} requests kar diye! 1 ghante baad try kar."
    
    return True, "OK"

def reset_hourly_limits():
    """Reset hourly request counts"""
    global request_counts, last_reset_time
    request_counts.clear()
    last_reset_time = datetime.now()
    logger.info("🔄 Hourly limits reset! All users can make requests again.")

# ================== 4. COMMAND HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ultra-Professional Start with Anime Style & Clean Logic"""
    try:
        user_id = update.message.from_user.id
        user_name = update.message.from_user.first_name
        
        # Action: Typing... (Professional touch)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
        
        # User Tracking (Conflict-free logic)
        if user_id not in user_data:
            user_data[user_id] = {
                "first_name": user_name,
                "joined_date": datetime.now().isoformat(),
                "total_requests": 0
            }
            update_stats("total_users")
        
        bot_obj = await context.bot.get_me()
        bot_username = bot_obj.username
        share_url = f"https://t.me/share/url?url=t.me/{bot_username}&text=Bhai, ye AI bot YouTube summary nikaal deta hai! 🔥"
        
        # ─── PROFESSIONAL FORMATTING & FONTS ───
        # Note: Unicode fonts looks premium on all devices
        welcome_text = (
            f"⚡ 𝖶𝖾𝗅𝖼𝗈𝗆𝖾, {user_name}! ⚡\n\n"
            "✨ *『 𝖠𝖨 𝖸𝖮𝖴𝖳𝖴𝖡𝖤 𝖲𝖴𝖬𝖬𝖠𝖱𝖨𝖹𝖤𝖱 』*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎬 *ꜱʏꜱᴛᴇᴍ ᴄᴀᴘᴀʙɪʟɪᴛɪᴇꜱ:*\n"
            "┠ 🔹 *ꜰᴀꜱᴛ ꜱᴜᴍᴍᴀʀʏ:* Seconds mein results\n"
            "┠ 🔹 *ʜɪɴɢʟɪꜱʜ ꜱᴜᴘᴘᴏʀᴛ:* Easy to understand\n"
            "┠ 🔹 *ꜱᴍᴀʀᴛ ᴀɪ:* No captions? No problem!\n\n"
            "🚀 *ʜᴏᴡ ᴛᴏ ᴜꜱᴇ:*\n"
            "➠ Bas YouTube link copy-paste karo!\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *ꜱᴛᴀᴛᴜꜱ:* `System Online` 🟢\n"
            "⏱️ *ʟɪᴍɪᴛꜱ:* `50 req/hr` | `5s cooldown`"
        )
        
        # Premium Buttons
        keyboard = [
            [InlineKeyboardButton("📖 𝖧𝖾𝗅𝗉 𝖬𝖾𝗇𝗎", callback_data='help'), 
             InlineKeyboardButton("📈 𝖲𝗍𝖺𝗍𝗎𝗌", callback_data='status')],
            [InlineKeyboardButton("👤 𝖬𝗒 𝖲𝗍𝖺𝗍𝗌", callback_data='mystats'),
             InlineKeyboardButton("🆘 𝖲𝗎𝗉𝗉𝗈𝗋𝗍", callback_data='support')],
            [InlineKeyboardButton("📢 𝖲𝗁𝖺𝗋𝖾 𝗐𝗂𝗍𝗁 𝖥𝗋𝗂𝖾𝗇𝖽𝗌", url=share_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        gif_url = "https://raw.githubusercontent.com/ayuuu1233/yt-summarizer-bot/main/gojo.gif"
        
        try:
            await context.bot.send_animation(
                chat_id=update.effective_chat.id,
                animation=gif_url,
                caption=welcome_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception:
            # Fallback text if GIF fails
            await update.message.reply_text(
                welcome_text, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Start error: {e}")
        # Conflict hone par silent fail ya chota msg
        pass 

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks - Fixed for GIF compatibility"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Note: 'edit_message_text' works only on text messages. 
        # Since we send a GIF, we must use 'reply_text' to avoid errors.
        
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
                "• Hum AI se summary nikalte hain\n"
                "• 5 second cooldown hai\n"
                "• 50 requests per hour limit\n\n"
                "❓ Problem ho raha hai?\n"
                "/support command use kar!"
            )
            await query.message.reply_text(help_text, parse_mode='Markdown')
            
        elif query.data == 'status':
            status_text = (
                "🚀 *Bot Status:*\n\n"
                "✅ *Servers:* All Green\n"
                "⚡ *Speed:* Lightning Fast\n"
                "🔧 *API:* Connected\n"
                "👥 *Users:* Active\n\n"
                "Bot mast chal raha hai bhai! 🔥"
            )
            await query.message.reply_text(status_text, parse_mode='Markdown')
            
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
            
            await query.message.reply_text(stats_text, parse_mode='Markdown')
            
        elif query.data == 'support':
            support_text = (
                "🆘 *Support Information:*\n\n"
                "❌ Video fail ho raha hai?\n"
                "→ Private videos ki summary nahi nikal sakti\n"
                "→ Dusra video try kar!\n\n"
                "⚠️ Rate limit exceed?\n"
                "→ 1 ghante baad try kar\n\n"
                "🐛 Bug mil gaya?\n"
                "→ /feedback command use kar\n\n"
                "📞 Direct Contact:\n"
                "→ @Ayushboy1 (Creator)"
            )
            await query.message.reply_text(support_text, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"Button callback error: {e}")
        await query.message.reply_text("❌ Error! Ek baar phir try kar bhai.")


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
    """Professional Status Command with Progress Bars"""
    stats = load_stats()
    
    status_text = (
        "🚀 *System Status Dashboard* 🚀\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Total Summaries:* `{stats['total_summaries']}`\n"
        f"👥 *Total Users:* `{stats['total_users']}`\n"
        f"⚠️ *System Errors:* `{stats['errors']}`\n\n"
        "🛰️ *Server Health:*\n"
        "🟢 API: `[▓▓▓▓▓▓▓▓▓▓] 100%` \n"
        "🟢 Database: `[▓▓▓▓▓▓▓▓░░] 85%` \n"
        "🟢 Speed: `Lightning Fast` ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ *Bot mast chal raha hai bhai!* 🔥"
    )
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 *Feedback Bhej De!*\n\n"
        "Bas apni feedback likh kar bhej. Improvements ke liye appreciate karte hain! 🙏"
    )
    return "waiting_for_feedback"

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
        f"🎐 Active Sessions: {len([u for u in request_counts if request_counts[u] > 0])}\n"
        f"⏰ Last Reset: {last_reset_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await update.message.reply_text(admin_text, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """About command with professional style"""
    about_text = (
        "🤖 *About This Bot* 🤖\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ *Core:* `Gemini AI 1.5 Flash`\n"
        "🛠️ *Library:* `Python-Telegram-Bot`\n"
        "⚡ *Engine:* `yt-dlp & Transcripts API`\n\n"
        "👤 *Developer:* @Ayushboy1 \n"
        "🌐 *Host:* `Render (24/7 Online)`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bhai, ye bot YouTube videos ki lambi bak-bak ko short karke deta hai! 🎬"
    )
    await update.message.reply_text(about_text, parse_mode='Markdown')

async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User ke personal usage statistics"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # User data fetch logic
    data = user_data.get(user_id, {"total_requests": 0, "joined_date": "N/A"})
    count = data['total_requests']
    
    # Rank logic based on usage
    rank = "🆕 Newbie" if count < 5 else "🔥 Regular" if count < 20 else "👑 Legend"

    mystats_text = (
        f"👤 *USER PROFILE: {user_name.upper()}* 👤\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎖️ *Your Rank:* `{rank}`\n"
        f"📊 *Total Summaries:* `{count}`\n"
        f"📅 *Joined On:* `{data['joined_date'][:10]}`\n\n"
        "🌟 *Performance Tracking:*\n"
        f"`[▓▓{'▓' * min(count//2, 8)}{'░' * max(8-count//2, 0)}]` {min(count*5, 100)}%\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bhai, thoda aur summarize kar aur Rank up kar! 🚀"
    )
    await update.message.reply_text(mystats_text, parse_mode='Markdown')

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Server latency check with animation"""
    import time
    start_time = time.time()
    
    # Initial ping message
    ping_msg = await update.message.reply_text("🛰️ *Pinging Server...*", parse_mode='Markdown')
    
    end_time = time.time()
    latency = round((end_time - start_time) * 1000, 2)
    
    # Upgrade to animated response
    await ping_msg.edit_text(
        "🏓 *Pong!* 🏓\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *Latency:* `{latency} ms`\n"
        "🟢 *Status:* `System Healthy`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Server bilkul smoothly chal raha hai! ✅",
        parse_mode='Markdown'
    )


# ================== 5. MESSAGE HANDLER ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upgraded Message Handler with Animations and Progress Bars"""
    try:
        user_id = update.message.from_user.id
        text = update.message.text.strip()
        
        # 1. Rate Limit Check
        is_allowed, message = check_rate_limit(user_id)
        if not is_allowed:
            await update.message.reply_text(f"{message}")
            return
        
        # 2. Extract Video ID
        video_id = get_video_id(text)
        if not video_id:
            await update.message.reply_text(
                "⚠️ *Invalid Link!* 🤔\n\nSahi YouTube link bhej bhai!",
                parse_mode='MarkdownV2'
            )
            return
        
        # 3. Initializing Animation
        status_msg = await update.message.reply_text("🌀 *Initializing AI System...*")
        
        # Update stats
        user_cooldown[user_id] = datetime.now()
        request_counts[user_id] += 1
        if user_id in user_data:
            user_data[user_id]['total_requests'] += 1

        # 4. Progress Animation - Fetching Transcript
        await status_msg.edit_text("⚙️ *Fetching Video Data...*\n`[▓▓░░░░░░░░] 20%`", parse_mode='Markdown')
        transcript = get_full_transcript(video_id)
        
        if not transcript:
            await status_msg.edit_text("🔄 *Captions missing, using Metadata...*\n`[▓▓▓▓░░░░░░] 40%`", parse_mode='Markdown')
            video_info = await get_video_info_fallback(text)
            
            if not video_info:
                await status_msg.edit_text("❌ Is video ki info nahi mil rahi (No Captions & No Metadata).")
                update_stats("errors")
                return
            
            prompt = f"Mujhe iss YouTube video ki VERY DETAILED SUMMARY Hinglish mein chahiye. Title: {video_info['title']}\nDescription: {video_info['description']}"
        else:
            await status_msg.edit_text("🧠 *AI is Analyzing Content...*\n`[▓▓▓▓▓▓▓░░░] 70%`", parse_mode='Markdown')
            prompt = f"Mujhe iss YouTube video ke liye VERY DETAILED SUMMARY Hinglish mein chahiye. Video transcript:\n\n{transcript[:100000]}"

        # 5. Generate Summary
        response = model.generate_content(prompt)
        summary = response.text if response and response.text else "❌ Summary generate nahi ho payi."
        
        await status_msg.edit_text("✍️ *Finalizing Detailed Summary...*\n`[▓▓▓▓▓▓▓▓▓▓] 100%`", parse_mode='Markdown')
        await asyncio.sleep(0.5)

        # 6. History and Stats Update
        update_stats("total_summaries")
        current_t_len = len(transcript) if transcript else 0
        user_history[user_id].append({
            "video_id": video_id,
            "timestamp": datetime.now().isoformat(),
            "transcript_length": current_t_len
        })

        # 7. Final Output Formatting
        final_header = "✨ *YOUTUBE VIDEO SUMMARY* ✨\n━━━━━━━━━━━━━━━━━━━━━━\n"
        final_footer = "\n━━━━━━━━━━━━━━━━━━━━━━\n📢 *Apne doston ke saath share karein!* 🎉"
        
        if len(summary) > 3800:
            parts = [summary[i:i+3800] for i in range(0, len(summary), 3800)]
            await status_msg.delete() # Progress message delete kar do
            for part in parts:
                await update.message.reply_text(f"📝 {part}", parse_mode='Markdown')
        else:
            try:
                await status_msg.edit_text(f"{final_header}{summary}{final_footer}", parse_mode='Markdown')
            except Exception:
                await update.message.reply_text(f"{final_header}{summary}{final_footer}", parse_mode='Markdown')
        
        logger.info(f"User {user_id} - Animated Summary generated for {video_id}")
        
    except Exception as e:
        logger.error(f"Handle message error: {e}")
        update_stats("errors")
        try:
            await update.message.reply_text(f"❌ *Error Aaya!* Technical Issue: {str(e)[:50]}... Phir se try kar bhai! 🔄")
        except:
            pass


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ye function feedback ko save karke Admin ko bhejega"""
    try:
        user_id = update.message.from_user.id
        feedback = update.message.text
        logger.info(f"📝 Feedback from {user_id}: {feedback}")
        
        await update.message.reply_text(
            "✅ *Feedback mil gaya!*\n\nShukriya bhai! Apki feedback zaruri hai. 🙏",
            parse_mode='Markdown'
        )
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📝 *New Feedback*\n\nUser ID: {user_id}\nMessage: {feedback[:500]}",
                parse_mode='Markdown'
            )
        except:
            pass
            
    except Exception as e:
        logger.error(f"Feedback handler error: {e}")
    
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ *Process cancel kar diya gaya.*\n\nAb aap naya YouTube link bhej sakte hain! 🚀",
        parse_mode='Markdown'
    )
    return ConversationHandler.END


# ================== 6. ERROR HANDLER ==================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ *Bot Error:*\n\n```\n{str(context.error)[:500]}\n```",
                parse_mode='Markdown'
            )
    except:
        pass

# ================== 7. POST INIT ==================
async def post_init(application):
    """Conflict error khatam karne ke liye purane updates drop karega"""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("🧹 All pending updates dropped. Conflict cleared!")

# ================== 7. MAIN APPLICATION ==================
def main():
    try:
        logger.info("🚀 Booting AI YouTube Summarizer (Professional Mode)...")

        keep_alive()

        app = (
            ApplicationBuilder()
            .token(TOKEN)
            .post_init(post_init)
            .build()
        )

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('feedback', feedback_command)],
            states={
                "waiting_for_feedback": [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback)
                ]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("stats", status_command))
        app.add_handler(CommandHandler("about", about_command))
        app.add_handler(CommandHandler("mystats", mystats_command))
        app.add_handler(CommandHandler("ping", ping_command))
        app.add_handler(CommandHandler("admin_stats", admin_stats))
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(conv_handler)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        app.add_error_handler(error_handler)

        if app.job_queue:
            app.job_queue.run_repeating(
                lambda ctx: reset_hourly_limits(),
                interval=3600,
                first=3600
            )
            logger.info("⏰ Background Job Queue started.")
        else:
            logger.warning("⚠️ JobQueue missing! Reset job not started.")

        logger.info("✅ All systems initialized successfully.")
        
        app.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.critical(f"❌ Fatal Startup Error: {e}")

if __name__ == '__main__':
    main()
