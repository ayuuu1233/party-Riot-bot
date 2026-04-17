"""
main.py — Party Riot Bot V2
Contains: Setup, utils, start, message handler, callbacks, owner commands, bot runner
All game commands are imported from games.py
"""

import os
import json
import random
import asyncio
import logging
import time
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
import google.generativeai as genai
from keep_alive import keep_alive

# ================== SETUP & CONFIG ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_START_TIME = time.time()

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

OWNER_ID_STR = os.getenv("OWNER_ID")
if not OWNER_ID_STR:
    raise ValueError("❌ OWNER_ID environment variable is required!")
OWNER_ID = int(OWNER_ID_STR)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# ================== DATA FILES ==================
STATS_FILE = "party_stats.json"
CONFESS_FILE = "confessions.json"
LEADERBOARD_FILE = "leaderboard.json"
BANNED_FILE = "banned.json"
CHAT_HISTORY_FILE = "chat_history.json"
MOOD_FILE = "user_moods.json"
STREAKS_FILE = "streaks.json"
POLLS_FILE = "active_polls.json"
WARNINGS_FILE = "warnings.json"
CUSTOM_CMDS_FILE = "custom_commands.json"

# ================== UTILITY FUNCTIONS ==================
def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(filepath, data):
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Save error {filepath}: {e}")

def is_owner(user_id):
    return user_id == OWNER_ID

def is_banned(user_id):
    banned = load_json(BANNED_FILE, [])
    return user_id in banned

async def owner_only(update: Update):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text(
            "🚫 *Tu owner nahi hai bhai!*\nYe command sirf malik ke liye hai 👑",
            parse_mode='Markdown'
        )
        return False
    return True

async def check_banned(update: Update):
    if is_banned(update.effective_user.id):
        await update.message.reply_text("🔨 Tu banned hai bhai. Owner se baat kar.")
        return True
    return False

def update_leaderboard(user_id, user_name, points=1, category=None):
    lb = load_json(LEADERBOARD_FILE, {})
    uid = str(user_id)
    if uid not in lb:
        lb[uid] = {"name": user_name, "points": 0, "dares_done": 0, "truths": 0, "trivia_correct": 0}
    lb[uid]["points"] += points
    lb[uid]["name"] = user_name
    if category == "dare":
        lb[uid]["dares_done"] = lb[uid].get("dares_done", 0) + 1
    elif category == "truth":
        lb[uid]["truths"] = lb[uid].get("truths", 0) + 1
    elif category == "trivia":
        lb[uid]["trivia_correct"] = lb[uid].get("trivia_correct", 0) + 1
    save_json(LEADERBOARD_FILE, lb)

def get_leaderboard_text():
    lb = load_json(LEADERBOARD_FILE, {})
    if not lb:
        return "📊 Abhi koi data nahi! Khelo aur points kamao!"
    sorted_lb = sorted(lb.items(), key=lambda x: x[1]["points"], reverse=True)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = "👑 *PARTY RIOT V2 LEADERBOARD* 👑\n━━━━━━━━━━━━━━━━━\n"
    for i, (uid, data) in enumerate(sorted_lb[:10]):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        dares = data.get('dares_done', 0)
        trivia = data.get('trivia_correct', 0)
        text += f"{medal} *{data['name']}* — `{data['points']} pts` | 😈{dares} dares | 🧠{trivia} trivia\n"
    return text

def update_streak(user_id, user_name):
    streaks = load_json(STREAKS_FILE, {})
    uid = str(user_id)
    today = datetime.now().date().isoformat()
    if uid not in streaks:
        streaks[uid] = {"name": user_name, "streak": 1, "last_date": today, "max_streak": 1}
    else:
        last = streaks[uid].get("last_date", "")
        try:
            last_date = datetime.fromisoformat(last).date()
            diff = (datetime.now().date() - last_date).days
            if diff == 1:
                streaks[uid]["streak"] += 1
                streaks[uid]["max_streak"] = max(streaks[uid].get("max_streak", 0), streaks[uid]["streak"])
            elif diff > 1:
                streaks[uid]["streak"] = 1
        except:
            streaks[uid]["streak"] = 1
        streaks[uid]["last_date"] = today
        streaks[uid]["name"] = user_name
    save_json(STREAKS_FILE, streaks)
    return streaks[uid].get("streak", 1)

