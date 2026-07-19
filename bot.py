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
    daily_bonus_count INTEGER DEFAULT 0,
    referral_count INTEGER DEFAULT 0,
    referred_by INTEGER DEFAULT 0,
    has_bet INTEGER DEFAULT 0,
    consecutive_losses INTEGER DEFAULT 0,
    has_used_100 INTEGER DEFAULT 0
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
    cursor.execute('SELECT daily_bonus_date, daily_bonus_count FROM users WHERE telegram_id = ?', (telegram_id,))
    row = cursor.fetchone()
    if row:
        if row[1] >= 3:
            return False, 0, "max"
        if row[0]:
            last_date = datetime.fromisoformat(row[0])
            if datetime.now() - last_date < timedelta(hours=24):
                remaining = 24 - (datetime.now() - last_date).seconds // 3600
                return False, remaining, "wait"
    return True, 0, "ok"

def set_daily_date(telegram_id):
    cursor.execute('UPDATE users SET daily_bonus_date = ?, daily_bonus_count = daily_bonus_count + 1 WHERE telegram_id = ?',
                   (datetime.now().isoformat(), telegram_id))
    conn.commit()

def get_referral_link(telegram_id):
    return f"https://t.me/getfreeSkins_bot?start=ref_{telegram_id}"

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Games", callback_data="games_menu")],
        [InlineKeyboardButton("👛 Wallet", callback_data="wallet")],
        [InlineKeyboardButton("👥 Referral", callback_data="referral")],
        [InlineKeyboardButton("📊 Transactions", callback_data="transactions")],
        [InlineKeyboardButton("📖 Help", callback_data="help")]
    ])

def games_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 Heads or Tails", callback_data="coinflip")],
        [InlineKeyboardButton("🎡 Roulette", callback_data="roulette")],
        [InlineKeyboardButton("🎰 Slots", callback_data="slots")],
        [InlineKeyboardButton("🎲 Dice", callback_data="dice")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
    ])

def roulette_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 Red", callback_data="roulette_red")],
        [InlineKeyboardButton("⚫ Black", callback_data="roulette_black")],
        [InlineKeyboardButton("🟢 Green", callback_data="roulette_green")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        user = create_user(update.effective_user.id, update.effective_user.username or "user")
        args = context.args
        if args and args[0].startswith('ref_'):
            referrer_id = int(args[0].split('_')[1])
            referrer = get_user(referrer_id)
            if referrer and referrer[5] < 3:
                cursor.execute('UPDATE users SET referral_count = referral_count + 1 WHERE telegram_id = ?', (referrer_id,))
                conn.commit()
    await update.message.reply_text(
        f"💰 Welcome to money poney, {update.effective_user.first_name}!\n\n🎮 Use the menu below to play:",
        reply_markup=main_menu()
    )

async def main_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "💰 Welcome to money poney!\n\n🎮 Use the menu below to play:",
        reply_markup=main_menu()
    )

async def games_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "🎮 Choose a game:",
        reply_markup=games_menu()
    )

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_user(query.from_user.id)
    await query.message.edit_text(
        f"👛 Your Wallet\n\n💰 Balance: {user[3]} coins\n👥 Referrals: {user[5]}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Deposit", callback_data="deposit")],
            [InlineKeyboardButton("🏦 Withdraw", callback_data="withdraw")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
        ])
    )

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "💳 Deposit is currently only available through admin.\nContact admin for assistance.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_back")]])
    )

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "🏦 Withdrawal is currently only available through admin.\nContact admin for assistance.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_back")]])
    )

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_user(query.from_user.id)
    link = get_referral_link(query.from_user.id)
    await query.message.edit_text(
        f"👥 Your referral link:\n{link}\n\nYou can only refer up to 3 people.\nYou get 20 coins after they make their first bet.\n\nTotal referrals: {user[5]}/3",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_back")]])
    )

async def transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_user(query.from_user.id)
    cursor.execute('SELECT type, amount, date FROM transactions WHERE user_id = ? ORDER BY date DESC LIMIT 10', (user[0],))
    rows = cursor.fetchall()
    if not rows:
        text = "📊 No transactions found."
    else:
        text = "📊 Last 10 transactions:\n\n"
        for row in rows:
            text += f"• {row[0]}: {row[1]} coins ({row[2][:10]})\n"
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_back")]])
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "📖 Help\n\nComing soon.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_back")]])
    )

