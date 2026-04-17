"""
games.py — Party Riot Bot V2
Contains: Static data, game logic helpers, and all game command handlers
"""

import random
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils import (
    check_banned, update_leaderboard, update_streak,
    load_json, save_json, LEADERBOARD_FILE, CONFESS_FILE,
    MOOD_FILE, STREAKS_FILE
)

logger = logging.getLogger(__name__)

# ================== STATIC DATA ==================

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
    "Ek cheez jo kabhi parents ko nahi bataya? 🤫",
    "Last time kab jhooth bola? Kya tha? 😬",
    "Kisi pe crush hai abhi bhi? Group mein hai kya woh? 👀",
    "Sabse badi galti kya ki hai relationship mein? 💔",
    "Kisi aur ke bf/gf pe crush tha kabhi? 😳",
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
    "Next message mein sirf backwards likhna (e.g. 'hello' = 'olleh') 🔄",
    "Khud ki baby voice mein ek sentence bolke voice note bhejo 👶",
    "Apne favourite celebrity ka impression karo voice note mein 🌟",
]

WYR_QUESTIONS = [
    ("🤔 Would You Rather:\nA) Hamesha jhooth pakda jaye\nB) Kabhi sach na bol pao", "wyr_truth_caught", "wyr_cant_speak_truth"),
    ("🤔 Would You Rather:\nA) Bina phone ke 1 saal\nB) Bina dost ke 1 saal", "wyr_no_phone", "wyr_no_friends"),
    ("🤔 Would You Rather:\nA) Sabke thoughts read kar pao\nB) Future dekh pao", "wyr_read_minds", "wyr_see_future"),
    ("🤔 Would You Rather:\nA) Famous ho par broke ho\nB) Rich ho par unknown", "wyr_famous", "wyr_rich"),
    ("🤔 Would You Rather:\nA) Udd sako\nB) Invisible ho sako", "wyr_fly", "wyr_invisible"),
    ("🤔 Would You Rather:\nA) Hamesha dance karte raho\nB) Hamesha gaate raho", "wyr_dance", "wyr_sing"),
    ("🤔 Would You Rather:\nA) 10 saal pehle wapas jao\nB) 10 saal aage chale jao", "wyr_past", "wyr_future"),
    ("🤔 Would You Rather:\nA) Apni pasand ki life karo par akele raho\nB) Log chahein par boring job karo", "wyr_lonelife", "wyr_crowded"),
]

ROAST_LINES = [
    "Bhai tera wifi ka signal teri life se zyada strong hai! 📶",
    "Teri personality itni bland hai ki unsalted chips bhi interesting lage tere saamne! 🍟",
    "Tu itna slow hai ki kachhua bhi tera speed dekh ke hasega! 🐢",
    "Bhai tera fashion sense dekh ke kapde khud rona lagein! 👗",
    "Teri jokes itni purani hain ki Wikipedia pe bhi nahi milti! 📖",
]

ZODIAC_TRAITS = {
    "aries": "🐏 *Aries* — Tu toh full fire hai bhai! Leader types, thoda impulsive, but always first! 🔥",
    "taurus": "🐂 *Taurus* — Stubborn af, par reliable bhi! Khana aur aaram — life goals! 🍔",
    "gemini": "👯 *Gemini* — Ek minute serious, doosre minute meme. Dono personalities valid hain! 😂",
    "cancer": "🦀 *Cancer* — Sensitive soul, ghar ka pyaar, emotions ka ocean! 🌊",
    "leo": "🦁 *Leo* — King/Queen energy 24/7! Spotlight tera birth right hai! 👑",
    "virgo": "🧹 *Virgo* — Perfectionist bhai! Sab kuch organize, sab kuch plan! 📋",
    "libra": "⚖️ *Libra* — Balance khojta hai, har jagah! Decision lena... kal karein? 😅",
    "scorpio": "🦂 *Scorpio* — Mystery man/woman! Intense, passionate, thoda dangerous 😏",
    "sagittarius": "🏹 *Sagittarius* — Adventure ka bhai! Ek jagah nahi tikta, sab explore karta! 🌍",
    "capricorn": "🐐 *Capricorn* — Hardworking machine! Goals set, achieve, repeat! 💼",
    "aquarius": "🪄 *Aquarius* — Rebel with a cause! Unique thinker, future ka insan! 🛸",
    "pisces": "🐟 *Pisces* — Dreamer supreme! Emotions deep, creativity wild! 🎨",
}

