"""
bot.py — Trend Pilot BTC Prediction Bot
AI auto-trading on Myriad Markets via Telegram
"""

import os
import asyncio
import logging
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters, CallbackQueryHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
import signal_engine as se
import wallet_manager as wm
import trader
import myriad_client as mc

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
TG_TOKEN       = os.getenv("TG_TOKEN")
OWNER_EVM      = os.getenv("OWNER_EVM", "0x95FB94763D57f8416A524091E641a9D26741cB31")
BYPASS_CODE    = os.getenv("BYPASS_CODE", "SYKE0X")
BYPASS_MAX     = int(os.getenv("BYPASS_MAX", "5"))
MIN_DEPOSIT    = float(os.getenv("MIN_DEPOSIT", "5.0"))
SIGNAL_THRESH  = float(os.getenv("SIGNAL_THRESH", "80.0"))
BET_AMOUNT     = float(os.getenv("BET_AMOUNT", "5.0"))
WINNING_FEE    = 0.025   # 2.5% of winnings to owner
REFERRAL_BONUS = 1.0     # $1 USD1 per referral

# Conversation states
ASK_EMAIL, ASK_REF, ASK_FEE, ASK_TX, ASK_BYPASS = range(5)


# ── Helpers ───────────────────────────────────────────────────────────────────
def is_owner(telegram_id: str) -> bool:
    user = db.get_user(telegram_id)
    return bool(user and user["is_owner"] == 1)


def is_active(telegram_id: str) -> bool:
    user = db.get_user(telegram_id)
    return bool(user and user["is_active"] == 1)


# ── Keyboards ─────────────────────────────────────────────────────────────────
def welcome_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Register Now", callback_data="register")],
        [InlineKeyboardButton("ℹ️ How It Works", callback_data="howto"),
         InlineKeyboardButton("🔑 Bypass Code", callback_data="do_bypass")],
    ])