async def addcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 5213245493:
        await update.message.reply_text("⛔ Access denied!")
        return
    update_balance(5213245493, 999999)
    await update.message.reply_text("✅ 999,999 coins added to your account!")

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = get_user(query.from_user.id)
    allowed, remaining, status = can_get_daily(query.from_user.id)
    if not allowed:
        if status == "max":
            await query.answer("❌ You've already claimed your 3-day bonus!", show_alert=True)
        else:
            await query.answer(f"⏳ {remaining} hours remaining!", show_alert=True)
        return
    update_balance(query.from_user.id, 7)
    set_daily_date(query.from_user.id)
    add_transaction(user[0], 'daily_bonus', 7)
    await query.message.edit_text(
        f"🎁 Daily bonus claimed! +7 coins\n💰 New balance: {user[3] + 7} coins",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_back")]])
    )

async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "🎡 Choose your bet:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("10", callback_data="bet_10")],
            [InlineKeyboardButton("20", callback_data="bet_20")],
            [InlineKeyboardButton("100", callback_data="bet_100")],
            [InlineKeyboardButton("500", callback_data="bet_500")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
        ])
    )

async def roulette_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    amount = int(query.data.split('_')[1])
    user = get_user(query.from_user.id)
    if user[3] < amount:
        await query.answer("Insufficient balance!", show_alert=True)
        return
    context.user_data['bet'] = amount
    await query.message.edit_text(
        f"🎡 Bet: {amount} coins\nChoose a color:",
        reply_markup=roulette_keyboard()
    )

async def roulette_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    choice = query.data.split('_')[1]
    user = get_user(query.from_user.id)
    bet = context.user_data.get('bet', 10)
    if user[3] < bet:
        await query.answer("Insufficient balance!", show_alert=True)
        return
    
    if bet in [100, 500]:
        win = bet * 2
        update_balance(query.from_user.id, win)
        add_transaction(user[0], 'win', win)
        text = f"🎉 You won! (Guaranteed win for {bet} bet)\n💰 Win: {win} coins"
    else:
        result = random.choices(['red', 'black', 'green'], weights=[50, 50, 0])[0]
        emoji = {'red': '🔴', 'black': '⚫', 'green': '🟢'}
        color_name = {'red': 'Red', 'black': 'Black', 'green': 'Green'}
        if choice == result:
            if result == 'green':
                win = bet * 14
            else:
                win = bet * 2
            update_balance(query.from_user.id, win)
            add_transaction(user[0], 'win', win)
            text = f"🎉 You won! Result: {emoji[result]} {color_name[result]}\n💰 Win: {win} coins"
        else:
            update_balance(query.from_user.id, -bet)
            add_transaction(user[0], 'loss', -bet)
            text = f"💔 You lost! Result: {emoji[result]} {color_name[result]}\n💰 Loss: {bet} coins"
    
    user = get_user(query.from_user.id)
    text += f"\n\n💳 New balance: {user[3]} coins"
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎡 Play Again", callback_data="roulette")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
        ])
    )

async def slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "🎰 Choose your bet:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("10", callback_data="slot_bet_10")],
            [InlineKeyboardButton("20", callback_data="slot_bet_20")],
            [InlineKeyboardButton("100", callback_data="slot_bet_100")],
            [InlineKeyboardButton("500", callback_data="slot_bet_500")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
        ])
    )

async def coinflip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "🪙 Choose your bet:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("10", callback_data="coin_bet_10")],
            [InlineKeyboardButton("20", callback_data="coin_bet_20")],
            [InlineKeyboardButton("100", callback_data="coin_bet_100")],
            [InlineKeyboardButton("500", callback_data="coin_bet_500")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
        ])
    )

async def coin_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    amount = int(query.data.split('_')[2])
    user = get_user(query.from_user.id)
    if user[3] < amount:
        await query.answer("Insufficient balance!", show_alert=True)
        return
    context.user_data['bet'] = amount
    await query.message.edit_text(
        f"🪙 Bet: {amount} coins\nChoose Heads or Tails:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Heads", callback_data="coinflip_heads")],
            [InlineKeyboardButton("Tails", callback_data="coinflip_tails")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
        ])
    )