FORTUNE_COOKIES = [
    "🔮 Aaj tera din lucky hai — kisi ko propose karo! 💘",
    "🔮 Aaj kuch unexpected hoga... achha bhi ho sakta hai, bura bhi 😂",
    "🔮 Stars bol rahe hain: chai pi aur life enjoy karo ☕",
    "🔮 Teri mehnat rang layegi... bas thoda aur wait karo 🌈",
    "🔮 Koi tujhe secretly like karta hai... 👀 Hint: group mein hai!",
    "🔮 Aaj kuch bada hone wala hai — ya phir kuch nahi bhi hoga 🤷",
    "🔮 Love life mein twist aane wala hai! Ready reh 💕",
    "🔮 Paisa aayega... ya jayega. Dono possibilities hain 😂",
    "🔮 Aaj jo decision lega, future pe asar padega. No pressure though 😅",
    "🔮 Teri energy aaj off the charts hai! Use it wisely 🔥",
]

COMPLIMENTS = [
    "Yaar tu toh sach mein gem hai! 💎 Group ka sabse pyaara insaan!",
    "Teri smile dekh ke log apni problems bhool jaate hain 😊✨",
    "Tu jo bhi karta hai, full dedication se karta hai. Respect bhai! 🙏",
    "Teri vibe alag hi level ki hai! Duniya tere jaisi aur chahiye 🌟",
    "Bhai/Behen tu toh walking sunshine hai ☀️ Sab khush ho jaate hain tere aane se!",
    "Teri sense of humor top-tier hai! Comedy king/queen 😂👑",
    "Tu sirf awesome nahi, extra awesome hai! 🔥",
    "Log tere baare mein kitna sochte hain — har baar positive! 💕",
]

EIGHT_BALL_ANSWERS = [
    "🎱 Bilkul haan! 100% sure!",
    "🎱 Nahi bhai... kabhi nahi 😂",
    "🎱 Shayad... stars theek nahi hain abhi",
    "🎱 Bahut chances hain! Try kar!",
    "🎱 Mujhe doubt hai... 🤔",
    "🎱 Haan, but thoda wait kar",
    "🎱 Bhai ball keh rahi hai: NAH 😂",
    "🎱 Signs point to YES! 🎉",
    "🎱 Apne dil se pooch, mujhe nahi pata 😅",
    "🎱 Absolutely YES! Jaa kar kar de!",
]

NEVER_HAVE_I_EVER = [
    "Never have I ever... raat ko ghar se chhup ke nikla/nikli hoon 🌙",
    "Never have I ever... kisi ka phone unlock karke dekha hoon 📱",
    "Never have I ever... exam mein teacher se hi copy ki hoon 😂",
    "Never have I ever... ek sath do logo ko like kiya hoon 😳",
    "Never have I ever... apni age zyada batai hai 😂",
    "Never have I ever... kisi ki burai unke saamne hi ki hoon 🫣",
    "Never have I ever... online aake 'offline' dikhaya hoon 👻",
    "Never have I ever... kisi ke liye fake sick hua/hui hoon 🤒",
    "Never have I ever... apne crush ko stalk kiya hoon 👀",
    "Never have I ever... parents se paise churaye hoon 😬",
]

