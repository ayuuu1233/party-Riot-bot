"""
games.py — Party Riot Bot
All game command handlers + static data
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
    "Pehli crush kaun tha/thi? First name bata 😏",
    "Kabhi class mein copy ki hai? Kitni baar? 📚",
    "Sabse weird sapna kya aaya tha kabhi? 💭",
    "Agar ek din invisible ho jao toh kya karoge? 😈",
    "Phone lock kyun hai? Kya chhupa raha/rahi ho? 🔐",
    "Kisi ko block kiya hai? Kyun? 😶",
    "Khud ko 1-10 mein looks mein kitna doge? 😂",
    "Aaj tak sabse bada prank kya khela hai? 🤣",
    "Ek cheez jo kabhi parents ko nahi bataya? 🤫",
    "Last time kab jhooth bola/boli? Kya tha? 😬",
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
    "Khud ko roast karo 3 lines mein, funny wala 😂",
    "Group mein ek shayari bhejo abhi ke abhi 📝",
    "Apna secret talent abhi prove karo group mein 🎭",
    "Next message mein sirf backwards likhna (hello = olleh) 🔄",
    "Khud ki baby voice mein ek sentence bolke voice note bhejo 👶",
    "Apne favourite celebrity ka impression karo voice note mein 🌟",
    "Apne profile pic ko 1 ghante ke liye kisi funny pic se badlo 😂",
]

WYR_QUESTIONS = [
    "🤔 *Would You Rather?*\n\n*A)* Hamesha jhooth pakda jaye\n*B)* Kabhi sach na bol pao",
    "🤔 *Would You Rather?*\n\n*A)* Bina phone ke 1 saal\n*B)* Bina dost ke 1 saal",
    "🤔 *Would You Rather?*\n\n*A)* Sabke thoughts read kar pao\n*B)* Future dekh pao",
    "🤔 *Would You Rather?*\n\n*A)* Famous ho par broke ho\n*B)* Rich ho par unknown",
    "🤔 *Would You Rather?*\n\n*A)* Udd sako\n*B)* Invisible ho sako",
    "🤔 *Would You Rather?*\n\n*A)* Hamesha dance karte raho\n*B)* Hamesha gaate raho",
    "🤔 *Would You Rather?*\n\n*A)* 10 saal pehle wapas jao\n*B)* 10 saal aage chale jao",
    "🤔 *Would You Rather?*\n\n*A)* Apni pasand ki life karo par akele raho\n*B)* Log chahein par boring job karo",
    "🤔 *Would You Rather?*\n\n*A)* Hamesha sach bolna pade\n*B)* Kisi bhi locked darwaze ko khol sako",
    "🤔 *Would You Rather?*\n\n*A)* Superstar bano par zero privacy\n*B)* Normal life par ek secret superpower",
]

ROAST_LINES = [
    "Bhai tera wifi ka signal teri life se zyada strong hai! 📶",
    "Teri personality itni bland hai ki unsalted chips bhi interesting lage tere saamne! 🍟",
    "Tu itna/itni slow hai ki kachhua bhi tera speed dekh ke hasega! 🐢",
    "Tera fashion sense dekh ke kapde khud rona lagein! 👗",
    "Teri jokes itni purani hain ki Wikipedia pe bhi nahi milti! 📖",
]

ZODIAC_TRAITS = {
    "aries": "🐏 *Aries* — Full fire! Leader type, thoda impulsive, but always first! 🔥",
    "taurus": "🐂 *Taurus* — Stubborn af, par reliable bhi! Khana aur aaram — life goals! 🍔",
    "gemini": "👯 *Gemini* — Ek minute serious, doosre minute meme. Dono personalities valid! 😂",
    "cancer": "🦀 *Cancer* — Sensitive soul, ghar ka pyaar, emotions ka ocean! 🌊",
    "leo": "🦁 *Leo* — King/Queen energy 24/7! Spotlight tera birth right hai! 👑",
    "virgo": "🧹 *Virgo* — Perfectionist! Sab kuch organize, sab kuch plan! 📋",
    "libra": "⚖️ *Libra* — Balance khojta/khojti hai har jagah! Decision lena... kal karein? 😅",
    "scorpio": "🦂 *Scorpio* — Mystery person! Intense, passionate, thoda dangerous 😏",
    "sagittarius": "🏹 *Sagittarius* — Adventure lover! Ek jagah nahi tikta/tikti! 🌍",
    "capricorn": "🐐 *Capricorn* — Hardworking machine! Goals set, achieve, repeat! 💼",
    "aquarius": "🪄 *Aquarius* — Rebel with a cause! Unique thinker, future ka insaan! 🛸",
    "pisces": "🐟 *Pisces* — Dreamer supreme! Emotions deep, creativity wild! 🎨",
}

FORTUNE_COOKIES = [
    "🔮 Aaj tera din lucky hai — kisi ko propose karo! 💘",
    "🔮 Aaj kuch unexpected hoga... achha bhi ho sakta hai, bura bhi 😂",
    "🔮 Stars bol rahe hain: chai pi aur life enjoy karo ☕",
    "🔮 Teri mehnat rang layegi... bas thoda aur wait karo 🌈",
    "🔮 Koi tujhe secretly like karta/karti hai... 👀 Hint: group mein hai!",
    "🔮 Love life mein twist aane wala hai! Ready reh 💕",
    "🔮 Paisa aayega... ya jayega. Dono possibilities hain 😂",
    "🔮 Teri energy aaj off the charts hai! Use it wisely 🔥",
]

COMPLIMENTS = [
    "Yaar tu toh sach mein gem hai! 💎 Group ka sabse pyaara insaan!",
    "Teri smile dekh ke log apni problems bhool jaate hain 😊✨",
    "Tu jo bhi karta/karti hai, full dedication se! Respect! 🙏",
    "Teri vibe alag hi level ki hai! Duniya tere jaisi aur chahiye 🌟",
    "Tu toh walking sunshine hai ☀️ Sab khush ho jaate hain tere aane se!",
    "Teri sense of humor top-tier hai! Comedy king/queen 😂👑",
    "Tu sirf awesome nahi, extra awesome hai! 🔥",
]

EIGHT_BALL_ANSWERS = [
    "🎱 Bilkul haan! 100% sure!",
    "🎱 Nahi... kabhi nahi 😂",
    "🎱 Shayad... stars theek nahi hain abhi",
    "🎱 Bahut chances hain! Try kar!",
    "🎱 Mujhe doubt hai... 🤔",
    "🎱 Haan, but thoda wait kar",
    "🎱 Ball keh rahi hai: NAH 😂",
    "🎱 Signs point to YES! 🎉",
    "🎱 Apne dil se pooch 😅",
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
    "Never have I ever... kisi ko dekh ke hasi roki ho 😆",
    "Never have I ever... dost ki bf/gf ko secretly like kiya hoon 😳",
    "Never have I ever... social media pe fake id banayi hai 🕵️",
    "Never have I ever... apne crush ko propose karne ki himmat nahi hui 💔",
    "Never have I ever... kisi ke liye likha letter deliver nahi kiya 💌",
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
        "q": "🧠 *TRIVIA TIME!*\n\nKitne countries mein Hindi primarily boli jaati hai?",
        "options": ["1", "4", "7", "12"],
        "answer": 1,
        "explanation": "Fiji, Mauritius, Suriname aur India — 4 countries! 🌍"
    },
    {
        "q": "🧠 *TRIVIA TIME!*\n\nChand tak pahunchne mein kitna time lagta hai?",
        "options": ["1 din", "3 din", "1 hafte", "1 mahina"],
        "answer": 1,
        "explanation": "Apollo missions ko approximately 3 din lage the! 🌙"
    },
]

# Mood keyword -> response list
MOOD_RESPONSES = {
    "happy": ["Wow finally koi khush hai! 😄🎉 Teri khushi se sab khush!", "Happy vibes! Keep smiling 🌟😄"],
    "sad": ["Aye yaar 😢 Kya hua? Sab saath hain 🫂", "Thodi der mein sab theek ho jayega! 💕"],
    "angry": ["Oye oye! 😠 Shant pani pi! Kya hua bata 👂", "Gussa toh hai par cute bhi lag raha/rahi hai 😂❤️"],
    "tired": ["Rest le yaar 🛌 Aaj ka quota complete!", "So ja jaldi 😴💤 Neend important hai!"],
    "hype": ["LESGOOO 🔥🔥🔥 Energy level max!", "Yeh vibe chahiye sab ko! 🚀⚡"],
    "meh": ["Theek hai theek hai 😐 Kal better hoga!", "Chal /truth ya /dare khel, mood set ho jayega 😏"],
}

# ===================================================
# SPIN BOTTLE — 8-direction arrow system
# ===================================================
SPIN_POSITIONS = {
    "⬆️": "upar wala bande/bandi",
    "↗️": "upar-daayein wala bande/bandi",
    "➡️": "daayein wala bande/bandi",
    "↘️": "neeche-daayein wala bande/bandi",
    "⬇️": "neeche wala bande/bandi",
    "↙️": "neeche-baayein wala bande/bandi",
    "⬅️": "baayein wala bande/bandi",
    "↖️": "upar-baayein wala bande/bandi",
}

async def spin_bottle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        user = update.effective_user.first_name
        spin_msg = await update.message.reply_text(
            f"🍾 *{user} ne bottle spin ki!*\n_Ghoom rahi hai..._",
            parse_mode='Markdown'
        )

        frames = ["🍾💨", "💨🍾", "🍾⚡", "⚡🍾", "🌀🍾", "🍾🌀", "🎯"]
        for frame in frames:
            await spin_msg.edit_text(f"*{frame} Ghoom rahi hai...*", parse_mode='Markdown')
            await asyncio.sleep(0.35)

        arrow = random.choice(list(SPIN_POSITIONS.keys()))
        position_label = SPIN_POSITIONS[arrow]
        action = random.choice([
            "Truth lo! 🔴", "Dare lo! 🟠",
            "Compliment do group mein! 💕",
            "Khud ko roast karo! 😂",
            "Apna sabse embarrassing secret batao! 😳",
        ])

        keyboard = [
            [
                InlineKeyboardButton("↖️ Main hun!", callback_data=f'spin_claim_↖️'),
                InlineKeyboardButton("⬆️ Main hun!", callback_data=f'spin_claim_⬆️'),
                InlineKeyboardButton("↗️ Main hun!", callback_data=f'spin_claim_↗️'),
            ],
            [
                InlineKeyboardButton("⬅️ Main hun!", callback_data=f'spin_claim_⬅️'),
                InlineKeyboardButton("🍾 Spin Again", callback_data='spin'),
                InlineKeyboardButton("➡️ Main hun!", callback_data=f'spin_claim_➡️'),
            ],
            [
                InlineKeyboardButton("↙️ Main hun!", callback_data=f'spin_claim_↙️'),
                InlineKeyboardButton("⬇️ Main hun!", callback_data=f'spin_claim_⬇️'),
                InlineKeyboardButton("↘️ Main hun!", callback_data=f'spin_claim_↘️'),
            ],
        ]

        await spin_msg.edit_text(
            f"🍾 *BOTTLE RUKI!*\n━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 Bottle point kar rahi hai: *{arrow}* — *{position_label}* taraf!\n\n"
            f"👆 Jo us direction mein baithe hain apna arrow dabao!\n"
            f"📌 Unhe milega: *{action}*\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"_Apni position ke hisaab se button press karo!_ 😈",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Spin error: {e}")


# ===================================================
# TRUTH
# ===================================================
async def truth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        question = random.choice(TRUTH_QUESTIONS)
        user = update.effective_user.first_name
        text = (
            f"🔴 *TRUTH TIME!* 🔴\n━━━━━━━━━━━━━━━━━\n"
            f"🎯 *{user}* ko yeh poochha gaya:\n\n💬 _{question}_\n\n"
            f"━━━━━━━━━━━━━━━━━\nSach bol de, koi judge nahi karega... ya karega? 😏"
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


# ===================================================
# DARE
# ===================================================
async def dare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        challenge = random.choice(DARE_CHALLENGES)
        user = update.effective_user.first_name
        text = (
            f"🟠 *DARE TIME!* 🟠\n━━━━━━━━━━━━━━━━━\n"
            f"😈 *{user}* ko yeh dare mila:\n\n⚡ _{challenge}_\n\n"
            f"━━━━━━━━━━━━━━━━━\nComplete karo aur pao 10 points! 😂"
        )
        keyboard = [[
            InlineKeyboardButton("✅ Done! +10pts", callback_data='dare_done'),
            InlineKeyboardButton("🔄 New Dare", callback_data='dare'),
            InlineKeyboardButton("🔴 Back to Truth", callback_data='truth')
        ]]
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Dare error: {e}")


# ===================================================
# COUPLE MATCH — command sender's name as person1
# ===================================================
async def couple_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        person1 = update.effective_user.first_name

        if update.message.reply_to_message:
            person2 = update.message.reply_to_message.from_user.first_name
        elif context.args:
            person2 = " ".join(context.args).replace("@", "")
        else:
            pool = [
                "Rahul 🕵️", "Priya 🌸", "Arjun 😎", "Sneha 💕", "Vikram 🔥",
                "Ananya 🌼", "Rohan 🎸", "Kavya 🦋", "Aditya ⚡", "Pooja 🌹",
                "Dev 🏆", "Simran 💫", "Karan 😏", "Nisha 🌙", "Meera 🎭",
                "Aarav 🚀", "Diya 🕯️", "Veer 🗡️", "Riya 🌺", "Kabir 🎵"
            ]
            person2 = random.choice(pool)

        compatibility = random.randint(55, 100)
        if compatibility >= 90:
            verdict = "💑 SOULMATES! Shaadi fix karo! 💍"
            emoji = "❤️❤️❤️"
        elif compatibility >= 75:
            verdict = "😍 Perfect couple material! 🌹"
            emoji = "❤️❤️"
        elif compatibility >= 60:
            verdict = "🤔 Thodi mehnat lagegi... par ho sakta hai! 😂"
            emoji = "💛"
        else:
            verdict = "💀 Yaar... dono enemies hi better lagte ho! 😂"
            emoji = "💔"

        bar = "▓" * int(compatibility / 10) + "░" * (10 - int(compatibility / 10))
        trope = random.choice([
            "Made in heaven ⭐", "Rivals to lovers 🔥",
            "Best friends first 💕", "Opposites attract 🧲",
            "Childhood crush 🌸", "Enemies to lovers 😤❤️"
        ])
        p2_base = person2.split()[0]
        ship = person1[:max(2, len(person1)//2 + 1)] + p2_base[:max(2, len(p2_base)//2)]

        text = (
            f"💘 *COUPLE MATCHING MACHINE* 💘\n━━━━━━━━━━━━━━━━━\n"
            f"👫 *{person1}* 💕 *{person2}*\n\n"
            f"🔥 Compatibility:\n`[{bar}]` *{compatibility}%*\n\n"
            f"{emoji} *Verdict:* _{verdict}_\n"
            f"🌟 *Trope:* _{trope}_\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💫 Ship name: *{ship}* 😂"
        )
        keyboard = [[
            InlineKeyboardButton("💘 Dobara Match!", callback_data='couple'),
            InlineKeyboardButton("⚡ Ship Name", callback_data='ship_random')
        ]]
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Couple error: {e}")


# ===================================================
# WOULD YOU RATHER — proper vote count on buttons
# ===================================================
async def would_you_rather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        question = random.choice(WYR_QUESTIONS)
        lines = [l for l in question.split('\n') if l.strip()]
        opt_a = lines[2].replace("*A)*", "").strip() if len(lines) > 2 else "Option A"
        opt_b = lines[4].replace("*B)*", "").strip() if len(lines) > 4 else "Option B"

        poll_id = f"wyr_{update.effective_chat.id}_{update.message.message_id}"

        # Save WYR poll state
        polls = load_json("active_polls.json", {})
        polls[poll_id] = {
            "type": "wyr",
            "question": question,
            "options": [opt_a, opt_b],
            "votes": {"0": 0, "1": 0},
            "voters": {}
        }
        save_json("active_polls.json", polls)

        keyboard = [[
            InlineKeyboardButton(f"🅰️ {opt_a[:25]} — 0 votes", callback_data=f'wyr_vote_0_{poll_id}'),
        ], [
            InlineKeyboardButton(f"🅱️ {opt_b[:25]} — 0 votes", callback_data=f'wyr_vote_1_{poll_id}'),
        ]]
        await update.message.reply_text(
            f"{question}\n\n_Vote karo! Count update hoga_ 👇",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"WYR error: {e}")


# ===================================================
# ROAST
# ===================================================
async def roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        if update.message.reply_to_message:
            target_name = update.message.reply_to_message.from_user.first_name
        elif context.args:
            target_name = " ".join(context.args).replace("@", "")
        else:
            target_name = update.effective_user.first_name + " (khud ko)"

        roast_msg = await update.message.reply_text("😈 *AI Roast Engine charging...*", parse_mode='Markdown')
        prompt = f"""Ek brutal funny Hinglish roast likho '{target_name}' ke liye.