def main_menu_keyboard(owner=False):
    buttons = [
        [InlineKeyboardButton("📊 Signal", callback_data="signal"),
         InlineKeyboardButton("💰 Balance", callback_data="balance")],
        [InlineKeyboardButton("📥 Deposit", callback_data="deposit"),
         InlineKeyboardButton("📂 Stats", callback_data="stats")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
         InlineKeyboardButton("👥 Referral", callback_data="referral")],
        [InlineKeyboardButton("🔑 My Key", callback_data="mykey"),
         InlineKeyboardButton("💳 Address", callback_data="myaddress")],
        [InlineKeyboardButton("📤 Withdraw", callback_data="withdraw"),
         InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    if owner:
        buttons.append([InlineKeyboardButton("🛠 Admin Dashboard", callback_data="admin")])
    return InlineKeyboardMarkup(buttons)


# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    name = update.effective_user.first_name or "Trader"

    db.create_user(uid, name)
    user = db.get_user(uid)

    # Auto-detect referral code from link e.g. t.me/pilotrend_bot?start=REF123
    if ctx.args and not user["referred_by"]:
        ref_code = ctx.args[0].upper()
        referrer = db.get_user_by_referral_code(ref_code)
        if referrer and str(referrer["telegram_id"]) != uid:
            db.update_user(uid, referred_by=ref_code)
            ctx.user_data["referral_code"] = ref_code

    if user["is_active"]:
        await update.message.reply_text(
            f"👋 Welcome back *{name}*!\n\n"
            f"Your bot is active and trading automatically.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(user["is_owner"] == 1)
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"👋 Welcome *{name}*!\n\n"
        f"🤖 *AI-Powered BTC Trading Bot*\n\n"
        f"Automatically trades BTC UP/DOWN on Myriad Markets when AI confidence exceeds 80%.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ AI trades 24/7 automatically\n"
        f"✅ Auto-claims winnings to your wallet\n"
        f"✅ Daily P&L reports\n"
        f"✅ 2.5% platform fee on winnings only\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*What you need to start:*\n"
        f"1️⃣ $5 USD1 — one-time access fee\n"
        f"2️⃣ $5+ USD1 — trading capital\n"
        f"3️⃣ ~0.002 BNB — gas fee\n\n"
        f"All on *Binance Smart Chain (BSC)*",
        parse_mode="Markdown",
        reply_markup=welcome_keyboard()
    )
    return ConversationHandler.END


# ── Button: Register ──────────────────────────────────────────────────────────
async def start_register(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📧 Enter your *Myriad email* to begin registration:",
        parse_mode="Markdown"
    )
    return ASK_EMAIL


# ── Button: How It Works ──────────────────────────────────────────────────────
async def how_it_works(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🤖 *How Trend Pilot Works*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*AI Signal Engine*\n"
        "Every hour the bot analyzes BTC using:\n"
        "  • RSI — momentum indicator\n"
        "  • MACD — trend direction\n"
        "  • MA20 — moving average\n"
        "  • Bollinger Bands — volatility\n\n"
        "*Auto-Trading*\n"
        "When confidence exceeds 80%, the bot automatically places a BTC UP or DOWN bet on Myriad Markets.\n\n"
        "*Winnings*\n"
        "Winnings are auto-claimed to your wallet every 10 minutes. 2.5% platform fee on profits only.\n\n"
        "*Your wallet*\n"
        "A unique BSC wallet is generated for you. You hold the private key — full custody.\n"
        "━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=welcome_keyboard()
    )


# ── Registration flow ─────────────────────────────────────────────────────────
async def ask_email(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = str(update.effective_user.id)
    email = update.message.text.strip().lower()

    if "@" not in email or "." not in email:
        await update.message.reply_text("❌ Invalid email. Please enter a valid email address:")
        return ASK_EMAIL

    conn = db.get_conn()
    existing = conn.execute(
        "SELECT telegram_id FROM users WHERE email = ? AND telegram_id != ?",
        (email, uid)
    ).fetchone()
    conn.close()

    if existing:
        await update.message.reply_text("❌ That email is already registered. Use a different one:")
        return ASK_EMAIL

    wallet = wm.generate_wallet()
    db.update_user(uid,
        email          = email,
        wallet_address = wallet["address"],
        wallet_key     = wallet["encrypted_key"]
    )

    await update.message.reply_text(
        f"✅ *Email saved!*\n\n"
        f"🔐 *Your Trading Wallet*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Address : `{wallet['address']}`\n"
        f"Network : Binance Smart Chain (BSC)\n\n"
        f"⚠️ *SAVE YOUR PRIVATE KEY NOW:*\n"
        f"`{wallet['private_key']}`\n\n"
        f"• Import to MetaMask to access funds\n"
        f"• Never share with anyone\n"
        f"• Use /mykey anytime to retrieve it\n"
        f"If you joined via a referral link, the bonus is applied automatically.\n\n"
        f"*Step 1 of 2 — Access Fee*\n\n"
        f"Send *$5.00 USD1* to the owner wallet on BSC:\n\n"
        f"`{OWNER_EVM}`\n\n"
        f"Once sent, paste the *transaction hash* here.",
        parse_mode="Markdown"
    )
    return ASK_FEE


async def ask_ref(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    text = update.message.text.strip().upper()
    user = db.get_user(uid)

    # Skip if referral already auto-detected from link
    if user["referred_by"]:
        await update.message.reply_text(
            f"✅ Referral code *{user['referred_by']}* already applied!",
            parse_mode="Markdown"
        )
    elif text != "SKIP":
        referrer = db.get_user_by_referral_code(text)
        if referrer and str(referrer["telegram_id"]) != uid:
            db.update_user(uid, referred_by=text)
            ctx.user_data["referral_code"] = text
            await update.message.reply_text(f"✅ Referral code *{text}* applied!", parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Invalid referral code — continuing without one.")

    user = db.get_user(uid)
    await update.message.reply_text(
        f"*Step 1 of 2 — Access Fee*\n\n"
        f"Send *$5.00 USD1* to the owner wallet on BSC:\n\n"
        f"`{OWNER_EVM}`\n\n"
        f"This is a one-time access fee.\n"
        f"Once sent, paste the *transaction hash* here.",
        parse_mode="Markdown"
    )
    return ASK_FEE


async def ask_fee(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    tx_hash = update.message.text.strip()
    user    = db.get_user(uid)

    if not tx_hash.startswith("0x") or len(tx_hash) < 60:
        await update.message.reply_text(
            "❌ Invalid tx hash. Must start with `0x` and be 66 characters.\n\nPlease paste the correct transaction hash:",
            parse_mode="Markdown"
        )
        return ASK_FEE

    if db.tx_already_used(tx_hash):
        await update.message.reply_text("❌ This transaction has already been used.")
        return ASK_FEE

    await update.message.reply_text("⏳ Verifying access fee payment...")
    result = wm.verify_tx_payment(tx_hash, OWNER_EVM, 5.0)

    if not result["valid"]:
        await update.message.reply_text(
            f"❌ *Verification failed*\n{result['error']}\n\nPlease check and try again:",
            parse_mode="Markdown"
        )
        return ASK_FEE

    db.log_deposit(user["id"], tx_hash, result["amount"], "access_fee")
    db.update_user(uid, fee_paid=1)

    # Pay referral bonus if applicable
    if user["referred_by"]:
        referrer = db.get_user_by_referral_code(user["referred_by"])
        if referrer:
            db.add_balance(str(referrer["telegram_id"]), REFERRAL_BONUS)
            db.log_referral(referrer["id"], user["id"])

    await update.message.reply_text(
        f"✅ *Access fee confirmed!* ${result['amount']:.2f} USD1\n\n"
        f"*Step 2 of 2 — Fund Your Trading Wallet*\n\n"
        f"Send trading capital to YOUR bot wallet:\n\n"
        f"`{user['wallet_address']}`\n\n"
        f"• Minimum: *$5 USD1* (trading capital)\n"
        f"• Plus: *~0.002 BNB* (gas fee)\n\n"
        f"Both on Binance Smart Chain (BSC).\n"
        f"Once USD1 is sent, paste the *transaction hash* here.",
        parse_mode="Markdown"
    )
    return ASK_TX


async def ask_tx(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    tx_hash = update.message.text.strip()
    user    = db.get_user(uid)

    if not user["fee_paid"]:
        await update.message.reply_text(
            "⚠️ Please complete Step 1 first — pay the $5 access fee to the owner wallet."
        )
        return ASK_FEE

    if not tx_hash.startswith("0x") or len(tx_hash) < 60:
        await update.message.reply_text(
            "❌ Invalid tx hash. Must start with `0x`.\n\nPlease paste the correct transaction hash:",
            parse_mode="Markdown"
        )
        return ASK_TX

    if db.tx_already_used(tx_hash):
        await update.message.reply_text("❌ This transaction has already been used.")
        return ASK_TX

    await update.message.reply_text("⏳ Verifying trading deposit...")
    result = wm.verify_tx_payment(tx_hash, user["wallet_address"], MIN_DEPOSIT)

    if not result["valid"]:
        await update.message.reply_text(
            f"❌ *Verification failed*\n{result['error']}\n\nPlease check and try again:",
            parse_mode="Markdown"
        )
        return ASK_TX

    db.log_deposit(user["id"], tx_hash, result["amount"], "trading")
    db.update_user(uid, is_active=1, balance=result["amount"])

    await update.message.reply_text(
        f"🎉 *Account Activated!*\n\n"
        f"💰 Trading Balance: *${result['amount']:.2f} USD1*\n\n"
        f"Your bot is now live. It will automatically trade BTC UP/DOWN when AI confidence exceeds 80%.\n\n"
        f"Your referral code: *{user['referral_code']}*\n"
        f"Share it to earn $1 USD1 per referral!",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(False)
    )
    return ConversationHandler.END


# ── /bypass ───────────────────────────────────────────────────────────────────
async def bypass_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if is_active(uid):
        await update.message.reply_text("✅ Your account is already active.")
        return ConversationHandler.END
    uses = db.count_bypass_uses()
    if uses >= BYPASS_MAX:
        await update.message.reply_text("❌ Bypass code limit reached.")
        return ConversationHandler.END
    await update.message.reply_text("🔑 Enter your bypass code:")
    return ASK_BYPASS


async def check_bypass(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    code = update.message.text.strip()
    uses = db.count_bypass_uses()

    if uses >= BYPASS_MAX:
        await update.message.reply_text("❌ Bypass code limit reached.")
        return ConversationHandler.END

    if code != BYPASS_CODE:
        await update.message.reply_text("❌ Wrong code.")
        return ConversationHandler.END

    conn = db.get_conn()
    already = conn.execute("SELECT id FROM bypass_uses WHERE telegram_id = ?", (uid,)).fetchone()
    conn.close()

    if already:
        await update.message.reply_text("❌ You've already used a bypass code.")
        return ConversationHandler.END

    db.log_bypass_use(uid)
    db.update_user(uid, is_active=1, is_owner=1, fee_paid=1, balance=999999)

    remaining = BYPASS_MAX - db.count_bypass_uses()
    await update.message.reply_text(
        f"✅ *Owner bypass activated!*\nRemaining uses: {remaining}/{BYPASS_MAX}",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(True)
    )
    return ConversationHandler.END


# ── /menu ─────────────────────────────────────────────────────────────────────
async def menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user or not is_active(uid):
        await update.message.reply_text("❌ Account not active. Use /start to register.")
        return
    await update.message.reply_text(
        "🤖 *Trend Pilot*\nChoose an option:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(user["is_owner"] == 1)
    )


# ── /verify ───────────────────────────────────────────────────────────────────
async def verify_deposit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)

    if not user or not is_active(uid):
        await update.message.reply_text("❌ Use /start first.")
        return

    if not ctx.args:
        await update.message.reply_text("Usage: /verify <transaction_hash>")
        return

    tx_hash = ctx.args[0].strip()
    if db.tx_already_used(tx_hash):
        await update.message.reply_text("❌ Transaction already used.")
        return

    await update.message.reply_text("⏳ Verifying...")
    result = wm.verify_tx_payment(tx_hash, user["wallet_address"], 1.0)

    if not result["valid"]:
        await update.message.reply_text(f"❌ {result['error']}")
        return

    db.log_deposit(user["id"], tx_hash, result["amount"], "trading")
    db.add_balance(uid, result["amount"])

    await update.message.reply_text(
        f"✅ *${result['amount']:.2f} USD1 credited!*\n"
        f"New balance: *${db.get_user(uid)['balance']:.2f} USD1*",
        parse_mode="Markdown"
    )


# ── /withdraw ─────────────────────────────────────────────────────────────────
async def withdraw(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💸 *Withdrawals*\n\n"
        "Visit myriad.markets and connect your bot wallet to withdraw directly.",
        parse_mode="Markdown"
    )


# ── /mykey ────────────────────────────────────────────────────────────────────
async def mykey(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user or not user["wallet_key"]:
        await update.message.reply_text("❌ No wallet found. Use /start to register.")
        return
    try:
        private_key = wm.decrypt_key(user["wallet_key"])
        await update.message.reply_text(
            f"🔐 *Your Private Key*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"`{private_key}`\n\n"
            f"⚠️ Never share this with anyone.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Could not retrieve key: {e}")


# ── /myaddress ────────────────────────────────────────────────────────────────
async def myaddress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user or not user["wallet_address"]:
        await update.message.reply_text("❌ No wallet found.")
        return
    await update.message.reply_text(
        f"💳 *Your Wallet Address*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"`{user['wallet_address']}`\n\n"
        f"Network: Binance Smart Chain (BSC)",
        parse_mode="Markdown"
    )


# ── /help ─────────────────────────────────────────────────────────────────────
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 *Trend Pilot — BTC Trading Bot*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Account*\n"
        f"  /start — register / onboard\n"
        f"  /bypass — owner bypass code\n"
        f"  /menu — show main menu\n"
        f"  /verify <tx> — credit a deposit\n"
        f"  /withdraw — withdrawal info\n\n"
        f"*Trading*\n"
        f"  /signal — run AI analysis now\n"
        f"  /stats — your P&L and trade history\n"
        f"  /leaderboard — top traders by volume\n"
        f"  /referral — your referral code\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Auto-trading fires when confidence > 80%_\n"
        f"_2.5% platform fee on winnings only_",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_owner(str(update.effective_user.id)))
    )


# ── /stats ────────────────────────────────────────────────────────────────────
async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user or not is_active(uid):
        await update.message.reply_text("❌ Account not active.")
        return
    s  = db.get_user_stats(user["id"])
    wr = round(s["wins"] / s["total_trades"] * 100, 1) if s["total_trades"] else 0
    await update.message.reply_text(
        f"📊 *Your Trading Stats*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Total Trades : {s['total_trades']}\n"
        f"Wins         : {s['wins']} ✅\n"
        f"Losses       : {s['losses']} ❌\n"
        f"Win Rate     : {wr}%\n"
        f"Total P&L    : ${s['total_pnl'] or 0:.2f}\n"
        f"Volume       : ${s['total_volume'] or 0:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Balance      : *${user['balance']:.2f} USD1*",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_owner(uid))
    )


# ── /signal ───────────────────────────────────────────────────────────────────
async def signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_active(uid):
        await update.message.reply_text("❌ Account not active.")
        return
    await update.message.reply_text("⏳ Analyzing BTC...")
    try:
        sig = se.generate_signal()
        await update.message.reply_text(
            se.format_signal(sig),
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Signal error: {e}")


# ── /leaderboard ──────────────────────────────────────────────────────────────
async def leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = db.get_leaderboard(10)
    if not rows:
        await update.message.reply_text("📭 No trading data yet.")
        return

    lines = ["🏆 *Top Traders by Volume*", "━━━━━━━━━━━━━━━━━━━━"]
    medals = ["🥇", "🥈", "🥉"]

    for i, row in enumerate(rows):
        addr    = row["wallet_address"] or "Unknown"
        short   = f"{addr[:6]}...{addr[-4:]}" if addr and len(addr) > 10 else addr
        medal   = medals[i] if i < 3 else f"{i+1}."
        volume  = row["total_volume"] or 0
        profit  = row["total_profit"] or 0
        trades  = row["total_trades"] or 0
        pnl_sym = "+" if profit >= 0 else ""
        lines.append(
            f"{medal} `{short}`\n"
            f"   Vol: ${volume:.2f} | P&L: {pnl_sym}${profit:.2f} | Trades: {trades}"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_owner(str(update.effective_user.id)))
    )


# ── /referral ─────────────────────────────────────────────────────────────────
async def referral(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user or not is_active(uid):
        await update.message.reply_text("❌ Account not active.")
        return
    count = db.get_referral_count(user["id"])
    earned = count * REFERRAL_BONUS
    await update.message.reply_text(
        f"👥 *Your Referral*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Your code  : *{user['referral_code']}*\n"
        f"Referrals  : {count}\n"
        f"Earned     : ${earned:.2f} USD1\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Share your code with friends:\n"
        f"Share your link: 👉 t.me/pilotrend_bot?start={user['referral_code']}\n\n"
        f"You earn *$1 USD1* for every person who joins using your code!",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_owner(uid))
    )


# ── /admin ────────────────────────────────────────────────────────────────────
async def admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_owner(uid):
        await update.message.reply_text("❌ Admin only.")
        return
    s = db.get_admin_stats()
    await update.message.reply_text(
        f"🛠 *Admin Dashboard*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users    : {s['total_users']}\n"
        f"✅ Active Users   : {s['active_users']}\n"
        f"👥 Total Referrals: {s['total_referrals']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 Total Trades   : {s['total_trades']}\n"
        f"📊 Total Volume   : ${s['total_volume']:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Today Trades   : {s['today_trades']}\n"
        f"💵 Today Volume   : ${s['today_volume']:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Total Fees     : ${s['total_fees']:.4f}\n"
        f"🏦 Owner Wallet   : `{OWNER_EVM[:16]}...`\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(True)
    )


# ── Button Handler ────────────────────────────────────────────────────────────
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = str(query.from_user.id)
    data = query.data

    if data == "register":
        await query.message.reply_text(
            "📧 Enter your *Myriad email* to begin registration:",
            parse_mode="Markdown"
        )
        ctx.user_data["registering"] = True
        return

    if data == "howto":
        await how_it_works(update, ctx)
        return

    if data == "do_bypass":
        uses = db.count_bypass_uses()
        if uses >= BYPASS_MAX:
            await query.message.reply_text("❌ Bypass code limit reached.")
            return
        await query.message.reply_text("🔑 Enter your bypass code:")
        ctx.user_data["awaiting_bypass"] = True
        return

    if not is_active(uid):
        await query.message.reply_text("❌ Account not active. Use /start to register.")
        return

    user = db.get_user(uid)

    if data == "signal":
        await query.message.reply_text("⏳ Analyzing BTC...")
        try:
            sig = se.generate_signal()
            await query.message.reply_text(
                se.format_signal(sig),
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(is_owner(uid))
            )
        except Exception as e:
            await query.message.reply_text(f"⚠️ Signal error: {e}")

    elif data == "balance":
        onchain   = wm.get_usd1_balance(user["wallet_address"])
        positions = trader.get_claimable_positions(user["wallet_address"])
        port_val  = sum(p.get("value", 0) for p in positions) if positions else 0
        open_pos  = len(positions) if positions else 0
        await query.message.reply_text(
            f"💰 *Your Wallet*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Address    : `{user['wallet_address']}`\n"
            f"Bot Balance: *${user['balance']:.2f} USD1*\n"
            f"On-chain   : *${onchain:.2f} USD1*\n"
            f"In Myriad  : *${port_val:.2f} USD1* ({open_pos} positions)\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "deposit":
        await query.message.reply_text(
            f"📥 *Top Up Your Balance*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Send *USD1* on *BSC* to:\n\n"
            f"`{user['wallet_address']}`\n\n"
            f"Also send *~0.002 BNB* for gas.\n"
            f"After sending use /verify <tx\\_hash>",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "stats":
        s  = db.get_user_stats(user["id"])
        wr = round(s["wins"] / s["total_trades"] * 100, 1) if s["total_trades"] else 0
        await query.message.reply_text(
            f"📊 *Your Trading Stats*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Trades : {s['total_trades']}\n"
            f"Wins         : {s['wins']} ✅\n"
            f"Losses       : {s['losses']} ❌\n"
            f"Win Rate     : {wr}%\n"
            f"Total P&L    : ${s['total_pnl'] or 0:.2f}\n"
            f"Volume       : ${s['total_volume'] or 0:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Balance      : *${user['balance']:.2f} USD1*",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "leaderboard":
        rows = db.get_leaderboard(10)
        if not rows:
            await query.message.reply_text("📭 No trading data yet.")
            return
        lines = ["🏆 *Top Traders by Volume*", "━━━━━━━━━━━━━━━━━━━━"]
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(rows):
            addr   = row["wallet_address"] or "Unknown"
            short  = f"{addr[:6]}...{addr[-4:]}" if len(addr) > 10 else addr
            medal  = medals[i] if i < 3 else f"{i+1}."
            vol    = row["total_volume"] or 0
            profit = row["total_profit"] or 0
            trades = row["total_trades"] or 0
            sym    = "+" if profit >= 0 else ""
            lines.append(f"{medal} `{short}`\n   Vol: ${vol:.2f} | P&L: {sym}${profit:.2f} | Trades: {trades}")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        await query.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "referral":
        count  = db.get_referral_count(user["id"])
        earned = count * REFERRAL_BONUS
        await query.message.reply_text(
            f"👥 *Your Referral*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Your code  : *{user['referral_code']}*\n"
            f"Referrals  : {count}\n"
            f"Earned     : ${earned:.2f} USD1\n\n"
            f"Share your link: 👉 t.me/pilotrend_bot?start={user['referral_code']}\n\n"
            f"Earn *$1 USD1* per referral!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "mykey":
        try:
            pk = wm.decrypt_key(user["wallet_key"])
            await query.message.reply_text(
                f"🔐 *Your Private Key*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"`{pk}`\n\n"
                f"⚠️ Never share this with anyone.",
                parse_mode="Markdown"
            )
        except Exception as e:
            await query.message.reply_text(f"❌ Could not retrieve key: {e}")

    elif data == "myaddress":
        await query.message.reply_text(
            f"💳 *Your Wallet Address*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"`{user['wallet_address']}`\n\n"
            f"Network: Binance Smart Chain (BSC)",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "withdraw":
        await query.message.reply_text(
            "💸 *Withdrawals*\n\n"
            "Visit myriad.markets and connect your bot wallet to withdraw directly.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "admin":
        if not is_owner(uid):
            await query.message.reply_text("❌ Admin only.")
            return
        s = db.get_admin_stats()
        await query.message.reply_text(
            f"🛠 *Admin Dashboard*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Total Users    : {s['total_users']}\n"
            f"✅ Active Users   : {s['active_users']}\n"
            f"👥 Referrals      : {s['total_referrals']}\n"
            f"📈 Total Trades   : {s['total_trades']}\n"
            f"📊 Total Volume   : ${s['total_volume']:.2f}\n"
            f"💵 Today Volume   : ${s['today_volume']:.2f}\n"
            f"💰 Total Fees     : ${s['total_fees']:.4f}\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(True)
        )

    elif data == "help":
        await query.message.reply_text(
            f"🤖 *Trend Pilot — BTC Trading Bot*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  /start — register\n"
            f"  /menu — main menu\n"
            f"  /verify <tx> — credit deposit\n"
            f"  /signal — AI analysis\n"
            f"  /stats — P&L history\n"
            f"  /leaderboard — top traders\n"
            f"  /referral — your referral code\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Auto-trades when confidence > 80%_\n"
            f"_2.5% fee on winnings only_",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )


# ── Auto-trader ───────────────────────────────────────────────────────────────
async def auto_trade(app: Application):
    logger.info("Running auto-trade scan...")
    try:
        sig = se.generate_signal()
    except Exception as e:
        logger.error(f"Signal error: {e}")
        return

    users = db.get_all_active_users()
    for user in users:
        try:
            await app.bot.send_message(
                chat_id=user["telegram_id"],
                text=se.format_signal(sig),
                parse_mode="Markdown"
            )
        except Exception:
            pass

    if not sig["tradeable"]:
        logger.info(f"Signal {sig['confidence']}% below threshold — skipping")
        return

    logger.info(f"Signal {sig['confidence']}% → trading {sig['direction'].upper()}")

    for user in users:
        uid = user["telegram_id"]
        if user["balance"] < BET_AMOUNT:
            try:
                await app.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"⚠️ *Insufficient balance*\n"
                        f"Need ${BET_AMOUNT:.2f} — have ${user['balance']:.2f}\n"
                        f"Use /deposit or tap Deposit to top up."
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            continue

        try:
            private_key = wm.decrypt_key(user["wallet_key"])
            result      = trader.place_trade(private_key, sig["direction"], BET_AMOUNT)
            tx_hash     = result.get("buy_tx", "pending")
            shares      = result.get("shares", 0)
            payout      = result.get("payout", 0)

            db.deduct_balance(uid, BET_AMOUNT)
            db.log_trade(
                user["id"], sig["direction"], BET_AMOUNT,
                sig["confidence"], result.get("market_id", 0), 0, tx_hash
            )

            await app.bot.send_message(
                chat_id=uid,
                text=(
                    f"✅ *Auto-trade Placed!*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Direction  : BTC {sig['direction'].upper()}\n"
                    f"Confidence : {sig['confidence']}%\n"
                    f"Stake      : ${BET_AMOUNT}\n"
                    f"Shares     : {shares}\n"
                    f"Potential  : ~${payout}\n"
                    f"Tx         : `{tx_hash[:20]}...`\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Balance    : ${db.get_user(uid)['balance']:.2f}"
                ),
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Trade failed for {uid}: {e}")
            try:
                await app.bot.send_message(chat_id=uid, text=f"⚠️ Auto-trade failed: {str(e)[:100]}")
            except Exception:
                pass


# ── Auto-claim ────────────────────────────────────────────────────────────────
async def auto_claim(app: Application):
    logger.info("Running auto-claim check...")
    users = db.get_all_active_users()

    for user in users:
        uid = user["telegram_id"]
        try:
            positions = trader.get_claimable_positions(user["wallet_address"])
            if not positions:
                continue

            private_key = wm.decrypt_key(user["wallet_key"])

            for pos in positions:
                try:
                    result  = trader.claim_winnings(
                        private_key, pos["marketId"],
                        pos["networkId"], pos["outcomeId"]
                    )
                    payout  = round(pos.get("value", 0), 2)
                    profit  = round(pos.get("profit", 0), 2)

                    # 2.5% platform fee on winnings
                    fee_amount = round(payout * WINNING_FEE, 4)
                    user_payout = round(payout - fee_amount, 4)

                    # Send fee on-chain to owner
                    try:
                        fee_data = trader.build_approve_data(OWNER_EVM, int(fee_amount * 10**18))
                        trader.sign_and_send(private_key, trader.USD1_ADDRESS,
                                           trader.build_transfer_data(OWNER_EVM, int(fee_amount * 10**18)))
                        db.log_fee(user["id"], fee_amount, 0)
                    except Exception as fe:
                        logger.error(f"Fee transfer error: {fe}")

                    db.add_balance(uid, user_payout)

                    conn = db.get_conn()
                    conn.execute(
                        "UPDATE trades SET result = 'win', pnl = ? WHERE user_id = ? AND market_id = ? AND status = 'pending'",
                        (profit, user["id"], pos["marketId"])
                    )
                    conn.commit()
                    conn.close()

                    await app.bot.send_message(
                        chat_id=uid,
                        text=(
                            f"🏆 *Winnings Claimed!*\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"Market  : {pos['marketTitle'][:40]}\n"
                            f"Outcome : {pos['outcomeTitle']} ✅\n"
                            f"Payout  : ${payout:.2f} USD1\n"
                            f"Fee     : ${fee_amount:.4f} (2.5%)\n"
                            f"You get : *${user_payout:.4f} USD1*\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"Balance : ${db.get_user(uid)['balance']:.2f} USD1"
                        ),
                        parse_mode="Markdown"
                    )

                except Exception as e:
                    logger.error(f"Claim error for {uid}: {e}")

        except Exception as e:
            logger.error(f"Auto-claim error for {uid}: {e}")


# ── Daily Report ──────────────────────────────────────────────────────────────
async def daily_report(app: Application):
    logger.info("Sending daily P&L reports...")
    users = db.get_all_active_users()

    for user in users:
        try:
            conn = db.get_conn()
            today = conn.execute("""
                SELECT COUNT(*) as trades, SUM(pnl) as pnl,
                       SUM(amount) as volume
                FROM trades
                WHERE user_id = ? AND DATE(placed_at) = DATE('now')
            """, (user["id"],)).fetchone()
            conn.close()

            if not today or today["trades"] == 0:
                continue

            pnl_emoji = "📈" if (today["pnl"] or 0) >= 0 else "📉"
            await app.bot.send_message(
                chat_id=user["telegram_id"],
                text=(
                    f"📋 *Daily Report*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Trades today : {today['trades']}\n"
                    f"Volume       : ${today['volume'] or 0:.2f}\n"
                    f"P&L          : {pnl_emoji} ${today['pnl'] or 0:.2f}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Balance      : *${user['balance']:.2f} USD1*"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Daily report error: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    db.init_db()
    app = Application.builder().token(TG_TOKEN).connect_timeout(60).read_timeout(60).write_timeout(60).pool_timeout(60).get_updates_read_timeout(60).build()

    # Registration conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
            ASK_REF:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_ref)],
            ASK_FEE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_fee)],
            ASK_TX:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_tx)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    bypass_conv = ConversationHandler(
        entry_points=[CommandHandler("bypass", bypass_start)],
        states={
            ASK_BYPASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_bypass)],
        },
        fallbacks=[CommandHandler("bypass", bypass_start)]
    )

    # Registration via button
    reg_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_register, pattern="^register$")],
        states={
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
            ASK_REF:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_ref)],
            ASK_FEE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_fee)],
            ASK_TX:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_tx)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv)
    app.add_handler(bypass_conv)
    app.add_handler(reg_conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("menu",        menu))
    app.add_handler(CommandHandler("verify",      verify_deposit))
    app.add_handler(CommandHandler("withdraw",    withdraw))
    app.add_handler(CommandHandler("stats",       stats))
    app.add_handler(CommandHandler("signal",      signal))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("referral",    referral))
    app.add_handler(CommandHandler("admin",       admin))
    app.add_handler(CommandHandler("help",        help_cmd))
    app.add_handler(CommandHandler("mykey",       mykey))
    app.add_handler(CommandHandler("myaddress",   myaddress))

    # Scheduler
    async def post_init(application):
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(lambda: asyncio.ensure_future(auto_trade(app)), 'interval', hours=1)
        scheduler.add_job(lambda: asyncio.ensure_future(auto_claim(app)), 'interval', minutes=10)
        scheduler.add_job(lambda: asyncio.ensure_future(daily_report(app)), 'cron', hour=23, minute=0)
        scheduler.start()
        logger.info("Bot started...")

    app.post_init = post_init
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