TRIVIA_QUESTIONS = [
    {
        "q": "🧠 *TRIVIA TIME!*\n\nIndia ka national animal kya hai?",
        "options": ["Sher 🦁", "Haathi 🐘", "Bagh 🐯", "Gaye 🐄"],
        "answer": 2,
        "explanation": "Bengal Tiger 🐯 India ka national animal hai!"
    },
    {
        "q": "🧠 *TRIVIA TIME!*\n\nSabse bada ocean kaun sa hai?",
        "options": ["Atlantic", "Indian", "Pacific", "Arctic"],
        "answer": 2,
        "explanation": "Pacific Ocean sabse bada hai duniya mein! 🌊"
    },
    {
        "q": "🧠 *TRIVIA TIME!*\n\nGoogle ka original naam kya tha?",
        "options": ["Googol", "BackRub", "PageRank", "Veritas"],
        "answer": 1,
        "explanation": "1996 mein Google ka naam 'BackRub' tha! 🤯"
    },
    {
        "q": "🧠 *TRIVIA TIME!*\n\nKitne countries mein Hindi boli jaati hai (primarily)?",
        "options": ["1", "4", "7", "12"],
        "answer": 1,
        "explanation": "Fiji, Mauritius, Suriname aur India mein Hindi primarily boli jaati hai!"
    },
]

# ================== GAME COMMAND HANDLERS ==================

async def truth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        question = random.choice(TRUTH_QUESTIONS)
        user = update.effective_user.first_name
        text = (
            f"🔴 *TRUTH TIME!* 🔴\n━━━━━━━━━━━━━━━━━\n"
            f"🎯 *{user}* ko yeh poochha gaya:\n\n💬 _{question}_\n\n"
            f"━━━━━━━━━━━━━━━━━\nSach bol de bhai, koi judge nahi karega... ya karega? 😏"
        )
        keyboard = [[
            InlineKeyboardButton("🔴 Aur Truth!", callback_data='truth'),
            InlineKeyboardButton("🟠 Switch to Dare", callback_data='dare'),
            InlineKeyboardButton("✅ Jawab Diya!", callback_data='truth_answered')
        ]]
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        update_leaderboard(update.effective_user.id, user, 1, "truth")
        update_streak(update.effective_user.id, user)
    except Exception as e:
        logger.error(f"Truth error: {e}")


async def dare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        challenge = random.choice(DARE_CHALLENGES)
        user = update.effective_user.first_name
        text = (
            f"🟠 *DARE TIME!* 🟠\n━━━━━━━━━━━━━━━━━\n"
            f"😈 *{user}* ko yeh dare mila:\n\n⚡ _{challenge}_\n\n"
            f"━━━━━━━━━━━━━━━━━\nComplete kiya toh 10 points! Nahi kiya toh... sharam aani chahiye! 😂"
        )
        keyboard = [[
            InlineKeyboardButton("✅ Done! +10pts", callback_data='dare_done'),
            InlineKeyboardButton("🔄 New Dare", callback_data='dare'),
            InlineKeyboardButton("🔴 Back to Truth", callback_data='truth')
        ]]
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Dare error: {e}")


