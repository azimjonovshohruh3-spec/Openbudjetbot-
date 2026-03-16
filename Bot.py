import sqlite3
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

TOKEN = "8760270032:AAHmFwJbNnJSRWobpz72VEXLEabksC5Pt3Y"
ADMIN_ID = 8476987832  # Sizning Telegram ID

# ===== DATABASE =====
conn = sqlite3.connect("bot.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    phone TEXT,
    voted INTEGER DEFAULT 0,
    screenshot INTEGER DEFAULT 0
)
""")
conn.commit()

# Agar eski bazada username ustuni bo‘lmasa, qo‘shamiz
try:
    c.execute("ALTER TABLE users ADD COLUMN username TEXT")
    conn.commit()
except sqlite3.OperationalError:
    pass

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username or "Noma’lum"
    
    c.execute("INSERT OR IGNORE INTO users(user_id, username) VALUES(?, ?)", (user_id, username))
    c.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
    conn.commit()

    contact_button = KeyboardButton("📱 Telefon raqamingizni yuborish", request_contact=True)
    keyboard = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Diqqat ❗\n\n"
        "Biz sizga 100 ming so‘m kabi yolg'on va'dalar bermaymiz.\n"
        "Ovoz narxi: 20 000 so‘m 💰\n\n"
        "Ovoz bergandan so'ng screenshot yuboring.\n\n"
        "Iltimos, avval telefon raqamingizni yuboring.",
        reply_markup=keyboard,
    )

# ===== TELEFON QABUL =====
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user = update.message.from_user
    if contact:
        phone_number = contact.phone_number
        c.execute("UPDATE users SET phone=? WHERE user_id=?", (phone_number, user.id))
        conn.commit()

        await update.message.reply_text(
            f"📱 Telefon raqamingiz qabul qilindi: {phone_number}\nEndi ovoz berishingiz mumkin."
        )

        # Inline tugmalarni alohida yuboramiz
        inline_keyboard = [
            [InlineKeyboardButton("🗳 Ovoz berish", url="https://openbudget.uz/initiative/053464928011")],
            [InlineKeyboardButton("✅ Ovoz berdim", callback_data="voted")],
        ]
        await update.message.reply_text(
            "⬇️ Quyidagi tugmalardan foydalaning:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )

# ===== OVOZ BERDIM =====
async def voted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    c.execute("UPDATE users SET voted=1 WHERE user_id=?", (user_id,))
    conn.commit()
    await query.edit_message_text("✅ Rahmat!\n\nOvoz berganingizni tasdiqlash uchun screenshot yuboring 📸")

# ===== SCREENSHOT =====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message
    user = user_msg.from_user

    c.execute("SELECT screenshot, username, phone FROM users WHERE user_id=?", (user.id,))
    data = c.fetchone()
    if data and data[0] == 1:
        await update.message.reply_text("⚠️ Siz allaqachon screenshot yuborgansiz.")
        return

    photo = user_msg.photo[-1].file_id
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlandi", callback_data=f"ok_{user.id}"),
         InlineKeyboardButton("❌ Rad etildi", callback_data=f"no_{user.id}")]
    ]

    username = data[1] if data[1] else "Noma’lum"
    phone = data[2] if data[2] else "Noma’lum"

    await context.bot.send_photo(
        ADMIN_ID,
        photo,
        caption=f"📸 Yangi screenshot\nUsername: @{username}\nTelefon: {phone}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    c.execute("UPDATE users SET screenshot=1 WHERE user_id=?", (user.id,))
    conn.commit()
    await update.message.reply_text("✅ Screenshot yuborildi. Admin tekshiradi.")

# ===== ADMIN TASDIQ =====
async def admin_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[1])
    if query.data.startswith("ok"):
        await context.bot.send_message(user_id, "✅ Ovoz tasdiqlandi. Tez orada siz bilan bog'lanamiz.")
        await query.edit_message_caption("✅ TASDIQLANDI")
    elif query.data.startswith("no"):
        await context.bot.send_message(user_id, "❌ Screenshot rad etildi. Iltimos to'g'ri screenshot yuboring.")
        await query.edit_message_caption("❌ RAD ETILDI")

# ===== ADMIN PANEL =====
async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    c.execute("SELECT username, phone, voted, screenshot FROM users")
    users_data = c.fetchall()
    total_users = len(users_data)
    total_votes = sum(1 for u in users_data if u[2] == 1)
    total_screenshots = sum(1 for u in users_data if u[3] == 1)

    msg = f"📊 ADMIN PANEL\n\n👥 Foydalanuvchilar: {total_users}\n🗳 Ovoz berganlar: {total_votes}\n📸 Screenshot yuborganlar: {total_screenshots}\n\n"
    msg += "Username | Telefon | Ovoz | Screenshot\n"
    msg += "-"*40 + "\n"

    for u in users_data:
        username, phone, voted, screenshot = u
        voted_text = "Ha" if voted else "Yo‘q"
        shot_text = "Ha" if screenshot else "Yo‘q"
        phone_text = phone if phone else "Noma’lum"
        msg += f"{username} | {phone_text} | {voted_text} | {shot_text}\n"

    await update.message.reply_text(msg)

# ===== TOP FOYDALANUVCHILAR =====
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    c.execute("SELECT username, screenshot FROM users ORDER BY screenshot DESC LIMIT 10")
    data = c.fetchall()
    msg = "🏆 TOP FOYDALANUVCHILAR\n\n"
    for i, user in enumerate(data, start=1):
        username, screenshot = user
        msg += f"{i}. {username} | Screenshot: {screenshot}\n"
    await update.message.reply_text(msg)

# ===== BROADCAST =====
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    msg = " ".join(context.args)
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()

    async def send_batch(batch):
        tasks = [context.bot.send_message(u[0], msg) for u in batch]
        await asyncio.gather(*tasks)

    for i in range(0, len(users), 20):
        batch = users[i : i + 20]
        await send_batch(batch)

    await update.message.reply_text("✅ Xabar yuborildi")

# ===== BOT START =====
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(CallbackQueryHandler(voted, pattern="voted"))
app.add_handler(CallbackQueryHandler(admin_check, pattern="^(ok_|no_)"))
app.add_handler(CommandHandler("panel", panel))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CommandHandler("top", top))

print("⚡ Supper mukammal mono bot ishga tushdi 24/7 ✅")
app.run_polling(poll_interval=1)