def warn_user(user_id, user_name, reason):
    warnings = load_json(WARNINGS_FILE, {})
    uid = str(user_id)
    if uid not in warnings:
        warnings[uid] = {"name": user_name, "count": 0, "reasons": []}
    warnings[uid]["count"] += 1
    warnings[uid]["reasons"].append({"reason": reason, "time": datetime.now().isoformat()})
    save_json(WARNINGS_FILE, warnings)
    return warnings[uid]["count"]

# ================== BOT PERSONALITY REPLIES ==================
BOT_PERSONALITY_REPLIES = {
    "hello": ["Heyy! 🌸 Kya scene hai aaj?", "Ayo! Party mode mein hoon! 🎉", "Namaste bhai! 😂 Kya ho raha hai?"],
    "hi": ["Hi hi hi! 👋 Kya haal hai?", "Heyyyy 🙌 Bot zinda hai!"],
    "how are you": ["Main toh full mast hoon! 🔥 Tu bata?", "Bilkul fresh! Thoda nap liya tha 😂", "Zabardast! Aaj kisi ko roast karein? 😈"],
    "thanks": ["Arre yaar mention not! 🙏", "Koi baat nahi bestie 💕", "Tere liye kuch bhi! 😂"],
    "good morning": ["Good morning! ☀️ Chai pi li? Warna neend nahi jayegi raat ko 😂", "Subah subah itni energy? Respect! 🌅"],
    "good night": ["Good night! 🌙 Sapne mein crush aaye 😏", "So ja jaldi, kal aur roast karenge 😂 Shubh raatri! 🌟"],
    "love you": ["Awww! 😳 Main toh bot hoon par dil touch ho gaya! 💕", "Aye aye 🫣 Bot ko pyaar? Cute hai!"],
    "bored": ["Bored hai? /truth khelo ya /dare le! 😈", "Chal /wyr khel, kuch toh tike ga! 🤔", "Teri boredom ka ilaaj mere paas hai — /roast? 😂"],
    "sad": ["Aye yaar 😢 Kya hua? Bata na! Main sun raha hoon 🤍", "Sad mat ho! Party mein aao, sab bhool jaoge 🎉"],
}