- 4-5 lines
- Comedy style, offensive nahi
- Hinglish mix, emojis use karo
- End mein soft landing line"""
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


# ===================================================
# CONFESS — react buttons with working count
# ===================================================
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
        confession_id = len(confessions) + 1
        confessions.append({
            "text": confession_text,
            "timestamp": datetime.now().isoformat(),
            "id": confession_id,
            "reactions": {"heart": 0, "woah": 0}
        })
        save_json(CONFESS_FILE, confessions)
        try:
            await update.message.delete()
        except:
            pass

        keyboard = [[
            InlineKeyboardButton("❤️ Relate! (0)", callback_data=f'confess_heart_{confession_id}'),
            InlineKeyboardButton("😮 Woah! (0)", callback_data=f'confess_woah_{confession_id}')
        ]]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"💌 *ANONYMOUS CONFESSION #{confession_id}* 💌\n━━━━━━━━━━━━━━━━━\n\n"
                f"_{confession_text}_\n\n━━━━━━━━━━━━━━━━━\n"
                f"😶 *Sender ka naam? Sirf dil jaanta hai...* 🌙"
            ),
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Confess error: {e}")


# ===================================================
# SHIP NAME
# ===================================================
async def ship_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        if context.args and len(context.args) >= 2:
            name1 = context.args[0]
            name2 = context.args[1]
        elif update.message.reply_to_message:
            name1 = update.effective_user.first_name
            name2 = update.message.reply_to_message.from_user.first_name
        else:
            name1 = update.effective_user.first_name
            name2 = random.choice(["Rahul", "Priya", "Arjun", "Sneha", "Riya", "Dev"])

        ship = name1[:max(2, len(name1)//2 + 1)] + name2[max(0, len(name2)//2):]
        compatibility = random.randint(50, 100)
        try:
            prompt = f"Write a funny 2-line Hinglish love story about '{name1}' and '{name2}' called '{ship}'. Light and fun with emojis."
            response = model.generate_content(prompt)
            story = response.text[:300]
        except:
            story = f"{name1} aur {name2} ek duje ke liye bane hain! 💕"

        await update.message.reply_text(
            f"⚡ *SHIP NAME GENERATOR* ⚡\n━━━━━━━━━━━━━━━━━\n"
            f"👫 *{name1}* + *{name2}*\n\n"
            f"💑 *Ship Name:* `{ship}`\n💯 *Score:* `{compatibility}%`\n\n"
            f"📖 *Love Story:*\n_{story}_\n━━━━━━━━━━━━━━━━━",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ship error: {e}")


# ===================================================
# RATE USER
# ===================================================
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
        avg = sum(categories.values()) / len(categories)
        rating_text = f"📊 *OFFICIAL RATING: {target}* 📊\n━━━━━━━━━━━━━━━━━\n\n"
        for cat, score in categories.items():
            bar = "▓" * score + "░" * (10 - score)
            rating_text += f"{cat}: `[{bar}]` {score}/10\n"
        rating_text += f"\n━━━━━━━━━━━━━━━━━\n⭐ *Overall:* `{avg:.1f}/10`\n"
        if avg >= 8:
            rating_text += "🔥 _Legend hai!_"
        elif avg >= 6:
            rating_text += "😎 _Solid player!_"
        elif avg >= 4:
            rating_text += "😐 _Theek hai... bas._"
        else:
            rating_text += "💀 _Koshish karte raho!_"
        await update.message.reply_text(rating_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Rate error: {e}")


# ===================================================
# NGL
# ===================================================
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


# ===================================================
# FORTUNE
# ===================================================
async def fortune_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        user = update.effective_user.first_name
        fortune_msg = await update.message.reply_text("🔮 *Crystal ball gazing...*", parse_mode='Markdown')
        await asyncio.sleep(1.5)
        try:
            prompt = f"Give a fun mysterious Hinglish fortune cookie prediction for '{user}' today. 2-3 lines, emojis, vague yet exciting."
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
            f"_Disclaimer: Bot ki bakwaas hai, seriously mat lo 😂_",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Fortune error: {e}")


# ===================================================
# 8 BALL
# ===================================================
async def eight_ball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        if not context.args:
            await update.message.reply_text(
                "🎱 *Magic 8 Ball*\n\nUsage: `/8ball [apna question]`",
                parse_mode='Markdown'
            )
            return
        question = " ".join(context.args)
        ball_msg = await update.message.reply_text("🎱 *8 Ball soch rahi hai...*", parse_mode='Markdown')
        await asyncio.sleep(1.2)
        await ball_msg.edit_text(
            f"🎱 *MAGIC 8 BALL*\n━━━━━━━━━━━━━━━━━\n"
            f"❓ *Q:* _{question}_\n\n"
            f"💬 *A:* {random.choice(EIGHT_BALL_ANSWERS)}\n━━━━━━━━━━━━━━━━━",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"8ball error: {e}")


# ===================================================
# ZODIAC
# ===================================================
async def zodiac_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        if not context.args:
            await update.message.reply_text(
                f"♈ *ZODIAC READER*\n\nUsage: `/zodiac [sign]`\n\nSigns: `{', '.join(ZODIAC_TRAITS.keys())}`",
                parse_mode='Markdown'
            )
            return
        sign = context.args[0].lower()
        if sign in ZODIAC_TRAITS:
            trait = ZODIAC_TRAITS[sign]
            try:
                response = model.generate_content(f"Funny Hinglish 2-line daily horoscope for {sign} today. Emojis.")
                daily = response.text
            except:
                daily = "Aaj ka din kuch aur hi scene laayega! 🌟"
            await update.message.reply_text(
                f"✨ *ZODIAC READING* ✨\n━━━━━━━━━━━━━━━━━\n\n"
                f"{trait}\n\n📅 *Aaj Ka Scene:*\n_{daily}_\n━━━━━━━━━━━━━━━━━",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ '{sign}' nahi pata! Valid sign likhna.")
    except Exception as e:
        logger.error(f"Zodiac error: {e}")


# ===================================================
# COMPLIMENT
# ===================================================
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
            response = model.generate_content(f"Genuine heartwarming Hinglish compliment for '{target}'. 3-4 lines. Emojis.")
            compliment = response.text
        except:
            compliment = random.choice(COMPLIMENTS)

        await comp_msg.edit_text(
            f"💐 *COMPLIMENT FOR: {target}* 💐\n━━━━━━━━━━━━━━━━━\n\n"
            f"_{compliment}_\n\n━━━━━━━━━━━━━━━━━\n💕 _Bot ki taraf se pyaar!_",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Compliment error: {e}")


# ===================================================
# MOOD — set mood + tag-based auto-response in handle_message
# ===================================================
async def mood_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        user = update.effective_user
        moods = load_json(MOOD_FILE, {})

        if context.args:
            mood_text = " ".join(context.args)
            moods[str(user.id)] = {
                "name": user.first_name,
                "username": (user.username or "").lower(),
                "mood": mood_text,
                "time": datetime.now().isoformat()
            }
            save_json(MOOD_FILE, moods)
            try:
                response = model.generate_content(
                    f"React to mood '{mood_text}' in Hinglish. 2-line supportive response with emojis."
                )
                reaction = response.text
            except:
                reaction = f"'{mood_text}' mood note kar liya! 💕"

            await update.message.reply_text(
                f"😊 *Mood Set!*\n\n🎭 *{user.first_name}'s Mood:* _{mood_text}_\n\n_{reaction}_\n\n"
                f"_Ab jab koi group mein tag karega toh mood ke hisaab se reply milega!_ 🎭",
                parse_mode='Markdown'
            )
        else:
            uid = str(user.id)
            if uid in moods:
                m = moods[uid]
                await update.message.reply_text(
                    f"🎭 *{user.first_name} ka current mood:*\n\n_{m['mood']}_\n\n_Change: /mood [naya mood]_",
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
                    "🎭 *Apna Mood Select Karo!*\n\nOr `/mood [apna mood]` type karo:",
                    parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
                )
    except Exception as e:
        logger.error(f"Mood error: {e}")


# ===================================================
# STREAK
# ===================================================
async def streak_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        user = update.effective_user
        current_streak = update_streak(user.id, user.first_name)
        streaks = load_json(STREAKS_FILE, {})
        max_streak = streaks.get(str(user.id), {}).get("max_streak", current_streak)
        emoji = "🔥🔥🔥" if current_streak >= 7 else "🔥🔥" if current_streak >= 3 else "🔥"
        title = "LEGENDARY!" if current_streak >= 7 else "ON FIRE!" if current_streak >= 3 else "Keep it up!"
        await update.message.reply_text(
            f"🔥 *{user.first_name}'s DAILY STREAK* 🔥\n━━━━━━━━━━━━━━━━━\n\n"
            f"{emoji} *Current:* `{current_streak} days`\n"
            f"🏆 *Best:* `{max_streak} days`\n\n"
            f"⚡ *Status:* _{title}_\n━━━━━━━━━━━━━━━━━\n"
            f"_Roz kheloge toh streak badhegi! 💪_",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Streak error: {e}")


# ===================================================
# ASK AI
# ===================================================
async def ask_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        if not context.args:
            await update.message.reply_text("🤖 Usage: `/ask [tera sawaal]`", parse_mode='Markdown')
            return
        question = " ".join(context.args)
        user = update.effective_user.first_name
        thinking_msg = await update.message.reply_text("🤖 *AI soch raha hai...*", parse_mode='Markdown')
        try:
            response = model.generate_content(
                f'Tu Party Riot Bot hai. User "{user}" ne poochha: "{question}". Hinglish mein jawab de, fun aur short (3-5 lines). Emojis use karo.'
            )
            answer = response.text
        except:
            answer = "Server load pe hai! Thodi der baad try karo 😅"
        await thinking_msg.edit_text(
            f"🤖 *AI KA JAWAB* 🤖\n━━━━━━━━━━━━━━━━━\n\n❓ _{question}_\n\n💬 {answer}\n━━━━━━━━━━━━━━━━━",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ask error: {e}")


# ===================================================
# RANDOM NUMBER
# ===================================================
async def random_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        min_num, max_num = 1, 100
        if context.args:
            try:
                if len(context.args) == 1:
                    max_num = int(context.args[0])
                else:
                    min_num, max_num = int(context.args[0]), int(context.args[1])
            except:
                pass
        result = random.randint(min_num, max_num)
        await update.message.reply_text(
            f"🎲 *RANDOM NUMBER*\n━━━━━━━━━━━━━━━━━\n"
            f"Range: `{min_num}` to `{max_num}`\n\n"
            f"🎯 *Result: `{result}`*\n━━━━━━━━━━━━━━━━━\n_Kismat ne decide kiya!_ 😂",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"RNG error: {e}")


# ===================================================
# BATTLE
# ===================================================
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

        battle_msg = await update.message.reply_text("⚔️ *Battle loading...*", parse_mode='Markdown')
        for frame in [f"⚔️ *{challenger}* VS *{opponent}*", "💥 Round 1!", "🔥 Fighting...", "⚡ Power rising!", "🏆 Winner is..."]:
            await battle_msg.edit_text(frame, parse_mode='Markdown')
            await asyncio.sleep(0.7)

        winner = random.choice([challenger, opponent])
        loser = opponent if winner == challenger else challenger
        try:
            response = model.generate_content(
                f"Funny 3-line Hinglish battle between '{challenger}' and '{opponent}' — '{winner}' wins. Dramatic + emojis."
            )
            commentary = response.text
        except:
            commentary = f"{winner} ne {loser} ko defeat kar diya! Legendary! 🔥"

        await battle_msg.edit_text(
            f"⚔️ *EPIC BATTLE RESULT* ⚔️\n━━━━━━━━━━━━━━━━━\n"
            f"🏆 *WINNER: {winner}*\n💀 *Defeated: {loser}*\n\n"
            f"📖 *Commentary:*\n_{commentary}_\n━━━━━━━━━━━━━━━━━",
            parse_mode='Markdown'
        )
        if winner == challenger:
            update_leaderboard(update.effective_user.id, challenger, 5)
    except Exception as e:
        logger.error(f"Battle error: {e}")


# ===================================================
# FACT
# ===================================================
async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        from utils import model
        fact_msg = await update.message.reply_text("🌍 *Fact dhundh raha hoon...*", parse_mode='Markdown')
        try:
            topic = random.choice(["science", "history", "technology", "animals", "space", "India", "food", "human body"])
            response = model.generate_content(
                f"Mind-blowing fact about {topic} in Hinglish. 2-3 sentences. Start with 'Did you know'. Emojis."
            )
            fact = response.text
        except:
            fact = "Did you know? Octopus ke teen dil hote hain! 🐙"

        keyboard = [[InlineKeyboardButton("🌍 Aur Fact!", callback_data='fact')]]
        await fact_msg.edit_text(
            f"🌍 *RANDOM COOL FACT* 🌍\n━━━━━━━━━━━━━━━━━\n\n"
            f"{fact}\n\n━━━━━━━━━━━━━━━━━\n_Sach hai, Google kar le! 😂_",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Fact error: {e}")


# ===================================================
# NHIE — "Next" edits same message, not new message
# ===================================================
async def never_have_i_ever(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        statement = random.choice(NEVER_HAVE_I_EVER)
        keyboard = [[
            InlineKeyboardButton("✅ Maine kiya!", callback_data='nhie_done'),
            InlineKeyboardButton("❌ Maine nahi kiya", callback_data='nhie_notdone'),
        ], [
            InlineKeyboardButton("🔄 Aagla Statement", callback_data='nhie_next')
        ]]
        await update.message.reply_text(
            f"🃏 *NEVER HAVE I EVER* 🃏\n━━━━━━━━━━━━━━━━━\n\n"
            f"_{statement}_\n\n━━━━━━━━━━━━━━━━━\n_Honestly jawab dena! 😏_",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"NHIE error: {e}")


# ===================================================
# TRIVIA
# ===================================================
async def trivia_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        q_data = random.choice(TRIVIA_QUESTIONS)
        keyboard = [[InlineKeyboardButton(
            opt, callback_data=f'trivia_{i}_{q_data["answer"]}_{update.effective_user.id}'
        )] for i, opt in enumerate(q_data["options"])]
        await update.message.reply_text(
            f"{q_data['q']}\n\n_Sahi jawab do aur points pao!_ 🏆",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Trivia error: {e}")


# ===================================================
# POLL — working buttons with vote count
# ===================================================
async def poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_banned(update): return
    try:
        if not context.args:
            await update.message.reply_text(
                "📊 *Poll Creator*\n\n"
                "Usage: `/poll [question]`\n_Auto: Haan/Nahi/Maybe_\n\n"
                "Custom: `/poll question | option1 | option2`\n\n"
                "_Example: /poll Chai ya Coffee? | Chai ☕ | Coffee ☕_",
                parse_mode='Markdown'
            )
            return

        full_text = " ".join(context.args)
        if "|" in full_text:
            parts = [p.strip() for p in full_text.split("|")]
            question = parts[0]
            options = parts[1:5]
        else:
            question = full_text
            options = ["Haan ✅", "Nahi ❌", "Maybe 🤔"]

        poll_id = f"{update.effective_chat.id}_{update.message.message_id}"

        polls = load_json("active_polls.json", {})
        polls[poll_id] = {
            "type": "poll",
            "question": question,
            "options": options,
            "votes": {str(i): 0 for i in range(len(options))},
            "voters": {}
        }
        save_json("active_polls.json", polls)

        keyboard = [[InlineKeyboardButton(
            f"{opt} — 0 votes", callback_data=f'poll_vote_{i}_{poll_id}'
        )] for i, opt in enumerate(options)]

        await update.message.reply_text(
            f"📊 *GROUP POLL*\n━━━━━━━━━━━━━━━━━\n\n❓ *{question}*\n\n_Vote karo! 👇_",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Poll error: {e}")
        