async def spin_bottle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        spin_msg = await update.message.reply_text("🍾 *Bottle spin ho rahi hai...*", parse_mode='Markdown')
        spin_frames = ["🍾 ➡️", "⬆️ 🍾", "⬅️ 🍾", "⬇️ 🍾", "🍾 ➡️", "⬆️ 🍾", "🎯 *RUKI!*"]
        for frame in spin_frames:
            await spin_msg.edit_text(f"*{frame}*", parse_mode='Markdown')
            await asyncio.sleep(0.3)

        funny_names = [
            "Sharma Ji Ka Beta 🤓", "Chai Wala Bhai ☕",
            "Neend Ki Dushman 😴", "Bakwaas Master 🗣️",
            "Group Ka Ghost 👻", "Meme Lord 😂",
            "Silent Killer 🔇", "Natak Queen/King 🎭",
            "Phone Addict 📱", "Party Starter 🎉"
        ]
        picked = random.choice(funny_names)
        action = random.choice(["Truth lo! 🔴", "Dare lo! 🟠", "Compliment do kisiko! 💕", "Roast karo khud ko! 😂"])
        await spin_msg.edit_text(
            f"🍾 *BOTTLE RUKI!*\n\n━━━━━━━━━━━━━━━━━\n"
            f"🎯 Bottle point kar rahi hai: *{picked}* ko!\n\n"
            f"📌 Next step: *{action}*\n━━━━━━━━━━━━━━━━━",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Spin error: {e}")


async def couple_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        names_pool = ["Rahul", "Priya", "Arjun", "Sneha", "Vikram", "Ananya",
                      "Rohan", "Kavya", "Aditya", "Pooja", "Dev", "Simran",
                      "Karan", "Nisha", "Raj", "Meera"]
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
        zodiac_pair = random.choice(["Made in heaven ⭐", "Rivals to lovers 🔥", "Best friends 💕", "Opposites attract 🧲"])
        text = (
            f"💘 *COUPLE MATCHING MACHINE* 💘\n━━━━━━━━━━━━━━━━━\n"
            f"👫 *{person1}* 💕 *{person2}*\n\n"
            f"🔥 Compatibility:\n`[{bar}]` *{compatibility}%*\n\n"
            f"{emoji} *Verdict:* _{verdict}_\n"
            f"🌟 *Trope:* _{zodiac_pair}_\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💫 Ship name: *{person1[:3]}{person2[:3]}* 😂"
        )
        keyboard = [[
            InlineKeyboardButton("💘 Dobara Match Karo!", callback_data='couple'),
            InlineKeyboardButton("⚡ Ship Name", callback_data='ship_random')
        ]]
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Couple error: {e}")


async def would_you_rather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        q_data = random.choice(WYR_QUESTIONS)
        question, cb_a, cb_b = q_data
        keyboard = [[
            InlineKeyboardButton("A 🅰️ — Vote!", callback_data=f'wyr_{cb_a}'),
            InlineKeyboardButton("B 🅱️ — Vote!", callback_data=f'wyr_{cb_b}')
        ]]
        await update.message.reply_text(
            f"{question}\n\n_Vote karo bhai!_ 👇",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"WYR error: {e}")


async def roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        if update.message.reply_to_message:
            target_name = update.message.reply_to_message.from_user.first_name
        elif context.args:
            target_name = " ".join(context.args).replace("@", "")
        else:
            target_name = update.effective_user.first_name + " (khud)"

        roast_msg = await update.message.reply_text("😈 *AI Roast Engine charging...*", parse_mode='Markdown')
        prompt = f"""Ek brutal funny Hinglish roast likho '{target_name}' ke liye.
- 4-5 lines mein
- Comedy style, actually offensive mat karo
- Hinglish mix (Hindi + English)
- Emojis zaroor use karo
- End mein ek soft landing line likhna (bura mat maan wala vibe)"""
        try:
            response = model.generate_content(prompt)
            roast_text = response.text
        except:
            roast_text = random.choice(ROAST_LINES)

        keyboard = [[InlineKeyboardButton("😂 Aur Roast!", callback_data=f'roast_{target_name}')]]
        await roast_msg.edit_text(
            f"🔥 *ROAST TIME: {target_name}* 🔥\n━━━━━━━━━━━━━━━━━\n\n"
            f"{roast_text}\n\n━━━━━━━━━━━━━━━━━\n😂 *Bura mat maan, pyaar se diya!*",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
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
        confessions.append({"text": confession_text, "timestamp": datetime.now().isoformat(), "id": len(confessions) + 1})
        save_json(CONFESS_FILE, confessions)
        try:
            await update.message.delete()
        except:
            pass
        confession_num = len(confessions)
        keyboard = [[
            InlineKeyboardButton("❤️ Relate!", callback_data=f'confess_react_{confession_num}'),
            InlineKeyboardButton("😮 Woah!", callback_data=f'confess_react_{confession_num}')
        ]]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"💌 *ANONYMOUS CONFESSION #{confession_num}* 💌\n━━━━━━━━━━━━━━━━━\n\n"
                f"_{confession_text}_\n\n━━━━━━━━━━━━━━━━━\n😶 *Sender ka naam? Sirf dil jaanta hai...* 🌙"
            ),
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Confess error: {e}")


async def ship_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        if context.args and len(context.args) >= 2:
            name1 = context.args[0]
            name2 = context.args[1]
        else:
            names = ["Rahul", "Priya", "Arjun", "Sneha", "Riya", "Dev"]
            name1 = random.choice(names)
            names.remove(name1)
            name2 = random.choice(names)

        ship = name1[:len(name1)//2 + 1] + name2[len(name2)//2:]
        compatibility = random.randint(50, 100)
        try:
            prompt = f"Write a funny 2-line Hinglish love story about '{name1}' and '{name2}' as a couple called '{ship}'. Keep it light and fun with emojis."
            response = model.generate_content(prompt)
            story = response.text[:300]
        except:
            story = f"{name1} aur {name2} ek duje ke liye bane hain! 💕"

        text = (
            f"⚡ *SHIP NAME GENERATOR* ⚡\n━━━━━━━━━━━━━━━━━\n"
            f"👫 *{name1}* + *{name2}*\n\n"
            f"💑 *Ship Name:* `{ship}`\n💯 *Score:* `{compatibility}%`\n\n"
            f"📖 *Love Story:*\n_{story}_\n━━━━━━━━━━━━━━━━━"
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
            "💪 Cringe Resistance": random.randint(1, 10),
        }
        total = sum(categories.values())
        avg = total / len(categories)
        rating_text = f"📊 *OFFICIAL RATING: {target}* 📊\n━━━━━━━━━━━━━━━━━\n\n"
        for cat, score in categories.items():
            bar = "▓" * score + "░" * (10 - score)
            rating_text += f"{cat}: `[{bar}]` {score}/10\n"
        rating_text += f"\n━━━━━━━━━━━━━━━━━\n⭐ *Overall:* `{avg:.1f}/10`\n"
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


async def ngl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        if not context.args:
            await update.message.reply_text(
                "💬 *NGL - Not Gonna Lie*\n\nUsage: `/ngl [message]`\n_Anonymous hai!_",
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
                f"💬 *NGL (Not Gonna Lie)* 💬\n━━━━━━━━━━━━━━━━━\n\n"
                f"_{message}_\n\n━━━━━━━━━━━━━━━━━\n🤫 _Sender anonymous hai!_"
            ),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"NGL error: {e}")


async def fortune_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        user = update.effective_user.first_name
        fortune_msg = await update.message.reply_text("🔮 *Crystal ball gazing...*", parse_mode='Markdown')
        await asyncio.sleep(1.5)
        try:
            prompt = f"Give a fun, mysterious, Hinglish fortune cookie prediction for '{user}' today. 2-3 lines, use emojis, be vague yet exciting like a real fortune teller. Mix Hindi and English."
            response = model.generate_content(prompt)
            fortune = response.text
        except:
            fortune = random.choice(FORTUNE_COOKIES)

        lucky_num = random.randint(1, 99)
        lucky_color = random.choice(["Red 🔴", "Blue 💙", "Green 💚", "Gold 🌟", "Purple 💜", "Pink 🩷"])
        await fortune_msg.edit_text(
            f"🔮 *{user} KA AAJ KA BHAVISHYA* 🔮\n━━━━━━━━━━━━━━━━━\n\n"
            f"_{fortune}_\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🍀 Lucky Number: `{lucky_num}`\n"
            f"🎨 Lucky Color: `{lucky_color}`\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"_Disclaimer: Bot ki bakwaas, seriously mat lo 😂_",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Fortune error: {e}")


async def eight_ball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        if not context.args:
            await update.message.reply_text(
                "🎱 *Magic 8 Ball*\n\nUsage: `/8ball [apna question]`\n_Example: /8ball Kya mujhe job milegi?_",
                parse_mode='Markdown'
            )
            return
        question = " ".join(context.args)
        ball_msg = await update.message.reply_text("🎱 *8 Ball soch rahi hai...*", parse_mode='Markdown')
        await asyncio.sleep(1.2)
        answer = random.choice(EIGHT_BALL_ANSWERS)
        await ball_msg.edit_text(
            f"🎱 *MAGIC 8 BALL*\n━━━━━━━━━━━━━━━━━\n"
            f"❓ *Q:* _{question}_\n\n"
            f"💬 *A:* {answer}\n━━━━━━━━━━━━━━━━━",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"8ball error: {e}")


async def zodiac_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        if not context.args:
            signs_list = ", ".join(ZODIAC_TRAITS.keys())
            await update.message.reply_text(
                f"♈ *ZODIAC READER*\n\nUsage: `/zodiac [sign]`\n\nAvailable signs:\n`{signs_list}`",
                parse_mode='Markdown'
            )
            return
        sign = context.args[0].lower()
        if sign in ZODIAC_TRAITS:
            trait = ZODIAC_TRAITS[sign]
            try:
                prompt = f"Add a funny Hinglish 2-line daily horoscope for {sign} today. Fun and light-hearted with emojis."
                response = model.generate_content(prompt)
                daily = response.text
            except:
                daily = "Aaj ka din kuch aur hi scene laayega! 🌟"
            await update.message.reply_text(
                f"✨ *ZODIAC READING* ✨\n━━━━━━━━━━━━━━━━━\n\n"
                f"{trait}\n\n📅 *Aaj Ka Scene:*\n_{daily}_\n━━━━━━━━━━━━━━━━━",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ '{sign}' nahi pata! Valid sign likhna bhai.")
    except Exception as e:
        logger.error(f"Zodiac error: {e}")


async def compliment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        if update.message.reply_to_message:
            target = update.message.reply_to_message.from_user.first_name
        elif context.args:
            target = " ".join(context.args).replace("@", "")
        else:
            target = update.effective_user.first_name

        comp_msg = await update.message.reply_text("💐 *Compliment generate ho raha hai...*", parse_mode='Markdown')
        try:
            prompt = f"Write a genuine, heartwarming Hinglish compliment for '{target}'. 3-4 lines, make them feel special and appreciated. Emojis use karo."
            response = model.generate_content(prompt)
            compliment = response.text
        except:
            compliment = random.choice(COMPLIMENTS)

        await comp_msg.edit_text(
            f"💐 *COMPLIMENT FOR: {target}* 💐\n━━━━━━━━━━━━━━━━━\n\n"
            f"_{compliment}_\n\n━━━━━━━━━━━━━━━━━\n"
            f"💕 _Bot ki taraf se pyaar!_",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Compliment error: {e}")


async def mood_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        user = update.effective_user
        moods = load_json(MOOD_FILE, {})
        if context.args:
            mood_text = " ".join(context.args)
            moods[str(user.id)] = {"name": user.first_name, "mood": mood_text, "time": datetime.now().isoformat()}
            save_json(MOOD_FILE, moods)
            try:
                prompt = f"React to someone's mood in Hinglish: they said their mood is '{mood_text}'. Give a fun 2-line response with emojis. Be supportive."
                response = model.generate_content(prompt)
                reaction = response.text
            except:
                reaction = f"Teri mood note kar li! {mood_text} — bot samajhta hai 💕"

            await update.message.reply_text(
                f"😊 *Mood Set!*\n\n🎭 *{user.first_name}'s Mood:* _{mood_text}_\n\n_{reaction}_",
                parse_mode='Markdown'
            )
        else:
            uid = str(user.id)
            if uid in moods:
                m = moods[uid]
                await update.message.reply_text(
                    f"🎭 *{user.first_name} ka current mood:*\n\n_{m['mood']}_\n\n_Set kiya tha kuch time pehle!_",
                    parse_mode='Markdown'
                )
            else:
                keyboard = [
                    [InlineKeyboardButton("😄 Happy", callback_data='mood_happy'),
                     InlineKeyboardButton("😢 Sad", callback_data='mood_sad')],
                    [InlineKeyboardButton("😠 Angry", callback_data='mood_angry'),
                     InlineKeyboardButton("😴 Tired", callback_data='mood_tired')],
                    [InlineKeyboardButton("🔥 Hype", callback_data='mood_hype'),
                     InlineKeyboardButton("😐 Meh", callback_data='mood_meh')]
                ]
                await update.message.reply_text(
                    "🎭 *Apna Mood Select Karo!*\n\nOr `/mood [apna mood]` type karo custom mood ke liye:",
                    parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
                )
    except Exception as e:
        logger.error(f"Mood error: {e}")


async def streak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        user = update.effective_user
        current_streak = update_streak(user.id, user.first_name)
        streaks = load_json(STREAKS_FILE, {})
        uid = str(user.id)
        max_streak = streaks.get(uid, {}).get("max_streak", current_streak)

        if current_streak >= 7:
            emoji = "🔥🔥🔥"
            title = "LEGENDARY STREAK!"
        elif current_streak >= 3:
            emoji = "🔥🔥"
            title = "ON FIRE!"
        else:
            emoji = "🔥"
            title = "Keep it up!"

        await update.message.reply_text(
            f"🔥 *{user.first_name}'s DAILY STREAK* 🔥\n━━━━━━━━━━━━━━━━━\n\n"
            f"{emoji} *Current Streak:* `{current_streak} days`\n"
            f"🏆 *Best Streak:* `{max_streak} days`\n\n"
            f"⚡ *Status:* _{title}_\n━━━━━━━━━━━━━━━━━\n"
            f"_Roz kheloge toh streak badhegi! 💪_",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Streak error: {e}")


async def ask_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        if not context.args:
            await update.message.reply_text(
                "🤖 *AI Se Pooch!*\n\nUsage: `/ask [tera sawaal]`\n_Example: /ask life mein kya karna chahiye?_",
                parse_mode='Markdown'
            )
            return
        question = " ".join(context.args)
        user = update.effective_user.first_name
        thinking_msg = await update.message.reply_text("🤖 *AI soch raha hai...*", parse_mode='Markdown')
        prompt = f"""Tu Party Riot Bot V2 hai. Ek user ne poochha: "{question}"
Hinglish mein jawab de, fun aur informative. 3-5 lines. Emojis use karo. User ka naam {user} hai."""
        try:
            response = model.generate_content(prompt)
            answer = response.text
        except:
            answer = "Yaar server load pe hai! Thodi der baad try karo 😅"

        await thinking_msg.edit_text(
            f"🤖 *AI KA JAWAB* 🤖\n━━━━━━━━━━━━━━━━━\n\n"
            f"❓ _{question}_\n\n💬 {answer}\n━━━━━━━━━━━━━━━━━",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ask error: {e}")


async def random_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        max_num = 100
        min_num = 1
        if context.args:
            try:
                max_num = int(context.args[0])
                if len(context.args) > 1:
                    min_num = int(context.args[0])
                    max_num = int(context.args[1])
            except:
                pass
        result = random.randint(min_num, max_num)
        await update.message.reply_text(
            f"🎲 *RANDOM NUMBER GENERATOR*\n━━━━━━━━━━━━━━━━━\n"
            f"Range: `{min_num}` to `{max_num}`\n\n"
            f"🎯 *Result: `{result}`*\n━━━━━━━━━━━━━━━━━\n_Kismat ne decide kiya!_ 😂",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"RNG error: {e}")


async def battle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        challenger = update.effective_user.first_name
        if update.message.reply_to_message:
            opponent = update.message.reply_to_message.from_user.first_name
        elif context.args:
            opponent = " ".join(context.args).replace("@", "")
        else:
            opponent = "Random Challenger 👻"

        battle_msg = await update.message.reply_text("⚔️ *Epic battle loading...*", parse_mode='Markdown')
        battle_frames = [
            f"⚔️ *{challenger}* VS *{opponent}*",
            "💥 Round 1 begins!",
            "🔥 Intense fighting...",
            "⚡ Power levels rising!",
            "🏆 And the winner is..."
        ]
        for frame in battle_frames:
            await battle_msg.edit_text(frame, parse_mode='Markdown')
            await asyncio.sleep(0.7)

        winner = random.choice([challenger, opponent])
        loser = opponent if winner == challenger else challenger
        win_hp = random.randint(10, 99)
        moves = random.randint(3, 12)
        try:
            prompt = f"Write a funny 3-line Hinglish battle commentary between '{challenger}' and '{opponent}' where '{winner}' wins. Be dramatic and funny. Emojis use karo."
            response = model.generate_content(prompt)
            commentary = response.text
        except:
            commentary = f"{winner} ne {loser} ko ek hi move mein defeat kar diya! Legendary! 🔥"

        await battle_msg.edit_text(
            f"⚔️ *EPIC BATTLE RESULT* ⚔️\n━━━━━━━━━━━━━━━━━\n"
            f"🏆 *WINNER: {winner}*\n"
            f"💀 *Defeated: {loser}*\n\n"
            f"📊 Stats:\n"
            f"• HP Remaining: `{win_hp}%`\n"
            f"• Total Moves: `{moves}`\n\n"
            f"📖 *Commentary:*\n_{commentary}_\n━━━━━━━━━━━━━━━━━",
            parse_mode='Markdown'
        )
        if winner == challenger:
            update_leaderboard(update.effective_user.id, challenger, 5)
    except Exception as e:
        logger.error(f"Battle error: {e}")


async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        fact_msg = await update.message.reply_text("🌍 *Fact dhundh raha hoon...*", parse_mode='Markdown')
        try:
            topics = ["science", "history", "technology", "animals", "space", "India", "food", "human body"]
            topic = random.choice(topics)
            prompt = f"Give one mind-blowing, interesting fact about {topic}. Present it in Hinglish (Hindi + English mix). 2-3 sentences. Start with 'Did you know' or a Hindi equivalent. Add emojis."
            response = model.generate_content(prompt)
            fact = response.text
        except:
            fact = "Did you know? Octopus ke teen dil hote hain! 🐙 Kitna romantic hai na!"

        keyboard = [[InlineKeyboardButton("🌍 Aur Fact!", callback_data='fact')]]
        await fact_msg.edit_text(
            f"🌍 *RANDOM COOL FACT* 🌍\n━━━━━━━━━━━━━━━━━\n\n"
            f"{fact}\n\n━━━━━━━━━━━━━━━━━\n_Sach hai bhai, Google kar le! 😂_",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Fact error: {e}")


async def never_have_i_ever(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        statement = random.choice(NEVER_HAVE_I_EVER)
        keyboard = [[
            InlineKeyboardButton("✅ Maine kiya!", callback_data='nhie_done'),
            InlineKeyboardButton("❌ Maine nahi kiya", callback_data='nhie_notdone'),
            InlineKeyboardButton("🔄 Next!", callback_data='nhie')
        ]]
        await update.message.reply_text(
            f"🃏 *NEVER HAVE I EVER* 🃏\n━━━━━━━━━━━━━━━━━\n\n"
            f"_{statement}_\n\n━━━━━━━━━━━━━━━━━\n_Honestly jawab dena! 😏_",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"NHIE error: {e}")


async def trivia_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        q_data = random.choice(TRIVIA_QUESTIONS)
        options = q_data["options"]
        keyboard = [[InlineKeyboardButton(f"{opt}", callback_data=f'trivia_{i}_{q_data["answer"]}_{update.effective_user.id}')] for i, opt in enumerate(options)]
        await update.message.reply_text(
            f"{q_data['q']}\n\n_Sahi jawab do aur points pao!_ 🏆",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Trivia error: {e}")


async def poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        if not context.args:
            await update.message.reply_text(
                "📊 *Poll Creator*\n\nUsage: `/poll [question]`\n_Auto options: Yes/No/Maybe_\n\nCustom: `/poll question | option1 | option2`",
                parse_mode='Markdown'
            )
            return
        full_text = " ".join(context.args)
        if "|" in full_text:
            parts = [p.strip() for p in full_text.split("|")]
            question = parts[0]
            options = parts[1:4] if len(parts) > 1 else ["Haan ✅", "Nahi ❌", "Maybe 🤔"]
        else:
            question = full_text
            options = ["Haan ✅", "Nahi ❌", "Maybe 🤔"]

        keyboard = [[InlineKeyboardButton(opt, callback_data=f'poll_{opt[:10]}')] for opt in options]
        await update.message.reply_text(
            f"📊 *GROUP POLL*\n━━━━━━━━━━━━━━━━━\n\n❓ *{question}*\n\n_Vote karo!_ 👇",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Poll error: {e}")
