import os
import re
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
    CallbackQueryHandler, filters, ContextTypes, ConversationHandler
)
import google.generativeai as genai
from keep_alive import keep_alive

# ================== 1. SETUP & CONFIG ==================
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

# ================== 2. DATA FILES ==================
STATS_FILE = "party_stats.json"
CONFESS_FILE = "confessions.json"
LEADERBOARD_FILE = "leaderboard.json"
BANNED_FILE = "banned.json"

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

# ================== 3. STATIC DATA ==================
TRUTH_QUESTIONS = [
    "Kabhi kisi ko secretly like kiya hai group mein? 👀",
    "Aaj tak ka sabse embarrassing moment kya tha? 😂",
    "Crush ko kabhi dekh ke ignore kiya hai? 🙈",
    "Last time kab roya/royi thay? Kyu? 😭",
    "Sabse bada jhooth kya bola hai life mein? 🤥",
    "Kisi ke baare mein galat gossip ki hai kabhi? 👀",
    "Sochte kya ho jab akele hote ho? 🌙",
    "Pehli crush kaun thi? First name bata 😏",
    "Kabhi class mein copy ki hai? Kitni baar? 📚",
    "Sabse weird sapna kya aaya tha kabhi? 💭",
    "Agar ek din invisible ho jao toh kya karoge? 😈",
    "Phone lock kyun hai? Kya chhupa raha/rahi ho? 🔐",
    "Kisi ko block kiya hai? Kyun? 😶",
    "Khud ko 1-10 mein looks mein kitna doge? 😂",
    "Aaj tak sabse bada prank kya khela hai? 🤣",
]

DARE_CHALLENGES = [
    "Abhi group mein ek cheesy pickup line bhejo! 😂",
    "Khud ki voice note bhejo 'I am the best' 10 baar bol ke 🎤",
    "Next 10 minutes tak sirf emoji mein reply karo 🐸",
    "Kisi bhi contact ko 'I miss you' message karo aur screenshot bhejo 😈",
    "Apna most embarrassing photo bhejo group mein 📸",
    "Abhi uthke 10 jumping jacks karo aur count karo bolte hue 🏋️",
    "Group ke kisi ek member ki tarif karo 5 lines mein 💐",
    "Apna favorite song ka 15 second voice note bhejo 🎵",
    "Aaj raat sone se pehle kisi unknown number ko 'hi' karo 👻",
    "Khud ko roast karo 3 lines mein, funny wala 😂",
    "Group mein ek shayari bhejo abhi ke abhi 📝",
    "Apna secret talent abhi prove karo group mein 🎭",
]

WYR_QUESTIONS = [
    "🤔 Would You Rather:\nA) Hamesha jhooth pakda jaye\nB) Kabhi sach na bol pao",
    "🤔 Would You Rather:\nA) Bina phone ke 1 saal\nB) Bina dost ke 1 saal",
    "🤔 Would You Rather:\nA) Sabke thoughts read kar pao\nB) Future dekh pao",
    "🤔 Would You Rather:\nA) Famous ho par broke ho\nB) Rich ho par unknown",
    "🤔 Would You Rather:\nA) Udd sako\nB) Invisible ho sako",
    "🤔 Would You Rather:\nA) Hamesha dance karte raho\nB) Hamesha gaate raho",
    "🤔 Would You Rather:\nA) 10 saal pehle wapas jao\nB) 10 saal aage chale jao",
]

ROAST_LINES = [
    "Bhai tera wifi ka signal teri life se zyada strong hai! 📶",
    "Teri personality itni bland hai ki unsalted chips bhi interesting lage tere saamne! 🍟",
    "Tu itna slow hai ki kachhua bhi tera speed dekh ke hasega! 🐢",
    "Bhai tera fashion sense dekh ke kapde khud rona lagein! 👗",
    "Teri jokes itni purani hain ki Wikipedia pe bhi nahi milti! 📖",
]

# ================== 4. HELPER FUNCTIONS ==================
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

