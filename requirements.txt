import logging
import random
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = "8846287029:AAEW5cNt2zWwoMCVRw6HhPyJsOhWGMl6Thc"

conn = sqlite3.connect('betting_bot.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    username TEXT,
    balance INTEGER DEFAULT 10,
    daily_bonus_date TEXT,
    referral_count INTEGER DEFAULT 0
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    amount INTEGER,
    date TEXT
)
''')
conn.commit()

def get_user(telegram_id):
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    return cursor.fetchone()

def create_user(telegram_id, username):
    cursor.execute('INSERT INTO users (telegram_id, username, balance) VALUES (?, ?, 10)', (telegram_id, username))
    conn.commit()
    return get_user(telegram_id)

def update_balance(telegram_id, amount):
    cursor.execute('UPDATE users SET balance = balance + ? WHERE telegram_id = ?', (amount, telegram_id))
    conn.commit()

def add_transaction(user_id, type, amount):
    cursor.execute('INSERT INTO transactions (user_id, type, amount, date) VALUES (?, ?, ?, ?)',
                   (user_id, type, amount, datetime.now().isoformat()))
    conn.commit()

def can_get_daily(telegram_id):
    cursor.execute('SELECT daily_bonus_date FROM users WHERE telegram_id = ?', (telegram_id,))
    row = cursor.fetchone()
    if row and row[0]:
        last_date = datetime.fromisoformat(row[0])
        if datetime.now() - last_date < timedelta(hours=24):
            remaining = 24 - (datetime.now() - last_date).seconds // 3600
            return False, remaining
    return True, 0

def set_daily_date(telegram_id):
    cursor.execute('UPDATE users SET daily_bonus_date = ? WHERE telegram_id = ?', (datetime.now().isoformat(), telegram_id))
    conn.commit()

def get_referral_link(telegram_id):
    return f"https://t.me/getfreeSkins_bot?start=ref_{telegram_id}"

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 رولت", callback_data="roulette"), InlineKeyboardButton("🪙 شیر یا خط", callback_data="coinflip")],
        [InlineKeyboardButton("💰 کیف پول", callback_data="wallet"), InlineKeyboardButton("🎁 سکه روزانه", callback_data="daily")],
        [InlineKeyboardButton("👥 معرفی", callback_data="referral"), InlineKeyboardButton("📊 تراکنش‌ها", callback_data="transactions")]
    ])

def roulette_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 قرمز", callback_data="roulette_red"), InlineKeyboardButton("⚫ مشکی", callback_data="roulette_black")],
        [InlineKeyboardButton("🟢 سبز", callback_data="roulette_green"), InlineKeyboardButton("🔙 منو", callback_data="menu")]
    ])

def coinflip_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🦅 شیر", callback_data="coinflip_heads"), InlineKeyboardButton("⚜️ خط", callback_data="coinflip_tails")],
        [InlineKeyboardButton("🔙 منو", callback_data="menu")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        user = create_user(update.effective_user.id, update.effective_user.username or "کاربر")
        args = context.args
        if args and args[0].startswith('ref_'):
            referrer_id = int(args[0].split('_')[1])
            referrer = get_user(referrer_id)
            if referrer:
                update_balance(referrer_id, 20)
                add_transaction(referrer[0], 'referral', 20)
                await context.bot.send_message(referrer_id, f"🎉 کاربر جدید با لینک شما ثبت‌نام کرد! ۲۰ سکه به حساب شما اضافه شد.")
    await update.message.reply_text(
        f"🎯 به ربات شرط‌بندی خوش آمدی، {update.effective_user.first_name}!\n\n"
        f"💰 موجودی: {user[3] if user else 10} سکه\n"
        f"🎁 سکه روزانه: ۷ سکه (هر ۲۴ ساعت)\n"
        f"👥 معرفی: ۲۰ سکه به ازای هر کاربر جدید\n\n"
        f"از منو استفاده کن، استاد!",
        reply_markup=main_menu()
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    await update.callback_query.message.edit_text(
        f"🎯 منوی اصلی\n💰 موجودی: {user[3] if user else 0} سکه",
        reply_markup=main_menu()
    )

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    await update.callback_query.message.edit_text(
        f"💰 کیف پول شما\n\nموجودی: {user[3]} سکه\nتعداد معرفی: {user[5]} نفر",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منو", callback_data="menu")]])
    )

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.callback_query.answer("ابتدا ثبت‌نام کنید!")
        return
    allowed, remaining = can_get_daily(update.effective_user.id)
    if not allowed:
        await update.callback_query.answer(f"⏳ {remaining} ساعت دیگر", show_alert=True)
        return
    update_balance(update.effective_user.id, 7)
    set_daily_date(update.effective_user.id)
    add_transaction(user[0], 'daily_bonus', 7)
    await update.callback_query.message.edit_text(
        f"🎁 سکه روزانه دریافت شد!\n💰 +۷ سکه\nموجودی جدید: {user[3] + 7} سکه",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منو", callback_data="menu")]])
    )

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    link = get_referral_link(update.effective_user.id)
    await update.callback_query.message.edit_text(
        f"👥 سیستم معرفی\n\nلینک معرفی شما:\n{link}\n\nتعداد معرفی‌ها: {user[5]} نفر\nپاداش هر معرف: ۲۰ سکه",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منو", callback_data="menu")]])
    )

async def transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    cursor.execute('SELECT type, amount, date FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT 10', (user[0],))
    rows = cursor.fetchall()
    text = "📊 آخرین تراکنش‌ها:\n\n" if rows else "📊 هیچ تراکنشی یافت نشد."
    for row in rows:
        text += f"• {row[0]}: {row[1]} سکه ({row[2][:10]})\n"
    await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 منو", callback_data="menu")]]))

async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.edit_text(
        "🎰 بازی رولت\n\nمبلغ شرط خود را انتخاب کن:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("۱۰", callback_data="bet_10"), InlineKeyboardButton("۵۰", callback_data="bet_50")],
            [InlineKeyboardButton("۱۰۰", callback_data="bet_100"), InlineKeyboardButton("۵۰۰", callback_data="bet_500")],
            [InlineKeyboardButton("🔙 منو", callback_data="menu")]
        ])
    )

async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = int(update.callback_query.data.split('_')[1])
    user = get_user(update.effective_user.id)
    if user[3] < amount:
        await update.callback_query.answer("موجودی کافی نیست!", show_alert=True)
        return
    context.user_data['bet'] = amount
    await update.callback_query.message.edit_text(
        f"🎰 رولت - مبلغ شرط: {amount} سکه\n\nرنگ مورد نظر را انتخاب کن:",
        reply_markup=roulette_keyboard()
    )

async def roulette_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.callback_query.data.split('_')[1]
    user = get_user(update.effective_user.id)
    bet = context.user_data.get('bet', 10)
    if user[3] < bet:
        await update.callback_query.answer("موجودی کافی نیست!", show_alert=True)
        return
    result = random.choices(['red', 'black', 'green'], weights=[49, 49, 2])[0]
    emoji = {'red': '🔴', 'black': '⚫', 'green': '🟢'}
    color_name = {'red': 'قرمز', 'black': 'مشکی', 'green': 'سبز'}
    if choice == result:
        win = bet * (36 if result == 'green' else 2)
        update_balance(update.effective_user.id, win)
        add_transaction(user[0], 'win', win)
        text = f"🎉 برد! نتیجه: {emoji[result]} {color_name[result]}\n💰 برد: {win} سکه"
    else:
        update_balance(update.effective_user.id, -bet)
        add_transaction(user[0], 'loss', -bet)
        text = f"💔 باخت! نتیجه: {emoji[result]} {color_name[result]}\n💰 باخت: {bet} سکه"
    user = get_user(update.effective_user.id)
    text += f"\n\n💳 موجودی جدید: {user[3]} سکه"
    await update.callback_query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎰 دوباره", callback_data="roulette")],
            [InlineKeyboardButton("🔙 منو", callback_data="menu")]
        ])
    )

async def coinflip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.edit_text(
        "🪙 بازی شیر یا خط\n\nمبلغ شرط خود را انتخاب کن:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("۱۰", callback_data="coin_bet_10"), InlineKeyboardButton("۵۰", callback_data="coin_bet_50")],
            [InlineKeyboardButton("۱۰۰", callback_data="coin_bet_100"), InlineKeyboardButton("۵۰۰", callback_data="coin_bet_500")],
            [InlineKeyboardButton("🔙 منو", callback_data="menu")]
        ])
    )

async def coin_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = int(update.callback_query.data.split('_')[2])
    user = get_user(update.effective_user.id)
    if user[3] < amount:
        await update.callback_query.answer("موجودی کافی نیست!", show_alert=True)
        return
    context.user_data['bet'] = amount
    await update.callback_query.message.edit_text(
        f"🪙 شیر یا خط - مبلغ شرط: {amount} سکه\n\nانتخاب خود را بکن:",
        reply_markup=coinflip_keyboard()
    )

async def coinflip_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.callback_query.data.split('_')[1]
    user = get_user(update.effective_user.id)
    bet = context.user_data.get('bet', 10)
    if user[3] < bet:
        await update.callback_query.answer("موجودی کافی نیست!", show_alert=True)
        return
    result = random.choice(['heads', 'tails'])
    result_name = {'heads': 'شیر 🦅', 'tails': 'خط ⚜️'}
    if choice == result:
        win = bet * 2
        update_balance(update.effective_user.id, win)
        add_transaction(user[0], 'win', win)
        text = f"🎉 برد! نتیجه: {result_name[result]}\n💰 برد: {win} سکه"
    else:
        update_balance(update.effective_user.id, -bet)
        add_transaction(user[0], 'loss', -bet)
        text = f"💔 باخت! نتیجه: {result_name[result]}\n💰 باخت: {bet} سکه"
    user = get_user(update.effective_user.id)
    text += f"\n\n💳 موجودی جدید: {user[3]} سکه"
    await update.callback_query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🪙 دوباره", callback_data="coinflip")],
            [InlineKeyboardButton("🔙 منو", callback_data="menu")]
        ])
    )

async def addcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 5213245493:
        await update.message.reply_text("⛔ نه")
        return
    update_balance(5213245493, 999999)
    await update.message.reply_text("✅ شد")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(menu, pattern="menu"))
    application.add_handler(CallbackQueryHandler(wallet, pattern="wallet"))
    application.add_handler(CallbackQueryHandler(daily, pattern="daily"))
    application.add_handler(CallbackQueryHandler(referral, pattern="referral"))
    application.add_handler(CallbackQueryHandler(transactions, pattern="transactions"))
    application.add_handler(CallbackQueryHandler(roulette, pattern="roulette"))
    application.add_handler(CallbackQueryHandler(bet, pattern="^bet_"))
    application.add_handler(CallbackQueryHandler(roulette_play, pattern="^roulette_"))
    application.add_handler(CallbackQueryHandler(coinflip, pattern="coinflip$"))
    application.add_handler(CallbackQueryHandler(coin_bet, pattern="^coin_bet_"))
    application.add_handler(CallbackQueryHandler(coinflip_play, pattern="^coinflip_"))
    application.add_handler(CommandHandler("addcoin", addcoin))
    application.run_polling()

if __name__ == "__main__":
    main()