# ================== START COMMAND ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await check_banned(update): return
        user_name = update.effective_user.first_name
        chat_id = update.effective_chat.id

        stats = load_json(STATS_FILE, {"total_users": 0, "total_commands": 0})
        stats["total_users"] += 1
        stats["total_commands"] += 1
        save_json(STATS_FILE, stats)

        msg1 = await context.bot.send_message(chat_id=chat_id, text="🌸 *Waking up the party spirits...*", parse_mode='Markdown')
        await asyncio.sleep(0.8)
        loader = await context.bot.send_message(chat_id=chat_id, text="🎉 `Loading V2...`", parse_mode='Markdown')
        frames = [
            "🎊 `Party Mode V2: Activating...`",
            "🤖 `AI Brain: Connecting...`",
            "💘 `Couple Matcher: Online...`",
            "😈 `Roast Engine: Charging...`",
            "🧠 `Trivia Bank: Loading...`",
            "🔮 `Fortune Teller: Awakening...`",
            "🎉 `SYSTEM V2 READY!`"
        ]
        for frame in frames:
            await loader.edit_text(frame, parse_mode='Markdown')
            await asyncio.sleep(0.5)

        await msg1.delete()
        await loader.delete()

        welcome_text = (
            f"🌸 *Heyy {user_name}-senpai!* Welcome to the chaos V2! 🎉\n\n"
            "╔══════════════════════════╗\n"
            "║  🎊 *PARTY RIOT BOT V2* 🎊  ║\n"
            "╚══════════════════════════╝\n\n"
            "🎮 *Game Commands:*\n"
            "┠ 🔴 /truth — Spicy sawaal!\n"
            "┠ 🟠 /dare — Crazy challenge!\n"
            "┠ 🍾 /spin — Bottle spin karo!\n"
            "┠ 💘 /couple — Love matching!\n"
            "┠ 🤔 /wyr — Would You Rather\n"
            "┠ 😂 /roast @user — AI Roast!\n"
            "┠ 💌 /confess — Anonymous confession\n"
            "┠ ⚡ /shipname — Ship banao!\n"
            "┠ 🎭 /rate @user — Rate karo!\n"
            "┠ 🃏 /nhie — Never Have I Ever\n"
            "┠ 🧠 /trivia — Test your knowledge!\n\n"
            "✨ *NEW V2 Commands:*\n"
            "┠ 🔮 /fortune — Aaj ka bhavishya!\n"
            "┠ 🎱 /8ball [question] — Magic 8 Ball!\n"
            "┠ ♈ /zodiac [sign] — Rashifal!\n"
            "┠ 💬 /compliment @user — Tarif karo!\n"
            "┠ 🎭 /mood — Apna mood set karo!\n"
            "┠ 📊 /poll [question] — Group poll!\n"
            "┠ 🔥 /streak — Daily streak check!\n"
            "┠ 🤖 /ask [question] — AI se pooch!\n"
            "┠ 🎲 /rng [max] — Random number!\n"
            "┠ ⚔️ /battle @user — Epic battle!\n"
            "┠ 💰 /economy — Check balance!\n"
            "┠ 🌍 /fact — Random cool fact!\n\n"
            "📊 *Info:*\n"
            "┠ 🏆 /leaderboard | 📈 /stats\n"
            "┠ ⚡ /ping | 💫 /alive | 📖 /help\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 _Main ab messages pe bhi react karta hoon!_\n"
            "📊 *Status:* `Online & Upgraded` 🟢"
        )

        keyboard = [
            [InlineKeyboardButton("🎮 Truth", callback_data='truth'),
             InlineKeyboardButton("😈 Dare", callback_data='dare'),
             InlineKeyboardButton("🧠 Trivia", callback_data='trivia')],
            [InlineKeyboardButton("🍾 Spin", callback_data='spin'),
             InlineKeyboardButton("💘 Couple", callback_data='couple'),
             InlineKeyboardButton("🔮 Fortune", callback_data='fortune')],
            [InlineKeyboardButton("🏆 Leaderboard", callback_data='leaderboard'),
             InlineKeyboardButton("📖 Help", callback_data='help')]
        ]

        video_url = "https://files.catbox.moe/dlg0rb.mp4"
        try:
            await context.bot.send_video(
                chat_id=chat_id, video=video_url, caption=welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )
        except:
            await context.bot.send_message(
                chat_id=chat_id, text=welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Start error: {e}")


# ================== MESSAGE HANDLER (AI) ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if await check_banned(update): return

    msg = update.message.text.lower().strip()
    user_name = update.effective_user.first_name
    bot_username = context.bot.username.lower() if context.bot.username else ""

    is_private = update.effective_chat.type == "private"
    is_mentioned = f"@{bot_username}" in msg or "party riot" in msg
    is_reply_to_bot = (
        update.message.reply_to_message and
        update.message.reply_to_message.from_user and
        update.message.reply_to_message.from_user.is_bot
    )

    # Keyword quick replies
    for keyword, replies in BOT_PERSONALITY_REPLIES.items():
        if keyword in msg:
            await asyncio.sleep(0.5)
            await update.message.reply_text(random.choice(replies))
            return

    # AI reply for private/mention/reply
    if is_private or is_mentioned or is_reply_to_bot:
        clean_msg = msg.replace(f"@{bot_username}", "").strip()
        if not clean_msg or len(clean_msg) < 2:
            return
        try:
            typing_msg = await update.message.reply_text("🤖 _Soch raha hoon..._", parse_mode='Markdown')
            history_data = load_json(CHAT_HISTORY_FILE, {})
            uid = str(update.effective_user.id)
            user_history = history_data.get(uid, [])[-6:]
            history_text = "".join([f"User: {h['user']}\nBot: {h['bot']}\n" for h in user_history])
            prompt = f"""Tu ek fun, desi party bot hai jiska naam "Party Riot Bot V2" hai.
Tu Hinglish mein baat karta hai (Hindi + English mix).
Teri personality: funny, sarcastic but caring, energetic, emojis use karta hai, desi references deta hai.
Tu kabhi boring nahi hota. Short responses (2-4 lines max).

Previous conversation:
{history_text}

User ({user_name}) ne kaha: {clean_msg}

Respond as the party bot in Hinglish, fun aur friendly way mein. No offensive content."""
            response = model.generate_content(prompt)
            bot_reply = response.text.strip()

            if uid not in history_data:
                history_data[uid] = []
            history_data[uid].append({"user": clean_msg, "bot": bot_reply})
            history_data[uid] = history_data[uid][-20:]
            save_json(CHAT_HISTORY_FILE, history_data)
            await typing_msg.edit_text(bot_reply)
        except Exception as e:
            logger.error(f"Message handler AI error: {e}")
            try:
                await typing_msg.edit_text("Yaar dimag thoda load pe hai abhi 😅 Thoda baad try karo!")
            except:
                pass


# ================== STATS & INFO COMMANDS ==================
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    await update.message.reply_text(get_leaderboard_text(), parse_mode='Markdown')

async def economy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        user = update.effective_user
        lb = load_json(LEADERBOARD_FILE, {})
        uid = str(user.id)
        if uid in lb:
            data = lb[uid]
            rank = sorted(lb.keys(), key=lambda x: lb[x]["points"], reverse=True).index(uid) + 1
            await update.message.reply_text(
                f"💰 *{user.first_name}'s ECONOMY* 💰\n━━━━━━━━━━━━━━━━━\n\n"
                f"🏆 Rank: `#{rank}`\n"
                f"💎 Points: `{data['points']}`\n"
                f"😈 Dares Done: `{data.get('dares_done', 0)}`\n"
                f"🔴 Truths Answered: `{data.get('truths', 0)}`\n"
                f"🧠 Trivia Correct: `{data.get('trivia_correct', 0)}`\n"
                f"━━━━━━━━━━━━━━━━━\n_Aur khelo, aur points kamao!_ 🎮",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"💰 *{user.first_name}* — Abhi 0 points!\n\n/truth, /dare, /trivia khelo aur points kamao! 🎮",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Economy error: {e}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    stats = load_json(STATS_FILE, {"total_users": 0, "total_commands": 0})
    confessions = load_json(CONFESS_FILE, [])
    lb = load_json(LEADERBOARD_FILE, {})
    text = (
        "📊 *PARTY RIOT V2 - STATS* 📊\n━━━━━━━━━━━━━━━━━\n"
        f"👥 *Total Users:* `{stats['total_users']}`\n"
        f"⚡ *Commands Used:* `{stats['total_commands']}`\n"
        f"💌 *Confessions:* `{len(confessions)}`\n"
        f"🏆 *Players on Board:* `{len(lb)}`\n"
        f"🤖 *Version:* `V2 - Upgraded!`\n"
        f"🟢 *Status:* `Online & Partying!`\n"
        "━━━━━━━━━━━━━━━━━\n🎉 _V2 chal raha hai full speed!_ 🔥"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_t = time.time()
    msg = await update.message.reply_text("🏓 Pong chalc rahi hai...")
    end_t = time.time()
    latency = round((end_t - start_t) * 1000, 2)
    await msg.edit_text(
        f"🏓 *PONG!*\n\n⚡ Latency: `{latency}ms`\n🟢 Status: `Online`\n😂 Mood: `V2 Party Mode!`",
        parse_mode='Markdown'
    )

async def alive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime_seconds = time.time() - BOT_START_TIME
    uptime = str(timedelta(seconds=int(uptime_seconds)))
    await update.message.reply_text(
        f"🌸 *PARTY RIOT V2 - ALIVE!* 🌸\n━━━━━━━━━━━━━━━━━\n"
        f"✅ *Status:* `Fully Operational`\n"
        f"⏱️ *Uptime:* `{uptime}`\n"
        f"🎉 *Version:* `V2 — Upgraded!`\n"
        f"🤖 *AI:* `Gemini 1.5 Flash`\n"
        f"━━━━━━━━━━━━━━━━━\nZinda hoon bhai, full josh V2 mein! 🔥",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    text = (
        "📖 *PARTY RIOT V2 - HELP* 📖\n━━━━━━━━━━━━━━━━━\n\n"
        "🎮 *Classic Games:*\n"
        "`/truth` `/dare` `/spin` `/couple`\n"
        "`/roast @user` `/confess [text]`\n"
        "`/ngl [msg]` `/wyr` `/shipname`\n"
        "`/rate @user` `/leaderboard`\n\n"
        "✨ *New V2 Commands:*\n"
        "`/fortune` — Aaj ka bhavishya\n"
        "`/8ball [q]` — Magic 8 ball\n"
        "`/zodiac [sign]` — Rashifal\n"
        "`/compliment @user` — Tarif\n"
        "`/mood [text]` — Mood set\n"
        "`/ask [question]` — AI se pooch\n"
        "`/battle @user` — Epic battle\n"
        "`/fact` — Random cool fact\n"
        "`/nhie` — Never Have I Ever\n"
        "`/trivia` — Quiz with points\n"
        "`/rng [max]` — Random number\n"
        "`/streak` — Daily streak\n"
        "`/economy` — Points check\n"
        "`/poll [question]` — Group poll\n\n"
        "📊 *Info:*\n"
        "`/start` `/help` `/stats` `/ping` `/alive`\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "🤖 _Mujhse baat bhi kar sakta hai — main reply karta hoon!_ 😊"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


# ================== OWNER COMMANDS ==================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    if not context.args:
        await update.message.reply_text("Usage: `/broadcast [message]`", parse_mode='Markdown')
        return
    msg = " ".join(context.args)
    await update.message.reply_text(
        f"📢 *OWNER BROADCAST* 📢\n━━━━━━━━━━━━━━━━━\n\n{msg}\n\n━━━━━━━━━━━━━━━━━\n— _Party Riot Bot V2 Owner_ 👑",
        parse_mode='Markdown'
    )

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    if not context.args:
        await update.message.reply_text("Usage: `/ban [user_id]`", parse_mode='Markdown')
        return
    try:
        target_id = int(context.args[0])
        banned = load_json(BANNED_FILE, [])
        if target_id not in banned:
            banned.append(target_id)
            save_json(BANNED_FILE, banned)
            await update.message.reply_text(f"🔨 *User `{target_id}` ban!*", parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ Already banned.", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ Valid user ID daal!")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    if not context.args:
        await update.message.reply_text("Usage: `/unban [user_id]`", parse_mode='Markdown')
        return
    try:
        target_id = int(context.args[0])
        banned = load_json(BANNED_FILE, [])
        if target_id in banned:
            banned.remove(target_id)
            save_json(BANNED_FILE, banned)
            await update.message.reply_text(f"✅ *User `{target_id}` unban!*", parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ Not banned.", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ Valid user ID daal!")

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    if not context.args:
        await update.message.reply_text("Usage: `/warn [user_id] [reason]`", parse_mode='Markdown')
        return
    try:
        target_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason given"
        count = warn_user(target_id, f"User#{target_id}", reason)
        await update.message.reply_text(
            f"⚠️ *User `{target_id}` warned!*\nReason: _{reason}_\nTotal warnings: `{count}`",
            parse_mode='Markdown'
        )
        if count >= 3:
            banned = load_json(BANNED_FILE, [])
            if target_id not in banned:
                banned.append(target_id)
                save_json(BANNED_FILE, banned)
                await update.message.reply_text("🔨 Auto-banned after 3 warnings!", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ Valid user ID daal!")

async def clear_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    save_json(LEADERBOARD_FILE, {})
    await update.message.reply_text("🗑️ *Leaderboard cleared!*", parse_mode='Markdown')

async def clear_confessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    save_json(CONFESS_FILE, [])
    await update.message.reply_text("🗑️ *Confessions deleted!*", parse_mode='Markdown')

async def owner_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    stats = load_json(STATS_FILE, {})
    confessions = load_json(CONFESS_FILE, [])
    banned = load_json(BANNED_FILE, [])
    lb = load_json(LEADERBOARD_FILE, {})
    warnings = load_json(WARNINGS_FILE, {})
    uptime = str(timedelta(seconds=int(time.time() - BOT_START_TIME)))
    await update.message.reply_text(
        f"🔐 *OWNER DASHBOARD V2* 🔐\n━━━━━━━━━━━━━━━━━\n"
        f"👥 Users: `{stats.get('total_users', 0)}`\n"
        f"⚡ Commands: `{stats.get('total_commands', 0)}`\n"
        f"💌 Confessions: `{len(confessions)}`\n"
        f"🔨 Banned: `{len(banned)}`\n"
        f"⚠️ Warned Users: `{len(warnings)}`\n"
        f"🏆 Board Entries: `{len(lb)}`\n"
        f"⏱️ Uptime: `{uptime}`\n"
        f"━━━━━━━━━━━━━━━━━\n🕐 `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        parse_mode='Markdown'
    )

async def add_truth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    if not context.args:
        await update.message.reply_text("Usage: `/addtruth [question]`", parse_mode='Markdown')
        return
    from games import TRUTH_QUESTIONS
    TRUTH_QUESTIONS.append(" ".join(context.args))
    await update.message.reply_text(f"✅ *Truth added!* Total: `{len(TRUTH_QUESTIONS)}`", parse_mode='Markdown')

async def add_dare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    if not context.args:
        await update.message.reply_text("Usage: `/adddare [challenge]`", parse_mode='Markdown')
        return
    from games import DARE_CHALLENGES
    DARE_CHALLENGES.append(" ".join(context.args))
    await update.message.reply_text(f"✅ *Dare added!* Total: `{len(DARE_CHALLENGES)}`", parse_mode='Markdown')

async def send_as_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: `/say [chat_id] [message]`", parse_mode='Markdown')
        return
    try:
        chat_id = context.args[0]
        msg = " ".join(context.args[1:])
        await context.bot.send_message(chat_id=chat_id, text=msg)
        await update.message.reply_text("✅ Sent!", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    if not context.args:
        await update.message.reply_text("Usage: `/announce [message]`", parse_mode='Markdown')
        return
    msg = " ".join(context.args)
    await update.message.reply_text(
        f"📣 *PARTY RIOT BOT ANNOUNCEMENT* 📣\n{'━' * 20}\n\n🔔 {msg}\n\n{'━' * 20}\n_— Party Riot Bot V2_ 🎉",
        parse_mode='Markdown'
    )


# ================== CALLBACK HANDLER ==================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from games import (
        TRUTH_QUESTIONS, DARE_CHALLENGES, WYR_QUESTIONS,
        TRIVIA_QUESTIONS, NEVER_HAVE_I_EVER, FORTUNE_COOKIES, ROAST_LINES
    )
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data == 'truth':
        question = random.choice(TRUTH_QUESTIONS)
        keyboard = [[
            InlineKeyboardButton("🔴 Aur Truth!", callback_data='truth'),
            InlineKeyboardButton("🟠 Dare!", callback_data='dare'),
            InlineKeyboardButton("✅ Answered!", callback_data='truth_answered')
        ]]
        await query.message.reply_text(
            f"🔴 *TRUTH!*\n━━━━━━━━━━━━━━━━━\n🎯 *{user.first_name}* ko:\n\n💬 _{question}_\n\n━━━━━━━━━━━━━━━━━\nSach bol! 😏",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == 'dare':
        challenge = random.choice(DARE_CHALLENGES)
        keyboard = [[
            InlineKeyboardButton("✅ Done! +10pts", callback_data='dare_done'),
            InlineKeyboardButton("🔄 New Dare", callback_data='dare'),
            InlineKeyboardButton("🔴 Truth!", callback_data='truth')
        ]]
        await query.message.reply_text(
            f"🟠 *DARE!*\n━━━━━━━━━━━━━━━━━\n😈 *{user.first_name}* ko:\n\n⚡ _{challenge}_\n\n━━━━━━━━━━━━━━━━━\nKar sakta hai? 😂",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == 'dare_done':
        update_leaderboard(user.id, user.first_name, 10, "dare")
        streak = update_streak(user.id, user.first_name)
        await query.message.reply_text(
            f"✅ *{user.first_name}* ne dare complete kiya!\n🏆 *+10 points!*\n🔥 Streak: `{streak} days`\n\n_Legend hai bhai!_ 🔥",
            parse_mode='Markdown'
        )

    elif data == 'truth_answered':
        update_leaderboard(user.id, user.first_name, 2, "truth")
        await query.message.reply_text(
            f"👏 *{user.first_name}* ne sach bola!\n🏆 *+2 points!*\n_Brave soul!_ 😊",
            parse_mode='Markdown'
        )

    elif data == 'spin':
        funny_names = ["Sharma Ji Ka Beta 🤓", "Chai Wala ☕", "Neend Ki Dushman 😴", "Bakwaas Master 🗣️", "Group Ka Ghost 👻"]
        picked = random.choice(funny_names)
        await query.message.reply_text(
            f"🍾 *Bottle ruki!*\n\n🎯 *{picked}* — ab tumhari baari! 😈",
            parse_mode='Markdown'
        )

    elif data == 'couple':
        names = ["Rahul", "Priya", "Arjun", "Sneha", "Riya", "Dev", "Kavya", "Rohan"]
        p1 = random.choice(names)
        names.remove(p1)
        p2 = random.choice(names)
        score = random.randint(60, 100)
        bar = "▓" * (score // 10) + "░" * (10 - score // 10)
        await query.message.reply_text(
            f"💘 *{p1}* + *{p2}* = `{score}%`\n`[{bar}]`\n\n_Ship: {p1[:3]}{p2[:3]}_ 😂",
            parse_mode='Markdown'
        )

    elif data == 'ship_random':
        names = ["Rahul", "Priya", "Arjun", "Sneha", "Dev", "Meera"]
        n1 = random.choice(names)
        names.remove(n1)
        n2 = random.choice(names)
        ship = n1[:len(n1)//2+1] + n2[len(n2)//2:]
        await query.message.reply_text(f"⚡ *Ship:* `{ship}`\n👫 {n1} + {n2} = 💕", parse_mode='Markdown')

    elif data == 'fortune':
        fortune = random.choice(FORTUNE_COOKIES)
        lucky = random.randint(1, 99)
        await query.message.reply_text(
            f"🔮 *YOUR FORTUNE*\n━━━━━━━━━━━━━━━━━\n\n_{fortune}_\n\n🍀 Lucky Number: `{lucky}`",
            parse_mode='Markdown'
        )

    elif data == 'trivia':
        q_data = random.choice(TRIVIA_QUESTIONS)
        options = q_data["options"]
        keyboard = [[InlineKeyboardButton(opt, callback_data=f'trivia_{i}_{q_data["answer"]}_{user.id}')] for i, opt in enumerate(options)]
        await query.message.reply_text(
            f"{q_data['q']}\n\n_Sahi jawab do!_ 🏆",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith('trivia_'):
        parts = data.split('_')
        chosen = int(parts[1])
        correct = int(parts[2])
        q_data = next((q for q in TRIVIA_QUESTIONS if q["answer"] == correct), None)
        if chosen == correct:
            update_leaderboard(user.id, user.first_name, 15, "trivia")
            explanation = q_data["explanation"] if q_data else "Sahi hai!"
            await query.message.reply_text(
                f"✅ *{user.first_name}* CORRECT! 🎉\n+15 points!\n\n📖 _{explanation}_",
                parse_mode='Markdown'
            )
        else:
            explanation = q_data["explanation"] if q_data else "Galat jawab!"
            await query.message.reply_text(
                f"❌ *{user.first_name}* galat! 😅\n\n📖 _{explanation}_",
                parse_mode='Markdown'
            )

    elif data == 'leaderboard':
        await query.message.reply_text(get_leaderboard_text(), parse_mode='Markdown')

    elif data == 'help':
        text = (
            "📖 *Quick Help V2:*\n\n"
            "Classic: `/truth` `/dare` `/spin` `/couple`\n"
            "New V2: `/fortune` `/8ball` `/zodiac` `/battle`\n"
            "AI: `/ask` `/roast` `/compliment` `/fact`\n"
            "Stats: `/economy` `/streak` `/leaderboard`\n\n"
            "_/help ke liye full menu!_ 🎉"
        )
        await query.message.reply_text(text, parse_mode='Markdown')

    elif data == 'fact':
        try:
            prompt = "Give one mind-blowing fact in Hinglish. 2 sentences. Emojis."
            response = model.generate_content(prompt)
            fact = response.text
        except:
            fact = "Insaan ke body mein itna iron hai ki ek choti nail ban sakti hai! 🔩"
        keyboard = [[InlineKeyboardButton("🌍 Aur Fact!", callback_data='fact')]]
        await query.message.reply_text(
            f"🌍 *RANDOM FACT*\n━━━━━━━━━━━━━━━━━\n\n{fact}",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == 'nhie':
        statement = random.choice(NEVER_HAVE_I_EVER)
        keyboard = [[
            InlineKeyboardButton("✅ Maine kiya!", callback_data='nhie_done'),
            InlineKeyboardButton("❌ Nahi kiya", callback_data='nhie_notdone'),
            InlineKeyboardButton("🔄 Next!", callback_data='nhie')
        ]]
        await query.message.reply_text(
            f"🃏 *NEVER HAVE I EVER*\n\n_{statement}_\n\n_Honestly jawab do!_ 😏",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == 'nhie_done':
        update_leaderboard(user.id, user.first_name, 3)
        await query.answer(f"😮 {user.first_name} ne kiya! +3 pts!", show_alert=True)

    elif data == 'nhie_notdone':
        await query.answer(f"😇 {user.first_name} ne nahi kiya! Innocent!", show_alert=True)

    elif data.startswith('mood_'):
        mood_map = {
            'mood_happy': "😄 Happy", 'mood_sad': "😢 Sad",
            'mood_angry': "😠 Angry", 'mood_tired': "😴 Tired",
            'mood_hype': "🔥 Hype", 'mood_meh': "😐 Meh"
        }
        mood_text = mood_map.get(data, "Unknown")
        moods = load_json(MOOD_FILE, {})
        moods[str(user.id)] = {"name": user.first_name, "mood": mood_text, "time": datetime.now().isoformat()}
        save_json(MOOD_FILE, moods)
        await query.message.reply_text(
            f"🎭 *{user.first_name}'s mood set to:* {mood_text}\n\n_Bot note kar liya!_ 📝",
            parse_mode='Markdown'
        )

    elif data.startswith('wyr_'):
        await query.message.reply_text(
            f"*{user.first_name}* ne choose kiya! 😂\n_Interesting choice!_ 🤔",
            parse_mode='Markdown'
        )

    elif data.startswith('poll_'):
        option = data.replace('poll_', '')
        await query.answer(f"Voted: {option}!", show_alert=False)
        await query.message.reply_text(
            f"📊 *{user.first_name}* ne vote diya: `{option}`",
            parse_mode='Markdown'
        )

    elif data.startswith('confess_react_'):
        await query.answer("React recorded! 💕", show_alert=False)

    elif data.startswith('roast_'):
        target = data.replace('roast_', '')
        try:
            prompt = f"New brutal funny Hinglish roast for '{target}'. 4 lines. Comedy only. Emojis."
            response = model.generate_content(prompt)
            roast_text = response.text
        except:
            roast_text = random.choice(ROAST_LINES)
        await query.message.reply_text(
            f"🔥 *ROAST V2: {target}*\n━━━━━━━━━━━━━━━━━\n\n{roast_text}\n\n😂 _Pyaar se!_",
            parse_mode='Markdown'
        )


# ================== ERROR HANDLER ==================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"⚠️ *Bot Error V2:*\n```\n{str(context.error)[:400]}\n```",
            parse_mode='Markdown'
        )
    except:
        pass

async def post_init(application):
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Webhook cleared!")


# ================== MAIN ==================
def main():
    from games import (
        truth, dare, spin_bottle, couple_match, would_you_rather, roast,
        confess, ship_name, rate_user, ngl_command, never_have_i_ever,
        trivia_command, fortune_command, eight_ball, zodiac_command,
        compliment_command, mood_command, streak_command, ask_ai,
        random_number, battle_command, fact_command, poll_command
    )

    logger.info("🎉 Booting Party Riot Bot V2...")
    keep_alive()

    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    # Classic game commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("truth", truth))
    app.add_handler(CommandHandler("dare", dare))
    app.add_handler(CommandHandler("spin", spin_bottle))
    app.add_handler(CommandHandler("couple", couple_match))
    app.add_handler(CommandHandler("wyr", would_you_rather))
    app.add_handler(CommandHandler("roast", roast))
    app.add_handler(CommandHandler("confess", confess))
    app.add_handler(CommandHandler("ngl", ngl_command))
    app.add_handler(CommandHandler("shipname", ship_name))
    app.add_handler(CommandHandler("rate", rate_user))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("nhie", never_have_i_ever))

    # New V2 commands
    app.add_handler(CommandHandler("fortune", fortune_command))
    app.add_handler(CommandHandler("8ball", eight_ball))
    app.add_handler(CommandHandler("zodiac", zodiac_command))
    app.add_handler(CommandHandler("compliment", compliment_command))
    app.add_handler(CommandHandler("mood", mood_command))
    app.add_handler(CommandHandler("streak", streak_command))
    app.add_handler(CommandHandler("ask", ask_ai))
    app.add_handler(CommandHandler("rng", random_number))
    app.add_handler(CommandHandler("battle", battle_command))
    app.add_handler(CommandHandler("fact", fact_command))
    app.add_handler(CommandHandler("trivia", trivia_command))
    app.add_handler(CommandHandler("economy", economy_command))
    app.add_handler(CommandHandler("poll", poll_command))

    # Info commands
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("alive", alive_command))

    # Owner commands
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("warn", warn_command))
    app.add_handler(CommandHandler("clearboard", clear_leaderboard))
    app.add_handler(CommandHandler("clearconfess", clear_confessions))
    app.add_handler(CommandHandler("ownerstats", owner_stats))
    app.add_handler(CommandHandler("addtruth", add_truth))
    app.add_handler(CommandHandler("adddare", add_dare))
    app.add_handler(CommandHandler("say", send_as_bot))
    app.add_handler(CommandHandler("announce", announce_command))

    # Message handler (MUST be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Callback buttons
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)

    logger.info("✅ Party Riot Bot V2 Ready! Let's go! 🎉")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
    