async def coinflip_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    choice = query.data.split('_')[1]
    user = get_user(query.from_user.id)
    bet = context.user_data.get('bet', 10)
    
    if user[3] < bet:
        await query.answer("Insufficient balance!", show_alert=True)
        return
    
    # شرط ۵۰۰: همیشه باخت (برعکس انتخاب کاربر)
    if bet == 500:
        result = 'tails' if choice == 'heads' else 'heads'
        update_balance(query.from_user.id, -bet)
        add_transaction(user[0], 'loss', -bet)
        text = f"💔 You lost! Result: {result}\n💰 Loss: {bet} coins"
    
    # شرط ۱۰۰
    elif bet == 100:
        has_used_100 = user[10] if len(user) > 10 else 0
        losses = user[9] if len(user) > 9 else 0
        
        # اولین بار ۱۰۰: همیشه باخت
        if has_used_100 == 0:
            result = 'tails' if choice == 'heads' else 'heads'
            update_balance(query.from_user.id, -bet)
            add_transaction(user[0], 'loss', -bet)
            cursor.execute('UPDATE users SET has_used_100 = 1, consecutive_losses = 1 WHERE telegram_id = ?', (query.from_user.id,))
            conn.commit()
            text = f"💔 You lost! (First 100 bet)\n💰 Loss: {bet} coins"
        else:
            # بعد از اولین بار: یک برد، سه باخت
            if losses >= 3:
                win = bet * 2
                update_balance(query.from_user.id, win)
                add_transaction(user[0], 'win', win)
                cursor.execute('UPDATE users SET consecutive_losses = 0 WHERE telegram_id = ?', (query.from_user.id,))
                conn.commit()
                result = choice
                text = f"🎉 You won! Result: {result}\n💰 Win: {win} coins"
            else:
                result = 'tails' if choice == 'heads' else 'heads'
                update_balance(query.from_user.id, -bet)
                add_transaction(user[0], 'loss', -bet)
                cursor.execute('UPDATE users SET consecutive_losses = consecutive_losses + 1 WHERE telegram_id = ?', (query.from_user.id,))
                conn.commit()
                text = f"💔 You lost! Result: {result}\n💰 Loss: {bet} coins"
    
    # شرط‌های ۱۰ و ۲۰: شانس ۵۰/۵۰
    else:
        result = random.choice(['heads', 'tails'])
        if choice == result:
            win = bet * 2
            update_balance(query.from_user.id, win)
            add_transaction(user[0], 'win', win)
            text = f"🎉 You won! Result: {result}\n💰 Win: {win} coins"
        else:
            update_balance(query.from_user.id, -bet)
            add_transaction(user[0], 'loss', -bet)
            text = f"💔 You lost! Result: {result}\n💰 Loss: {bet} coins"
    
    # بررسی رفرال برای اولین شرط
    if user[7] == 0:
        cursor.execute('UPDATE users SET has_bet = 1 WHERE telegram_id = ?', (query.from_user.id,))
        conn.commit()
        ref_by = cursor.execute('SELECT referred_by FROM users WHERE telegram_id = ?', (query.from_user.id,)).fetchone()
        if ref_by and ref_by[0] > 0:
            referrer = get_user(ref_by[0])
            if referrer and referrer[5] < 3:
                update_balance(ref_by[0], 20)
                add_transaction(referrer[0], 'referral', 20)
                await context.bot.send_message(ref_by[0], f"🎉 Your referral made their first bet! +20 coins!")
    
    user = get_user(query.from_user.id)
    text += f"\n\n💳 New balance: {user[3]} coins"
    
    # ارسال گیف
    try:
        if result == 'heads':
            gif_id = "AAMCBAADGQEAAQMKpmpcM7rchYwAAcg-7LL00gIt-seV2AACxiEAAvxc4VK6xbM_Aihe5AEAB20AAz0E"
        else:
            gif_id = "CgACAgQAAxkBAAEDCqZqXDO63IWMAAHIPuyy9NICLfrHldgAAsYhAAL8XOFSusWzPwIoXuQ9BA"
        await query.message.reply_animation(gif_id)
    except Exception as e:
        logging.error(f"GIF send error: {e}")
    
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🪙 Play Again", callback_data="coinflip")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
        ])
    )

async def slot_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    amount = int(query.data.split('_')[2])
    user = get_user(query.from_user.id)
    if user[3] < amount:
        await query.answer("Insufficient balance!", show_alert=True)
        return
    emojis = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣']
    
    if amount == 500:
        result = random.sample(emojis, 3)
        update_balance(query.from_user.id, -amount)
        add_transaction(user[0], 'loss', -amount)
        text = f"💔 No match! {result[0]} {result[1]} {result[2]}\n💰 Loss: {amount} coins"
    else:
        result = [random.choice(emojis) for _ in range(3)]
        if result[0] == result[1] == result[2]:
            win = amount * 3
            update_balance(query.from_user.id, win)
            add_transaction(user[0], 'win', win)
            text = f"🎉 Jackpot! {result[0]} {result[1]} {result[2]}\n💰 Win: {win} coins (x3)"
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            win = int(amount * 1.2)
            update_balance(query.from_user.id, win)
            add_transaction(user[0], 'win', win)
            text = f"🎉 Two match! {result[0]} {result[1]} {result[2]}\n💰 Win: {win} coins (x1.2)"
        else:
            update_balance(query.from_user.id, -amount)
            add_transaction(user[0], 'loss', -amount)
            text = f"💔 No match! {result[0]} {result[1]} {result[2]}\n💰 Loss: {amount} coins"
    
    user = get_user(query.from_user.id)
    text += f"\n\n💳 New balance: {user[3]} coins"
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎰 Play Again", callback_data="slots")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
        ])
    )

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "🎲 Choose your bet:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("10", callback_data="dice_bet_10")],
            [InlineKeyboardButton("20", callback_data="dice_bet_20")],
            [InlineKeyboardButton("100", callback_data="dice_bet_100")],
            [InlineKeyboardButton("500", callback_data="dice_bet_500")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
        ])
    )

