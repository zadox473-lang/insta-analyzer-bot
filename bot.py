# ================= IMPORTS =================
import os
import random
import hashlib
import sqlite3
import requests
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler,
    CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

# ================= CONFIG =================
# FIXED: Token ko directly string mein dala gaya hai
BOT_TOKEN = "8441563953:AAH6SU2IEu0uV5gfGhsYN_fYscvRCXRxVfI"
ADMIN_ID = int(os.getenv("ADMIN_ID", "8345525909"))

API_URL = "https://insta-profile-info-api.vercel.app/api/instagram.php?username="

FORCE_CHANNELS = [
    "@midnight_xaura",
    "@proxydominates"
]

PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# ================= DATABASE =================
db = sqlite3.connect("users.db", check_same_thread=False)
cur = db.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)")
db.commit()

def save_user(uid):
    cur.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (uid,))
    db.commit()

def total_users():
    cur.execute("SELECT COUNT(*) FROM users")
    res = cur.fetchone()
    return res[0] if res else 0

# ================= FORCE JOIN =================
async def is_joined(bot, user_id):
    for ch in FORCE_CHANNELS:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status in ("left", "kicked"):
                return False
        except:
            return False
    return True

def join_kb():
    btns = [[InlineKeyboardButton(f"📢 Join {c}", url=f"https://t.me/{c[1:]}")] for c in FORCE_CHANNELS]
    btns.append([InlineKeyboardButton("✅ Check Again", callback_data="check")])
    return InlineKeyboardMarkup(btns)

# ================= UI =================
def menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Deep Analysis", callback_data="deep")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ])

def after_kb(username):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Full Report", callback_data=f"report|{username}")],
        [InlineKeyboardButton("🔄 Analyze Again", callback_data="deep")],
        [InlineKeyboardButton("⬅️ Menu", callback_data="menu")]
    ])

# ================= API =================
def fetch_profile(username):
    try:
        r = requests.get(API_URL + username, timeout=20)
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("status") != "ok":
            return None
        return data.get("profile")
    except:
        return None

def download(url):
    r = requests.get(url, timeout=15)
    bio = BytesIO(r.content)
    bio.name = "pfp.jpg"
    return bio

# ================= ANALYSIS =================
def calc_risk(profile):
    username = profile.get("username", "user")
    bio = (profile.get("biography") or "").lower()
    private = profile.get("is_private", False)
    posts = int(profile.get("posts") or 0)

    seed = int(hashlib.sha256(username.encode()).hexdigest(), 16)
    rnd = random.Random(seed)

    pool = ["SCAM", "SPAM", "NUDITY", "HATE", "HARASSMENT", "BULLYING", "VIOLENCE"]

    if any(x in bio for x in ["music", "rapper", "artist"]):
        pool += ["DRUGS", "DRUGS"]

    if private and posts == 0:
        pool += ["SCAM", "SCAM"]

    rnd.shuffle(pool)
    selected = list(dict.fromkeys(pool))[:rnd.randint(1, 3)]

    issues, intensity = [], 0
    for i in selected:
        count = rnd.randint(1, 4)
        intensity += count
        issues.append(f"{count}x {i}")

    risk = min(95, 40 + intensity * 6 + (10 if private else 0))
    return risk, issues

# ================= TEXT =================
def report_text(username, profile, risk, issues):
    t = f"🎯 DEEP ANALYSIS REPORT\nProfile: @{username}\n\n"
    t += f"👥 Followers: {profile.get('followers',0)}\n"
    t += f"👤 Following: {profile.get('following',0)}\n"
    t += f"📸 Posts: {profile.get('posts',0)}\n"
    t += f"🔐 Private: {'Yes' if profile.get('is_private') else 'No'}\n\n"
    t += "🚨 DETECTED ISSUES\n"
    for i in issues:
        t += f"• {i}\n"
    t += f"\n⚠️ OVERALL RISK: {risk}%"
    return t

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    save_user(uid)

    if not await is_joined(context.bot, uid):
        await update.message.reply_text("❌ Please join all channels first.", reply_markup=join_kb())
        return

    await update.message.reply_text("✨ Welcome to Insta Analyzer Pro ✨", reply_markup=menu_kb())

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "check":
        if await is_joined(context.bot, q.from_user.id):
            await q.edit_message_text("✅ Access granted", reply_markup=menu_kb())
        else:
            await q.message.reply_text("❌ Join all channels", reply_markup=join_kb())

    elif q.data == "menu":
        await q.edit_message_text("🏠 Main Menu", reply_markup=menu_kb())

    elif q.data == "deep":
        context.user_data["wait"] = True
        await q.message.reply_text("👤 Send Instagram username:")

    elif q.data.startswith("report|"):
        username = q.data.split("|")[1]
        profile = fetch_profile(username)
        if not profile:
            await q.message.reply_text("❌ Profile error")
            return

        risk, issues = calc_risk(profile)
        await q.message.reply_text(report_text(username, profile, risk, issues), reply_markup=after_kb(username))

    elif q.data == "help":
        await q.message.reply_text("• Deep Analysis\n• Risk detection\n• Admin broadcast")

async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("wait"):
        return

    context.user_data["wait"] = False
    username = update.message.text.replace("@", "").strip()

    await update.message.reply_text("🔄 Analyzing...")

    profile = fetch_profile(username)
    if not profile:
        await update.message.reply_text("❌ Profile not found", reply_markup=menu_kb())
        return

    risk, issues = calc_risk(profile)
    caption = f"🎯 ANALYSIS COMPLETE\n@{username}\nRisk: {risk}%"

    pfp = profile.get("profile_pic_url_hd")
    if pfp:
        try:
            await update.message.reply_photo(photo=download(pfp), caption=caption, reply_markup=after_kb(username))
            return
        except:
            pass

    await update.message.reply_text(caption, reply_markup=after_kb(username))

# ================= ADMIN =================
async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(f"👥 Total users: {total_users()}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast message")
        return

    msg = " ".join(context.args)
    cur.execute("SELECT id FROM users")
    users = cur.fetchall()
    sent = 0

    for (uid,) in users:
        try:
            await context.bot.send_message(uid, msg)
            sent += 1
        except:
            pass

    await update.message.reply_text(f"✅ Broadcast sent to {sent} users")

# ================= RUN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_username))

    # WEBHOOK Setup (Recommended for Hosting)
    if WEBHOOK_URL:
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL
        )
    else:
        # Local testing ke liye polling
        app.run_polling()

if __name__ == "__main__":
    main()