def update_leaderboard(user_id, user_name, points=1):
    lb = load_json(LEADERBOARD_FILE, {})
    uid = str(user_id)
    if uid not in lb:
        lb[uid] = {"name": user_name, "points": 0, "dares_done": 0}
    lb[uid]["points"] += points
    lb[uid]["name"] = user_name
    save_json(LEADERBOARD_FILE, lb)

def get_leaderboard_text():
    lb = load_json(LEADERBOARD_FILE, {})
    if not lb:
        return "📊 Abhi koi data nahi! Khelo aur points kamao!"
    
    sorted_lb = sorted(lb.items(), key=lambda x: x[1]["points"], reverse=True)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    text = "👑 *PARTY RIOT LEADERBOARD* 👑\n━━━━━━━━━━━━━━━━━\n"
    
    for i, (uid, data) in enumerate(sorted_lb[:10]):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        text += f"{medal} *{data['name']}* — `{data['points']} pts`\n"
    
    return text

# ================== 5. START COMMAND ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if await check_banned(update): return

        user_name = update.effective_user.first_name
        chat_id = update.effective_chat.id

        # Stats update
        stats = load_json(STATS_FILE, {"total_users": 0, "total_commands": 0})
        stats["total_users"] += 1
        stats["total_commands"] += 1
        save_json(STATS_FILE, stats)

        # Cinematic start sequence
        msg1 = await context.bot.send_message(
            chat_id=chat_id,
            text="🌸 *Waking up the party spirits...*",
            parse_mode='Markdown',
            message_effect_id="5104841245755180586"
        )
        await asyncio.sleep(0.8)

        loader = await context.bot.send_message(chat_id=chat_id, text="🎉 `Loading...`", parse_mode='Markdown')
        frames = [
            "🎊 `Party Mode: Activating...`",
            "💘 `Couple Matcher: Online...`",
            "😈 `Roast Engine: Charging...`",
            "🎉 `SYSTEM READY!`"
        ]
        for frame in frames:
            await loader.edit_text(frame, parse_mode='Markdown')
            await asyncio.sleep(0.6)

        await msg1.delete()
        await loader.delete()

        welcome_text = (
            f"🌸 *Heyy {user_name}-senpai!* Welcome to the chaos! 🎉\n\n"
            "╔══════════════════════╗\n"
            "║  🎊 *PARTY RIOT BOT* 🎊  ║\n"
            "╚══════════════════════╝\n\n"
            "🎮 *Game Commands:*\n"
            "┠ 🔴 /truth — Spicy sawaal!\n"
            "┠ 🟠 /dare — Crazy challenge!\n"
            "┠ 🍾 /spin — Bottle spin karo!\n"
            "┠ 💘 /couple — Love matching!\n"
            "┠ 🤔 /wyr — Would You Rather\n"
            "┠ 😂 /roast @user — Roast!\n"
            "┠ 💌 /confess — Anonymous dil ki baat\n"
            "┠ ⚡ /shipname — Ship banao!\n"
            "┠ 🎭 /rate @user — Rate karo!\n\n"
            "📊 *Other Commands:*\n"
            "┠ 🏆 /leaderboard — Top players\n"
            "┠ 📈 /stats — Bot stats\n"
            "┠ ⚡ /ping — Bot ping\n"
            "┠ 💫 /alive — Bot status\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *Status:* `Online` 🟢\n"
            "🌸 *Mood:* `Full Crazy Mode` 😂"
        )

        keyboard = [
            [InlineKeyboardButton("🎮 Play Truth", callback_data='truth'),
             InlineKeyboardButton("😈 Play Dare", callback_data='dare')],
            [InlineKeyboardButton("🍾 Spin Bottle", callback_data='spin'),
             InlineKeyboardButton("💘 Match Couple", callback_data='couple')],
            [InlineKeyboardButton("🏆 Leaderboard", callback_data='leaderboard'),
             InlineKeyboardButton("📖 Help", callback_data='help')]
        ]

        video_url = "https://files.catbox.moe/nywp1r.mp4"

        try:
            await context.bot.send_video(
                chat_id=chat_id,
                video=video_url,
                caption=welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except:
            await context.bot.send_message(
                chat_id=chat_id,
                text=welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Start error: {e}")


# ================== 6. GAME COMMANDS ==================
async def truth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        question = random.choice(TRUTH_QUESTIONS)
        user = update.effective_user.first_name

        text = (
            f"🔴 *TRUTH TIME!* 🔴\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🎯 *{user}* ko yeh poochha gaya:\n\n"
            f"💬 _{question}_\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"Sach bol de bhai, koi judge nahi karega... ya karega? 😏"
        )
        keyboard = [[
            InlineKeyboardButton("🔴 Aur Truth!", callback_data='truth'),
            InlineKeyboardButton("🟠 Switch to Dare", callback_data='dare')
        ]]
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        update_leaderboard(update.effective_user.id, update.effective_user.first_name, 1)
        
    except Exception as e:
        logger.error(f"Truth error: {e}")


async def dare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        challenge = random.choice(DARE_CHALLENGES)
        user = update.effective_user.first_name

        text = (
            f"🟠 *DARE TIME!* 🟠\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"😈 *{user}* ko yeh dare mila:\n\n"
            f"⚡ _{challenge}_\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"Complete kiya toh 10 points! Nahi kiya toh... sharam aani chahiye! 😂"
        )
        keyboard = [[
            InlineKeyboardButton("✅ Done!", callback_data='dare_done'),
            InlineKeyboardButton("🔴 Back to Truth", callback_data='truth')
        ]]
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Dare error: {e}")


async def spin_bottle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        chat = update.effective_chat
        
        # Spin animation
        spin_msg = await update.message.reply_text("🍾 *Bottle spin ho rahi hai...*", parse_mode='Markdown')
        
        spin_frames = ["🍾 ➡️", "⬆️ 🍾", "⬅️ 🍾", "⬇️ 🍾", "🍾 ➡️", "⬆️ 🍾"]
        for frame in spin_frames:
            await spin_msg.edit_text(f"*{frame} Spinning...*", parse_mode='Markdown')
            await asyncio.sleep(0.3)

        # Pick random member
        funny_names = [
            "Sharma Ji Ka Beta 🤓", "Chai Wala Bhai ☕",
            "Neend Ki Dushman 😴", "Bakwaas Master 🗣️",
            "Group Ka Ghost 👻", "Meme Lord 😂",
            "Silent Killer 🔇", "Natak Queen/King 🎭"
        ]
        picked = random.choice(funny_names)

        await spin_msg.edit_text(
            f"🍾 *BOTTLE RUKI!*\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🎯 Bottle point kar rahi hai: *{picked}* ko!\n\n"
            f"Ab inhe /truth ya /dare lena padega! 😈\n"
            f"━━━━━━━━━━━━━━━━━",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Spin error: {e}")


async def couple_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        names_pool = [
            "Rahul", "Priya", "Arjun", "Sneha", "Vikram", "Ananya",
            "Rohan", "Kavya", "Aditya", "Pooja", "Dev", "Simran",
            "Karan", "Nisha", "Raj", "Meera"
        ]
        
        person1 = random.choice(names_pool)
        names_pool.remove(person1)
        person2 = random.choice(names_pool)
        
        compatibility = random.randint(60, 100)
        
        if compatibility >= 90:
            verdict = "💑 SOULMATES! Shaadi fix karo! 💍"
            emoji = "❤️❤️❤️"
        elif compatibility >= 75:
            verdict = "😍 Perfect couple material! 🌹"
            emoji = "❤️❤️"
        else:
            verdict = "🤔 Thodi mehnat lagegi... par ho sakta hai! 😂"
            emoji = "💛"

        bar_filled = int(compatibility / 10)
        bar = "▓" * bar_filled + "░" * (10 - bar_filled)

        text = (
            f"💘 *COUPLE MATCHING MACHINE* 💘\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"👫 *{person1}* 💕 *{person2}*\n\n"
            f"🔥 Compatibility:\n"
            f"`[{bar}]` *{compatibility}%*\n\n"
            f"{emoji} *Verdict:* _{verdict}_\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💫 Ship name: *{person1[:3]}{person2[:3]}* 😂"
        )
        keyboard = [[InlineKeyboardButton("💘 Dobara Match Karo!", callback_data='couple')]]
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Couple error: {e}")


async def would_you_rather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        question = random.choice(WYR_QUESTIONS)
        keyboard = [[
            InlineKeyboardButton("A 🅰️", callback_data='wyr_a'),
            InlineKeyboardButton("B 🅱️", callback_data='wyr_b')
        ]]
        await update.message.reply_text(
            f"{question}\n\n_Vote karo bhai!_ 👇",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"WYR error: {e}")


async def roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        # Check if someone is mentioned
        if update.message.reply_to_message:
            target_name = update.message.reply_to_message.from_user.first_name
        elif context.args:
            target_name = " ".join(context.args).replace("@", "")
        else:
            target_name = "Khud ko"

        roast_msg = await update.message.reply_text("😈 *AI Roast Engine charging...*", parse_mode='Markdown')

        prompt = f"""
Ek brutal funny Hinglish roast likho '{target_name}' ke liye.
- 4-5 lines mein
- Comedy style, actually offensive mat karo
- Hinglish mix (Hindi + English)
- Emojis zaroor use karo
- End mein "No offense bhai, love you 😂" likhna
"""
        try:
            response = model.generate_content(prompt)
            roast_text = response.text
        except:
            roast_text = random.choice(ROAST_LINES)

        await roast_msg.edit_text(
            f"🔥 *ROAST TIME: {target_name}* 🔥\n"
            f"━━━━━━━━━━━━━━━━━\n\n"
            f"{roast_text}\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"😂 *Bura mat maan, pyaar se diya!*",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Roast error: {e}")


async def confess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        if not context.args:
            await update.message.reply_text(
                "💌 *Anonymous Confession System*\n\n"
                "Usage: `/confess [tera dil ka raaz]`\n\n"
                "_Example: /confess Mujhe Rahul pasand hai_ 😳",
                parse_mode='Markdown'
            )
            return

        confession_text = " ".join(context.args)
        confessions = load_json(CONFESS_FILE, [])
        confessions.append({
            "text": confession_text,
            "timestamp": datetime.now().isoformat(),
            "id": len(confessions) + 1
        })
        save_json(CONFESS_FILE, confessions)

        # Delete original message for anonymity
        try:
            await update.message.delete()
        except:
            pass

        confession_num = len(confessions)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"💌 *ANONYMOUS CONFESSION #{confession_num}* 💌\n"
                f"━━━━━━━━━━━━━━━━━\n\n"
                f"_{confession_text}_\n\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"😶 *Sender ka naam? Sirf dil jaanta hai...* 🌙"
            ),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Confess error: {e}")


async def ship_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        if context.args and len(context.args) >= 2:
            name1 = context.args[0]
            name2 = context.args[1]
        else:
            names = ["Rahul", "Priya", "Arjun", "Sneha", "Riya", "Dev"]
            name1 = random.choice(names)
            names.remove(name1)
            name2 = random.choice(names)

        # Generate ship name
        ship = name1[:len(name1)//2 + 1] + name2[len(name2)//2:]
        compatibility = random.randint(50, 100)
        
        prompt = f"Write a funny 2-line Hinglish love story about '{name1}' and '{name2}' as a couple called '{ship}'. Keep it light and fun with emojis."
        try:
            response = model.generate_content(prompt)
            story = response.text[:300]
        except:
            story = f"{name1} aur {name2} ek duje ke liye bane hain! 💕"

        text = (
            f"⚡ *SHIP NAME GENERATOR* ⚡\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"👫 *{name1}* + *{name2}*\n\n"
            f"💑 *Ship Name:* `{ship}`\n"
            f"💯 *Score:* `{compatibility}%`\n\n"
            f"📖 *Love Story:*\n_{story}_\n"
            f"━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ship error: {e}")


async def rate_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        if update.message.reply_to_message:
            target = update.message.reply_to_message.from_user.first_name
        elif context.args:
            target = " ".join(context.args).replace("@", "")
        else:
            target = update.effective_user.first_name

        categories = {
            "😂 Funniness": random.randint(1, 10),
            "😎 Coolness": random.randint(1, 10),
            "🧠 Intelligence": random.randint(1, 10),
            "💅 Vibe": random.randint(1, 10),
            "🗣️ Bakwaas Level": random.randint(1, 10),
        }
        
        total = sum(categories.values())
        avg = total / len(categories)
        
        rating_text = f"📊 *OFFICIAL RATING: {target}* 📊\n━━━━━━━━━━━━━━━━━\n\n"
        for cat, score in categories.items():
            bar = "▓" * score + "░" * (10 - score)
            rating_text += f"{cat}: `[{bar}]` {score}/10\n"
        
        rating_text += f"\n━━━━━━━━━━━━━━━━━\n"
        rating_text += f"⭐ *Overall:* `{avg:.1f}/10`\n"
        
        if avg >= 8:
            rating_text += "🔥 _Legend hai bhai!_"
        elif avg >= 6:
            rating_text += "😎 _Solid player!_"
        elif avg >= 4:
            rating_text += "😐 _Theek hai... bas._"
        else:
            rating_text += "💀 _Bhai... koshish karte raho!_"
            
        await update.message.reply_text(rating_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Rate error: {e}")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        lb_text = get_leaderboard_text()
        await update.message.reply_text(lb_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")


async def ngl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        if not context.args:
            await update.message.reply_text(
                "💬 *NGL - Not Gonna Lie*\n\n"
                "Usage: `/ngl @username [message]`\n"
                "_Example: /ngl @Rahul Tu bahut funny hai!_",
                parse_mode='Markdown'
            )
            return

        message = " ".join(context.args)
        try:
            await update.message.delete()
        except:
            pass

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"💬 *NGL (Not Gonna Lie)* 💬\n"
                f"━━━━━━━━━━━━━━━━━\n\n"
                f"_{message}_\n\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"🤫 _Sender anonymous hai!_"
            ),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"NGL error: {e}")


# ================== 7. STATS & UTILITY COMMANDS ==================
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    stats = load_json(STATS_FILE, {"total_users": 0, "total_commands": 0})
    confessions = load_json(CONFESS_FILE, [])
    
    text = (
        "📊 *PARTY RIOT BOT - STATS* 📊\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"👥 *Total Users:* `{stats['total_users']}`\n"
        f"⚡ *Commands Used:* `{stats['total_commands']}`\n"
        f"💌 *Confessions:* `{len(confessions)}`\n"
        f"🟢 *Status:* `Online & Partying!`\n"
        "━━━━━━━━━━━━━━━━━\n"
        "🎉 _Bot mast chal raha hai!_ 🔥"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_t = time.time()
    msg = await update.message.reply_text("🏓 Pong chalc rahi hai...")
    end_t = time.time()
    latency = round((end_t - start_t) * 1000, 2)
    
    await msg.edit_text(
        f"🏓 *PONG!*\n\n"
        f"⚡ Latency: `{latency}ms`\n"
        f"🟢 Status: `Online`\n"
        f"😂 Mood: `Party Mode!`",
        parse_mode='Markdown'
    )


async def alive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime_seconds = time.time() - BOT_START_TIME
    uptime = str(timedelta(seconds=int(uptime_seconds)))
    
    text = (
        f"🌸 *PARTY RIOT BOT - ALIVE!* 🌸\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"✅ *Status:* `Fully Operational`\n"
        f"⏱️ *Uptime:* `{uptime}`\n"
        f"🎉 *Mode:* `Party Hard!`\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"Zinda hoon bhai, full josh mein! 🔥"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    text = (
        "📖 *PARTY RIOT BOT - HELP* 📖\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "🎮 *Game Commands:*\n"
        "`/truth` — Random spicy truth question\n"
        "`/dare` — Crazy dare challenge\n"
        "`/spin` — Bottle spin karo\n"
        "`/couple` — Random couple match 💘\n"
        "`/wyr` — Would You Rather\n"
        "`/roast @user` — AI roast 😂\n"
        "`/confess [text]` — Anonymous confession\n"
        "`/ngl [msg]` — Anonymous NGL\n"
        "`/shipname [n1] [n2]` — Ship name\n"
        "`/rate @user` — Rate someone\n"
        "`/leaderboard` — Top players 🏆\n\n"
        "📊 *Info Commands:*\n"
        "`/start` — Main menu\n"
        "`/help` — Ye help menu\n"
        "`/stats` — Bot stats\n"
        "`/ping` — Bot latency\n"
        "`/alive` — Bot status\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "_Group mein use karo, maza dugna hoga!_ 🎉"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


# ================== 8. OWNER COMMANDS ==================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    
    if not context.args:
        await update.message.reply_text("Usage: `/broadcast [message]`", parse_mode='Markdown')
        return
    
    msg = " ".join(context.args)
    broadcast_text = (
        f"📢 *OWNER BROADCAST* 📢\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"{msg}\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"— _Party Riot Bot Owner_ 👑"
    )
    await update.message.reply_text(
        f"✅ Broadcast message ready:\n\n{broadcast_text}\n\n_(Send karne ke liye manually copy karo group mein)_",
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
            await update.message.reply_text(f"🔨 *User `{target_id}` ko ban kar diya!*", parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ Ye user pehle se banned hai.", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ Valid user ID daal bhai!")


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
            await update.message.reply_text(f"✅ *User `{target_id}` unban ho gaya!*", parse_mode='Markdown')
        else:
            await update.message.reply_text("⚠️ Ye user banned nahi tha.", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ Valid user ID daal bhai!")


async def clear_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    save_json(LEADERBOARD_FILE, {})
    await update.message.reply_text("🗑️ *Leaderboard saaf ho gaya!*", parse_mode='Markdown')


async def clear_confessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    save_json(CONFESS_FILE, [])
    await update.message.reply_text("🗑️ *Saari confessions delete ho gayi!*", parse_mode='Markdown')


async def owner_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    
    stats = load_json(STATS_FILE, {})
    confessions = load_json(CONFESS_FILE, [])
    banned = load_json(BANNED_FILE, [])
    lb = load_json(LEADERBOARD_FILE, {})
    uptime = str(timedelta(seconds=int(time.time() - BOT_START_TIME)))
    
    text = (
        f"🔐 *OWNER DASHBOARD* 🔐\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users: `{stats.get('total_users', 0)}`\n"
        f"⚡ Total Commands: `{stats.get('total_commands', 0)}`\n"
        f"💌 Confessions: `{len(confessions)}`\n"
        f"🔨 Banned Users: `{len(banned)}`\n"
        f"🏆 Leaderboard Entries: `{len(lb)}`\n"
        f"⏱️ Uptime: `{uptime}`\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🕐 Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def add_truth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    if not context.args:
        await update.message.reply_text("Usage: `/addtruth [question]`", parse_mode='Markdown')
        return
    question = " ".join(context.args)
    TRUTH_QUESTIONS.append(question)
    await update.message.reply_text(f"✅ *Naya truth question add ho gaya!*\n\n_{question}_", parse_mode='Markdown')


async def add_dare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update): return
    if not context.args:
        await update.message.reply_text("Usage: `/adddare [challenge]`", parse_mode='Markdown')
        return
    dare_text = " ".join(context.args)
    DARE_CHALLENGES.append(dare_text)
    await update.message.reply_text(f"✅ *Naya dare add ho gaya!*\n\n_{dare_text}_", parse_mode='Markdown')


async def send_as_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner special: Bot ki taraf se koi bhi message bhejo kisi bhi chat mein"""
    if not await owner_only(update): return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/say [chat_id] [message]`\n"
            "_Example: /say -100123456 Hello everyone!_",
            parse_mode='Markdown'
        )
        return
    
    try:
        chat_id = context.args[0]
        msg = " ".join(context.args[1:])
        await context.bot.send_message(chat_id=chat_id, text=msg)
        await update.message.reply_text("✅ Message bhej diya!", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ================== 9. CALLBACK HANDLER ==================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == 'truth':
        question = random.choice(TRUTH_QUESTIONS)
        user = query.from_user.first_name
        text = (
            f"🔴 *TRUTH!*\n━━━━━━━━━━━━━━━━━\n"
            f"🎯 *{user}* ko:\n\n💬 _{question}_\n\n"
            f"━━━━━━━━━━━━━━━━━\nSach bol! 😏"
        )
        keyboard = [[
            InlineKeyboardButton("🔴 Aur Truth!", callback_data='truth'),
            InlineKeyboardButton("🟠 Dare!", callback_data='dare')
        ]]
        await query.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'dare':
        challenge = random.choice(DARE_CHALLENGES)
        user = query.from_user.first_name
        text = (
            f"🟠 *DARE!*\n━━━━━━━━━━━━━━━━━\n"
            f"😈 *{user}* ko:\n\n⚡ _{challenge}_\n\n"
            f"━━━━━━━━━━━━━━━━━\nKar sakta hai? 😂"
        )
        keyboard = [[
            InlineKeyboardButton("✅ Done!", callback_data='dare_done'),
            InlineKeyboardButton("🔴 Truth!", callback_data='truth')
        ]]
        await query.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'dare_done':
        user = query.from_user.first_name
        update_leaderboard(query.from_user.id, user, 10)
        await query.message.reply_text(
            f"✅ *{user}* ne dare complete kiya!\n🏆 *+10 points!*\n\n_Legend hai bhai!_ 🔥",
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

    elif data == 'leaderboard':
        await query.message.reply_text(get_leaderboard_text(), parse_mode='Markdown')

    elif data == 'help':
        text = (
            "📖 *Quick Help:*\n\n"
            "`/truth` `/dare` `/spin` `/couple`\n"
            "`/roast` `/confess` `/wyr` `/ngl`\n"
            "`/shipname` `/rate` `/leaderboard`\n\n"
            "_/help ke liye full menu dekho!_ 🎉"
        )
        await query.message.reply_text(text, parse_mode='Markdown')

    elif data in ['wyr_a', 'wyr_b']:
        choice = "A 🅰️" if data == 'wyr_a' else "B 🅱️"
        user = query.from_user.first_name
        await query.message.reply_text(
            f"*{user}* ne choose kiya: *{choice}*! 😂\n_Interesting choice!_ 🤔",
            parse_mode='Markdown'
        )


# ================== 10. ERROR HANDLER ==================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"⚠️ *Bot Error:*\n```\n{str(context.error)[:400]}\n```",
            parse_mode='Markdown'
        )
    except:
        pass


async def post_init(application):
    await application.bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Webhook cleared!")


# ================== 11. MAIN ==================
def main():
    logger.info("🎉 Booting Party Riot Bot...")

    keep_alive()

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    # Game commands
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

    # Info commands
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("alive", alive_command))

    # Owner commands 🔐
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("clearboard", clear_leaderboard))
    app.add_handler(CommandHandler("clearconfess", clear_confessions))
    app.add_handler(CommandHandler("ownerstats", owner_stats))
    app.add_handler(CommandHandler("addtruth", add_truth))
    app.add_handler(CommandHandler("adddare", add_dare))
    app.add_handler(CommandHandler("say", send_as_bot))

    # Callback buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    app.add_error_handler(error_handler)

    logger.info("✅ Party Riot Bot Ready! Let's go! 🎉")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == '__main__':
    main()