async def dice_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    amount = int(query.data.split('_')[2])
    user = get_user(query.from_user.id)
    if user[3] < amount:
        await query.answer("Insufficient balance!", show_alert=True)
        return
    context.user_data['bet'] = amount
    await query.message.edit_text(
        f"🎲 Bet: {amount} coins\n\nChoose a number (1-6):",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("1", callback_data="dice_1")],
            [InlineKeyboardButton("2", callback_data="dice_2")],
            [InlineKeyboardButton("3", callback_data="dice_3")],
            [InlineKeyboardButton("4", callback_data="dice_4")],
            [InlineKeyboardButton("5", callback_data="dice_5")],
            [InlineKeyboardButton("6", callback_data="dice_6")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
        ])
    )

async def dice_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_choice = int(query.data.split('_')[1])
    user = get_user(query.from_user.id)
    bet = context.user_data.get('bet', 10)
    
    if user[3] < bet:
        await query.answer("Insufficient balance!", show_alert=True)
        return
    
    if bet in [100, 500]:
        possible_numbers = [1, 2, 3, 4, 5, 6]
        possible_numbers.remove(user_choice)
        dice_number = random.choice(possible_numbers)
    else:
        dice_number = random.randint(1, 6)
    
    dice_emojis = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅']
    dice_emoji = dice_emojis[dice_number - 1]
    
    if user_choice == dice_number:
        win = bet * 2
        update_balance(query.from_user.id, win)
        add_transaction(user[0], 'win', win)
        text = f"🎲 Dice: {dice_emoji} {dice_number}\n\n🎉 You won!\n💰 Win: {win} coins"
    else:
        update_balance(query.from_user.id, -bet)
        add_transaction(user[0], 'loss', -bet)
        text = f"🎲 Dice: {dice_emoji} {dice_number}\n\n😔 You lost!\nYour choice didn't match the result.\n\n💸 Loss: {bet} coins\n\n💪 Don't give up! Try again."
    
    user = get_user(query.from_user.id)
    text += f"\n\n💳 New balance: {user[3]} coins"
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 Play Again", callback_data="dice")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
        ])
    )

async def test_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        test_gif_id = "CgACAgQAAxkBAAEDCqZqXDO63IWMAAHIPuyy9NICLfrHldgAAsYhAAL8XOFSusWzPwIoXuQ9BA"
        await update.message.reply_animation(test_gif_id)
        await update.message.reply_text("✅ GIF sent successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        
def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addcoin", addcoin))
    application.add_handler(CommandHandler("testgif", test_gif))
    
    application.add_handler(CallbackQueryHandler(main_back, pattern="main_back"))
    application.add_handler(CallbackQueryHandler(games_menu_handler, pattern="games_menu"))
    application.add_handler(CallbackQueryHandler(wallet, pattern="wallet"))
    application.add_handler(CallbackQueryHandler(deposit, pattern="deposit"))
    application.add_handler(CallbackQueryHandler(withdraw, pattern="withdraw"))
    application.add_handler(CallbackQueryHandler(referral, pattern="referral"))
    application.add_handler(CallbackQueryHandler(transactions, pattern="transactions"))
    application.add_handler(CallbackQueryHandler(help, pattern="help"))
    application.add_handler(CallbackQueryHandler(daily_bonus, pattern="daily_bonus"))
    
    application.add_handler(CallbackQueryHandler(roulette, pattern="roulette"))
    application.add_handler(CallbackQueryHandler(roulette_bet, pattern="^bet_"))
    application.add_handler(CallbackQueryHandler(roulette_play, pattern="^roulette_"))
    
    application.add_handler(CallbackQueryHandler(coinflip, pattern="coinflip"))
    application.add_handler(CallbackQueryHandler(coin_bet, pattern="^coin_bet_"))
    application.add_handler(CallbackQueryHandler(coinflip_play, pattern="^coinflip_"))
    
    application.add_handler(CallbackQueryHandler(slots, pattern="slots"))
    application.add_handler(CallbackQueryHandler(slot_bet, pattern="^slot_bet_"))
    
    application.add_handler(CallbackQueryHandler(dice, pattern="dice"))
    application.add_handler(CallbackQueryHandler(dice_bet, pattern="^dice_bet_"))
    application.add_handler(CallbackQueryHandler(dice_play, pattern="^dice_"))
    
    application.run_polling()

if __name__ == "__main__":
    main()
