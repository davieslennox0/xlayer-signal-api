"""
bot.py — Trend Pilot BTC + Sports Prediction Bot
AI auto-trading on Myriad Markets via Telegram
"""

import os
import io
import asyncio
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters, CallbackQueryHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
import signal_engine as se
import sniper_engine as sne
import sports_engine as spe
import wallet_manager as wm
import trader
import win_card as wc

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
TG_TOKEN       = os.getenv("TG_TOKEN")
OWNER_EVM      = os.getenv("OWNER_EVM", "0x95FB94763D57f8416A524091E641a9D26741cB31")
BYPASS_CODE    = os.getenv("BYPASS_CODE", "FLORK")
BYPASS_MAX     = int(os.getenv("BYPASS_MAX", "5"))
BYPASS_CODE2   = os.getenv("BYPASS_CODE2", "RHENA")
BYPASS_MAX2    = int(os.getenv("BYPASS_MAX2", "10"))
MIN_DEPOSIT    = float(os.getenv("MIN_DEPOSIT", "5.0"))
SIGNAL_THRESH  = float(os.getenv("SIGNAL_THRESH", "80.0"))
BET_AMOUNT     = float(os.getenv("BET_AMOUNT", "2.0"))
WINNING_FEE    = 0.025
SPORTS_MIN_BET = 5.0
SPORTS_MAX_BET = 500.0
REFERRAL_PTS   = 100

# Conversation states
ASK_EMAIL, ASK_FEE, ASK_TX, ASK_BYPASS, ASK_SPORT_AMOUNT = range(5)


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
         InlineKeyboardButton("🔑 Bypass Code",  callback_data="do_bypass")],
    ])


def main_menu_keyboard(owner=False):
    buttons = [
        [InlineKeyboardButton("📊 BTC Signal",   callback_data="signal"),
         InlineKeyboardButton("⚽ Sports Pick",  callback_data="sports_pick")],
        [InlineKeyboardButton("💰 Balance",      callback_data="balance"),
         InlineKeyboardButton("📋 History",      callback_data="history")],
        [InlineKeyboardButton("📂 Stats",        callback_data="stats"),
         InlineKeyboardButton("🏆 Leaderboard",  callback_data="leaderboard")],
        [InlineKeyboardButton("⭐ Points",       callback_data="points"),
         InlineKeyboardButton("👥 Referral",     callback_data="referral")],
        [InlineKeyboardButton("⚙️ Settings",    callback_data="settings"),
         InlineKeyboardButton("📥 Deposit",      callback_data="deposit")],
        [InlineKeyboardButton("📤 Withdraw",     callback_data="withdraw"),
         InlineKeyboardButton("❓ Help",         callback_data="help")],
    ]
    if owner:
        buttons.append([InlineKeyboardButton("🛠 Admin Dashboard", callback_data="admin")])
    return InlineKeyboardMarkup(buttons)



def settings_keyboard(user):
    btc_status   = "✅ ON" if user["btc_auto_trade"] else "❌ OFF"
    sport_status = "✅ ON" if user["sports_betting"] else "❌ OFF"
    btc_amt      = user["btc_bet_amount"] if user["btc_bet_amount"] else 2.0
    sport_amt    = user["sports_bet_amount"]
    mode         = user["trading_mode"] if user["trading_mode"] else "hybrid"
    mode_labels  = {"precision": "🎯 Precision", "sniper": "⚡ Sniper", "hybrid": "🔥 Hybrid"}
    mode_label   = mode_labels.get(mode, "🔥 Hybrid")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"₿ BTC Auto-trade: {btc_status}", callback_data="toggle_btc")],
        [InlineKeyboardButton(f"₿ BTC Bet Amount: ${btc_amt:.0f}", callback_data="set_btc_amount")],
        [InlineKeyboardButton(f"⚽ Sports Betting: {sport_status}", callback_data="toggle_sports")],
        [InlineKeyboardButton(f"💵 Sports Bet Amount: ${sport_amt:.0f}", callback_data="set_sport_amount")],
        [InlineKeyboardButton(f"🤖 Mode: {mode_label}", callback_data="cycle_mode")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu")],
    ])


def sport_confirm_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm Bet", callback_data="sport_confirm"),
         InlineKeyboardButton("❌ Skip",        callback_data="sport_skip")],
    ])


# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    name = update.effective_user.first_name or "Trader"

    db.create_user(uid, name)
    user = db.get_user(uid)

    # Auto-detect referral from link
    if ctx.args and not user["referred_by"]:
        ref_code = ctx.args[0].upper()
        referrer = db.get_user_by_referral_code(ref_code)
        if referrer and str(referrer["telegram_id"]) != uid:
            db.update_user(uid, referred_by=ref_code)

    if user["is_active"]:
        await update.message.reply_text(
            f"👋 Welcome back *{name}*!\n\nYour bot is active and trading.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(user["is_owner"] == 1)
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"👋 Welcome *{name}*!\n\n"
        f"🤖 *Trend Pilot — AI Trading Bot*\n\n"
        f"Automatically trades BTC UP/DOWN markets and sports prediction markets on Myriad Markets.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ AI BTC trading 24/7\n"
        f"✅ AI Sports betting\n"
        f"✅ Auto-claims winnings\n"
        f"✅ Daily P&L reports\n"
        f"✅ 2.5% fee on winnings only\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*What you need:*\n"
        f"1️⃣ $2 USD1 — first month subscription\n"
        f"2️⃣ $5+ USD1 — trading capital\n"
        f"3️⃣ ~0.002 BNB — gas fee\n\n"
        f"All on *Binance Smart Chain (BSC)*\n\n"
        f"_$2/month billed on the 28th_",
        parse_mode="Markdown",
        reply_markup=welcome_keyboard()
    )
    return ConversationHandler.END


# ── Registration ──────────────────────────────────────────────────────────────
async def start_register(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📧 Enter your *Myriad email* to begin:",
        parse_mode="Markdown"
    )
    return ASK_EMAIL


async def how_it_works(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🤖 *How Trend Pilot Works*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*BTC AI Trading*\n"
        "Analyzes 5-min BTC candles using RSI, MACD, VWAP, Bollinger Bands, "
        "Order Book pressure, Volume trends and candle patterns. Trades when confidence > 80%.\n\n"
        "*Sports AI Betting*\n"
        "Scans Myriad prediction markets for sports games. Scores each market "
        "by probability, liquidity and volume. Notifies you before major games — you confirm each bet.\n\n"
        "*Winnings*\n"
        "Auto-claimed every 10 minutes. 2.5% platform fee on profits only.\n"
        "━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=welcome_keyboard()
    )


async def ask_email(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = str(update.effective_user.id)
    email = update.message.text.strip().lower()

    if "@" not in email or "." not in email:
        await update.message.reply_text("❌ Invalid email. Please enter a valid email:")
        return ASK_EMAIL

    conn = db.get_conn()
    existing = conn.execute(
        "SELECT telegram_id FROM users WHERE email = ? AND telegram_id != ?",
        (email, uid)
    ).fetchone()
    conn.close()

    if existing:
        await update.message.reply_text("❌ Email already registered. Use another:")
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
        f"⚠️ *SAVE YOUR PRIVATE KEY:*\n"
        f"`{wallet['private_key']}`\n\n"
        f"• Import to MetaMask to access funds\n"
        f"• Use /mykey anytime to retrieve it\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Subscription Payment*\n\n"
        f"Send *$2.00 USD1* to activate your account:\n\n"
        f"`{OWNER_EVM}`\n\n"
        f"Once sent, paste the *transaction hash* here.",
        parse_mode="Markdown"
    )
    return ASK_FEE


async def ask_fee(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    tx_hash = update.message.text.strip()
    user    = db.get_user(uid)

    if not tx_hash.startswith("0x") or len(tx_hash) < 60:
        await update.message.reply_text("❌ Invalid tx hash. Paste the correct one:")
        return ASK_FEE

    if db.tx_already_used(tx_hash):
        await update.message.reply_text("❌ Transaction already used.")
        return ASK_FEE

    await update.message.reply_text("⏳ Verifying access fee...")
    result = wm.verify_tx_payment(tx_hash, OWNER_EVM, 2.0)

    if not result["valid"]:
        await update.message.reply_text(
            f"❌ *Failed*: {result['error']}\n\nTry again:",
            parse_mode="Markdown"
        )
        return ASK_FEE

    sub_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db.log_deposit(user["id"], tx_hash, result["amount"], "subscription")
    db.update_user(uid, fee_paid=1, subscription_date=sub_date, is_suspended=0)

    # Referral points
    if user["referred_by"]:
        referrer = db.get_user_by_referral_code(user["referred_by"])
        if referrer:
            db.add_points(str(referrer["telegram_id"]), REFERRAL_PTS)
            db.log_referral(referrer["id"], user["id"])

    await update.message.reply_text(
        f"✅ *Subscription activated!* ${result['amount']:.2f} USD1\n\n"
        f"*Fund Your Trading Wallet*\n\n"
        f"Send trading capital to YOUR wallet:\n\n"
        f"`{user['wallet_address']}`\n\n"
        f"• Minimum: *$5 USD1*\n"
        f"• Plus: *~0.002 BNB* for gas\n\n"
        f"Once sent, paste the *transaction hash* here.",
        parse_mode="Markdown"
    )
    return ASK_TX


async def ask_tx(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    tx_hash = update.message.text.strip()
    user    = db.get_user(uid)

    if not user["fee_paid"]:
        await update.message.reply_text("⚠️ Complete Step 1 first — pay the $5 access fee.")
        return ASK_FEE

    if not tx_hash.startswith("0x") or len(tx_hash) < 60:
        await update.message.reply_text("❌ Invalid tx hash. Paste the correct one:")
        return ASK_TX

    if db.tx_already_used(tx_hash):
        await update.message.reply_text("❌ Transaction already used.")
        return ASK_TX

    await update.message.reply_text("⏳ Verifying deposit...")
    result = wm.verify_tx_payment(tx_hash, user["wallet_address"], MIN_DEPOSIT)

    if not result["valid"]:
        await update.message.reply_text(
            f"❌ *Failed*: {result['error']}\n\nTry again:",
            parse_mode="Markdown"
        )
        return ASK_TX

    db.log_deposit(user["id"], tx_hash, result["amount"], "trading")
    db.update_user(uid, is_active=1, balance=result["amount"])

    await update.message.reply_text(
        f"🎉 *Account Activated!*\n\n"
        f"💰 Balance: *${result['amount']:.2f} USD1*\n\n"
        f"Your bot is now live:\n"
        f"• BTC auto-trade: ✅ ON\n"
        f"• Sports betting: ✅ ON\n\n"
        f"Your referral code: *{user['referral_code']}*\n"
        f"Share to earn *100 points* per referral!\n\n"
        f"Use ⚙️ *Settings* to customize your preferences.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(False)
    )
    return ConversationHandler.END


# ── /bypass ───────────────────────────────────────────────────────────────────
async def bypass_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if is_active(uid):
        await update.message.reply_text("✅ Already active.", reply_markup=main_menu_keyboard(is_owner(uid)))
        return ConversationHandler.END
    if db.count_bypass_uses() >= BYPASS_MAX:
        await update.message.reply_text("❌ Bypass limit reached.")
        return ConversationHandler.END
    await update.message.reply_text("🔑 Enter bypass code:")
    return ASK_BYPASS


async def check_bypass(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    code = update.message.text.strip()

    if db.count_bypass_uses() >= BYPASS_MAX:
        await update.message.reply_text("❌ Bypass limit reached.")
        return ConversationHandler.END

    if code != BYPASS_CODE and code != BYPASS_CODE2:
        await update.message.reply_text("❌ Wrong code.")
        return ConversationHandler.END

    # Check limit for each code separately
    if code == BYPASS_CODE2:
        conn_b = db.get_conn()
        code2_uses = conn_b.execute(
            "SELECT COUNT(*) FROM bypass_uses WHERE bypass_code = ?", ("RHENA",)
        ).fetchone()[0]
        conn_b.close()
        if code2_uses >= BYPASS_MAX2:
            await update.message.reply_text("❌ This bypass code has reached its limit.")
            return ConversationHandler.END

    conn = db.get_conn()
    already = conn.execute("SELECT id FROM bypass_uses WHERE telegram_id = ?", (uid,)).fetchone()
    conn.close()
    if already:
        await update.message.reply_text("❌ Already used bypass.")
        return ConversationHandler.END

    db.log_bypass_use(uid, code)
    db.update_user(uid, is_active=1, fee_paid=1, balance=0)

    remaining = BYPASS_MAX - db.count_bypass_uses()
    await update.message.reply_text(
        f"✅ *Owner bypass!* Remaining: {remaining}/{BYPASS_MAX}",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(False)
    )
    return ConversationHandler.END


# ── /menu ─────────────────────────────────────────────────────────────────────
async def menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user or not is_active(uid):
        await update.message.reply_text("❌ Use /start to register.")
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
        await update.message.reply_text("Usage: /verify <tx_hash>")
        return

    tx_hash = ctx.args[0].strip()
    if db.tx_already_used(tx_hash):
        await update.message.reply_text("❌ Already used.")
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
        f"Balance: *${db.get_user(uid)['balance']:.2f}*",
        parse_mode="Markdown"
    )


# ── /mykey / /myaddress ───────────────────────────────────────────────────────
async def mykey(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user or not user["wallet_key"]:
        await update.message.reply_text("❌ No wallet. Use /start.")
        return
    try:
        pk = wm.decrypt_key(user["wallet_key"])
        await update.message.reply_text(
            f"🔐 *Private Key*\n`{pk}`\n\n⚠️ Never share.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def myaddress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user:
        await update.message.reply_text("❌ No wallet. Use /start.")
        return
    await update.message.reply_text(
        f"💳 *Wallet*\n`{user['wallet_address']}`\nNetwork: BSC",
        parse_mode="Markdown"
    )


# ── Sports bet amount conversation ────────────────────────────────────────────
async def ask_sport_amount_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    # Check pending setting from DB
    conn2 = db.get_conn()
    pending2 = conn2.execute(
        "SELECT pending_setting FROM users WHERE telegram_id = ?", (uid,)
    ).fetchone()
    conn2.close()
    if not pending2 or pending2[0] != "sport_amount":
        return
    try:
        amount = float(update.message.text.strip())
        if amount < 1.0:
            await update.message.reply_text(f"❌ Minimum is $1. Enter again:")
            return ASK_SPORT_AMOUNT
        if amount > SPORTS_MAX_BET:
            await update.message.reply_text(f"❌ Maximum is ${SPORTS_MAX_BET}. Enter again:")
            return ASK_SPORT_AMOUNT
        db.update_user(uid, sports_bet_amount=amount)
        db.update_user(uid, pending_setting=None)
        user = db.get_user(uid)
        await update.message.reply_text(
            f"✅ Sports bet amount set to *${amount:.0f}*",
            parse_mode="Markdown",
            reply_markup=settings_keyboard(user)
        )
    except ValueError:
        await update.message.reply_text("❌ Enter a number:")
        return ASK_SPORT_AMOUNT
    return ConversationHandler.END


async def ask_btc_amount_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    # Check pending setting from DB
    conn = db.get_conn()
    pending = conn.execute(
        "SELECT pending_setting FROM users WHERE telegram_id = ?", (uid,)
    ).fetchone()
    conn.close()
    if not pending or pending[0] != "btc_amount":
        return
    try:
        amount = float(update.message.text.strip())
        if amount < 1:
            await update.message.reply_text("❌ Minimum is $1. Enter again:")
            return
        if amount > 500:
            await update.message.reply_text("❌ Maximum is $500. Enter again:")
            return
        db.update_user(uid, btc_bet_amount=amount, pending_setting=None)
        user = db.get_user(uid)
        await update.message.reply_text(
            f"✅ BTC bet amount set to *${amount:.0f}*",
            parse_mode="Markdown",
            reply_markup=settings_keyboard(user)
        )
    except ValueError:
        await update.message.reply_text("❌ Enter a number:")


# ── /history ─────────────────────────────────────────────────────────────────
async def history_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user or not is_active(uid):
        await update.message.reply_text("❌ Account not active.")
        return

    conn = db.get_conn()

    # Get BTC/ETH trades
    btc_trades = conn.execute("""
        SELECT trade_type, direction, amount, result, pnl, confidence,
               market_title, outcome_title, placed_at
        FROM trades WHERE user_id = ?
        ORDER BY placed_at DESC LIMIT 10
    """, (user["id"],)).fetchall()

    # Get sports bets
    sport_bets = conn.execute("""
        SELECT market_title, outcome_title, amount, result, pnl,
               confidence, status, placed_at
        FROM sports_bets WHERE user_id = ?
        ORDER BY placed_at DESC LIMIT 5
    """, (user["id"],)).fetchall()

    conn.close()

    if not btc_trades and not sport_bets:
        await update.message.reply_text(
            "📭 No trades yet.",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )
        return

    lines = ["📋 *Trade History*", "━━━━━━━━━━━━━━━━━━━━"]

    # BTC/ETH trades
    for t in btc_trades:
        asset  = (t["trade_type"] or "btc").upper()
        emoji  = "₿" if asset == "BTC" else "Ξ"
        direct = (t["direction"] or "").upper()
        amount = t["amount"] or 0
        conf   = t["confidence"] or 0
        time   = t["placed_at"][:16] if t["placed_at"] else ""

        if t["result"] == "win":
            status = f"🟢 Won +${t['pnl']:.2f}"
        elif t["result"] == "loss":
            status = f"🔴 Lost -${amount:.2f}"
        else:
            status = "⚫ Pending"

        market = t["market_title"] or f"{asset} candles"
        lines.append(
            f"{emoji} *{asset} {direct}* — ${amount:.2f}\n"
            f"   {status} | {conf:.0f}% conf | {time}"
        )

    if sport_bets:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚽ *Sports Bets*")
        for b in sport_bets:
            amount = b["amount"] or 0
            conf   = b["confidence"] or 0
            time   = b["placed_at"][:16] if b["placed_at"] else ""
            market = (b["market_title"] or "")[:35]
            pick   = b["outcome_title"] or ""

            if b["result"] == "win":
                status = f"🟢 Won +${b['pnl']:.2f}"
            elif b["result"] == "loss":
                status = f"🔴 Lost -${amount:.2f}"
            else:
                status = "⚫ Pending"

            lines.append(
                f"⚽ *{pick}* — ${amount:.2f}\n"
                f"   {market}\n"
                f"   {status} | {conf:.0f}% conf | {time}"
            )

    lines.append("━━━━━━━━━━━━━━━━━━━━")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_owner(uid))
    )


# ── /help ─────────────────────────────────────────────────────────────────────
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    await update.message.reply_text(
        "🤖 *Trend Pilot Commands*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "/start — register\n"
        "/menu — main menu\n"
        "/verify <tx> — credit deposit\n"
        "/mykey — your private key\n"
        "/myaddress — your wallet\n"
        "/signal — BTC AI signal\n"
        "/sports — sports AI pick\n"
        "/stats — P&L history\n"
        "/leaderboard — top traders\n"
        "/points — your points\n"
        "/referral — referral link\n"
        "/settings — preferences\n"
        "/withdraw — withdrawal info\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "_2.5% fee on winnings only_",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_owner(uid))
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
        f"📊 *Your Stats*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Trades   : {s['total_trades']}\n"
        f"Wins     : {s['wins']} ✅  Losses: {s['losses']} ❌\n"
        f"Win Rate : {wr}%\n"
        f"P&L      : ${s['total_pnl'] or 0:.2f}\n"
        f"Volume   : ${s['total_volume'] or 0:.2f}\n"
        f"Points   : ⭐ {user['points']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Balance  : *${user['balance']:.2f} USD1*",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_owner(uid))
    )


# ── /signal ───────────────────────────────────────────────────────────────────
async def signal_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_active(uid):
        await update.message.reply_text("❌ Account not active.")
        return
    await update.message.reply_text("⏳ Analyzing BTC & ETH...")
    try:
        btc = se.generate_signal()
        await update.message.reply_text(se.format_signal(btc), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ BTC signal error: {e}")
    try:
        eth = se.generate_eth_signal()
        await update.message.reply_text(
            se.format_signal(eth),
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ ETH signal error: {e}")


# ── /sports ───────────────────────────────────────────────────────────────────
async def sports_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not is_active(uid):
        await update.message.reply_text("❌ Account not active.")
        return
    if not user["sports_betting"]:
        await update.message.reply_text("⚽ Sports betting is OFF. Enable in /settings")
        return

    await update.message.reply_text("⏳ Scanning sports markets...")
    try:
        pick = spe.find_best_sports_bet(min_confidence=55.0)
        if not pick:
            await update.message.reply_text(
                "📭 No strong sports picks right now.\n\nCheck back before major game times.",
                reply_markup=main_menu_keyboard(is_owner(uid))
            )
            return

        amount = user["sports_bet_amount"]
        db.save_pending_sport(
            user["id"], pick["market_id"], pick["network_id"],
            pick["market_title"], pick["outcome_id"],
            pick["outcome_title"], pick["confidence"], pick["expires_at"]
        )

        await update.message.reply_text(
            spe.format_sports_pick(pick, amount),
            parse_mode="Markdown",
            reply_markup=sport_confirm_keyboard()
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Sports error: {e}")


# ── /leaderboard ──────────────────────────────────────────────────────────────
async def leaderboard_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = db.get_leaderboard(10)
    if not rows:
        await update.message.reply_text("📭 No data yet.")
        return
    lines  = ["🏆 *Top Traders by Volume*", "━━━━━━━━━━━━━━━━━━━━"]
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows):
        addr   = row["wallet_address"] or "Unknown"
        short  = f"{addr[:6]}...{addr[-4:]}" if len(addr) > 10 else addr
        medal  = medals[i] if i < 3 else f"{i+1}."
        vol    = row["total_volume"] or 0
        profit = row["total_profit"] or 0
        trades = row["total_trades"] or 0
        sym    = "+" if profit >= 0 else ""
        lines.append(f"{medal} `{short}`\n   Vol: ${vol:.2f} | P&L: {sym}${profit:.2f} | {trades} trades")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_owner(str(update.effective_user.id)))
    )


# ── /points ───────────────────────────────────────────────────────────────────
async def points_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user or not is_active(uid):
        await update.message.reply_text("❌ Account not active.")
        return

    rows   = db.get_points_leaderboard(10)
    rank   = next((i+1 for i, r in enumerate(rows)
                   if r["wallet_address"] == user["wallet_address"]), "N/A")
    count  = db.get_referral_count(user["id"])

    await update.message.reply_text(
        f"⭐ *Your Points*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Points     : *{user['points']}*\n"
        f"Rank       : #{rank}\n"
        f"Referrals  : {count} (×{REFERRAL_PTS} pts each)\n\n"
        f"*Points Leaderboard Top 5:*\n",
        parse_mode="Markdown"
    )

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows[:5]):
        addr  = row["wallet_address"] or "?"
        short = f"{addr[:6]}...{addr[-4:]}"
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} `{short}` — ⭐ {row['points']}")

    await update.message.reply_text(
        "\n".join(lines) if lines else "No data yet.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_owner(uid))
    )


# ── /referral ─────────────────────────────────────────────────────────────────
async def referral_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user or not is_active(uid):
        await update.message.reply_text("❌ Account not active.")
        return
    count = db.get_referral_count(user["id"])
    await update.message.reply_text(
        f"👥 *Your Referral*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Code       : *{user['referral_code']}*\n"
        f"Referrals  : {count}\n"
        f"Points     : ⭐ {count * REFERRAL_PTS}\n\n"
        f"Share your link:\n"
        f"👉 t.me/pilotrend_bot?start={user['referral_code']}\n\n"
        f"Earn *{REFERRAL_PTS} points* per referral!",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_owner(uid))
    )


# ── /settings ─────────────────────────────────────────────────────────────────
async def settings_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)
    if not user or not is_active(uid):
        await update.message.reply_text("❌ Account not active.")
        return
    await update.message.reply_text(
        "⚙️ *Your Settings*\n\nToggle your trading preferences:",
        parse_mode="Markdown",
        reply_markup=settings_keyboard(user)
    )


# ── /analyze ─────────────────────────────────────────────────────────────────
async def analyze_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_owner(uid):
        await update.message.reply_text("❌ Admin only.")
        return

    conn = db.get_conn()

    # Overall win rate
    total = conn.execute("SELECT COUNT(*) FROM trades WHERE result IN ('win','loss')").fetchone()[0]
    wins  = conn.execute("SELECT COUNT(*) FROM trades WHERE result='win'").fetchone()[0]
    wr    = round(wins/total*100,1) if total else 0

    # Win rate by regime
    for regime in ["ranging","expanding","contracting"]:
        t = conn.execute(f"SELECT COUNT(*) FROM trades WHERE result IN ('win','loss') AND bb_regime=?", (regime,)).fetchone()[0]
        w = conn.execute(f"SELECT COUNT(*) FROM trades WHERE result='win' AND bb_regime=?", (regime,)).fetchone()[0]
        rr = round(w/t*100,1) if t else 0

    # Win rate by direction
    for d in ["up","down"]:
        t = conn.execute(f"SELECT COUNT(*) FROM trades WHERE result IN ('win','loss') AND direction=?", (d,)).fetchone()[0]
        w = conn.execute(f"SELECT COUNT(*) FROM trades WHERE result='win' AND direction=?", (d,)).fetchone()[0]

    # Best confidence range
    ranges = [(71,75),(75,80),(80,85),(85,90),(90,100)]
    range_stats = []
    for lo, hi in ranges:
        t = conn.execute("SELECT COUNT(*) FROM trades WHERE result IN ('win','loss') AND confidence>=? AND confidence<?", (lo,hi)).fetchone()[0]
        w = conn.execute("SELECT COUNT(*) FROM trades WHERE result='win' AND confidence>=? AND confidence<?", (lo,hi)).fetchone()[0]
        if t > 0:
            range_stats.append((lo, hi, t, round(w/t*100,1)))

    # By hour
    best_hours = conn.execute("""
        SELECT strftime('%H', placed_at) as hr,
               COUNT(*) as total,
               SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins
        FROM trades WHERE result IN ('win','loss')
        GROUP BY hr ORDER BY wins*1.0/total DESC LIMIT 3
    """).fetchall()

    conn.close()

    lines = [
        "📊 *Trade Pattern Analysis*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Total settled : {total}",
        f"Overall WR    : {wr}%",
        "━━━━━━━━━━━━━━━━━━━━",
        "*Win Rate by Confidence:*"
    ]
    for lo, hi, t, wr2 in range_stats:
        lines.append(f"  {lo}-{hi}% conf: {wr2}% WR ({t} trades)")

    if best_hours:
        lines.append("*Best Hours (UTC):*")
        for h in best_hours:
            hr_wr = round(h[2]/h[1]*100,1) if h[1] else 0
            lines.append(f"  {h[0]}:00 UTC — {hr_wr}% WR ({h[1]} trades)")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("_More patterns unlock after 50+ trades_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(True)
    )


# ── /admin ────────────────────────────────────────────────────────────────────
async def admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_owner(uid):
        await update.message.reply_text("❌ Admin only.")
        return
    s = db.get_admin_stats()
    await update.message.reply_text(
        f"🛠 *Admin Dashboard*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Users      : {s['total_users']} ({s['active_users']} active)\n"
        f"₿  BTC traders: {s['btc_traders']}\n"
        f"⚽ Sports     : {s['sports_bettors']}\n"
        f"👥 Referrals  : {s['total_referrals']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 Trades     : {s['total_trades']} ({s['today_trades']} today)\n"
        f"📊 Volume     : ${s['total_volume']:.2f} (${s['today_volume']:.2f} today)\n"
        f"⚽ Sports Bets: {s['sports_bets']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Total Fees : ${s['total_fees']:.4f}\n"
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
        await query.message.reply_text("📧 Enter your *Myriad email*:", parse_mode="Markdown")
        return

    if data == "howto":
        await how_it_works(update, ctx)
        return

    if data == "do_bypass":
        if db.count_bypass_uses() >= BYPASS_MAX:
            await query.message.reply_text("❌ Bypass limit reached.")
            return
        await query.message.reply_text("🔑 Use /bypass command and enter your code:")
        return

    if data == "menu":
        user = db.get_user(uid)
        await query.message.reply_text(
            "🤖 *Trend Pilot*\nChoose an option:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(user and user["is_owner"] == 1)
        )
        return

    if not is_active(uid):
        await query.message.reply_text("❌ Use /start to register.")
        return

    user = db.get_user(uid)

    if data == "signal":
        await query.message.reply_text("⏳ Analyzing BTC & ETH...")
        best = None
        try:
            btc = se.generate_signal()
            await query.message.reply_text(se.format_signal(btc), parse_mode="Markdown")
            if not best or btc["confidence"] > best["confidence"]:
                best = btc
        except Exception as e:
            await query.message.reply_text(f"⚠️ BTC: {e}")
        try:
            eth = se.generate_eth_signal()
            await query.message.reply_text(se.format_signal(eth), parse_mode="Markdown")
            if not best or eth["confidence"] > best["confidence"]:
                best = eth
        except Exception as e:
            await query.message.reply_text(f"⚠️ ETH: {e}")

        # If signal is tradeable, offer to trade now
        if best and best["tradeable"]:
            await query.message.reply_text(
                f"⚡ Signal above threshold!\n"
                f"Auto-trade fires on next scan.\n"
                f"Tap below to trade NOW:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"⚡ Trade {best['asset']} {best['direction'].upper()} NOW",
                                         callback_data=f"manual_trade_{best['asset'].lower()}_{best['direction']}")],
                    [InlineKeyboardButton("⏭ Skip", callback_data="menu")]
                ])
            )
        else:
            await query.message.reply_text(
                "📋 Menu:", reply_markup=main_menu_keyboard(is_owner(uid))
            )

    elif data == "sports_pick":
        if not user["sports_betting"]:
            await query.message.reply_text("⚽ Sports betting is OFF. Enable in ⚙️ Settings.")
            return
        await query.message.reply_text("⏳ Scanning sports markets...")
        try:
            pick = spe.find_best_sports_bet(min_confidence=55.0)
            if not pick:
                await query.message.reply_text(
                    "📭 No strong sports picks right now.",
                    reply_markup=main_menu_keyboard(is_owner(uid))
                )
                return
            amount = user["sports_bet_amount"]
            db.save_pending_sport(
                user["id"], pick["market_id"], pick["network_id"],
                pick["market_title"], pick["outcome_id"],
                pick["outcome_title"], pick["confidence"], pick["expires_at"]
            )
            await query.message.reply_text(
                spe.format_sports_pick(pick, amount),
                parse_mode="Markdown",
                reply_markup=sport_confirm_keyboard()
            )
        except Exception as e:
            await query.message.reply_text(f"⚠️ {e}")

    elif data == "sport_confirm":
        pending = db.get_pending_sport(user["id"])
        if not pending:
            await query.message.reply_text("❌ No pending sports bet.")
            return
        amount = user["sports_bet_amount"]
        if user["balance"] < amount:
            await query.message.reply_text(
                f"❌ Insufficient balance. Need ${amount:.2f}, have ${user['balance']:.2f}"
            )
            return
        try:
            await query.message.reply_text("⏳ Placing sports bet...")
            pk     = wm.decrypt_key(user["wallet_key"])
            result = trader.run_cli(["trade","buy","--market-id",str(pending["market_id"]),"--network-id",str(pending["network_id"]),"--outcome-id",str(pending["outcome_id"]),"--value",str(amount),"--slippage","0.05"], pk)
            execution = result.get("execution", {})
            tx = execution.get("txHash", "pending")
            db.log_sports_bet(
                pending["outcome_id"], pending["outcome_title"],
                amount, pending["confidence"], tx
            )
            db.clear_pending_sport(user["id"])
            await query.message.reply_text(
                f"✅ *Sports Bet Placed!*\n"
                f"Market : {pending['market_title'][:40]}\n"
                f"Pick   : {pending['outcome_title']}\n"
                f"Stake  : ${amount:.2f}\n"
                f"Tx     : `{tx[:20]}...`",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(is_owner(uid))
            )
        except Exception as e:
            await query.message.reply_text(f"⚠️ Bet failed: {e}")

    elif data == "sport_skip":
        db.clear_pending_sport(user["id"])
        await query.message.reply_text(
            "⏭ Skipped.",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "history":
        uid2 = str(query.from_user.id)
        user2 = db.get_user(uid2)
        conn = db.get_conn()
        btc_trades = conn.execute(
            "SELECT trade_type, direction, amount, result, pnl, confidence, market_title, placed_at FROM trades WHERE user_id = ? ORDER BY placed_at DESC LIMIT 10",
            (user2["id"],)
        ).fetchall()
        sport_bets = conn.execute(
            "SELECT market_title, outcome_title, amount, result, pnl, confidence, status, placed_at FROM sports_bets WHERE user_id = ? ORDER BY placed_at DESC LIMIT 5",
            (user2["id"],)
        ).fetchall()
        conn.close()

        if not btc_trades and not sport_bets:
            await query.message.reply_text("📭 No trades yet.", reply_markup=main_menu_keyboard(is_owner(uid2)))
            return

        lines = ["📋 *Trade History*", "━━━━━━━━━━━━━━━━━━━━"]
        for t in btc_trades:
            asset  = (t["trade_type"] or "btc").upper()
            emoji  = "₿" if asset == "BTC" else "Ξ"
            direct = (t["direction"] or "").upper()
            amount = t["amount"] or 0
            time   = t["placed_at"][:16] if t["placed_at"] else ""
            if t["result"] == "win":
                status = f"🟢 Won +${t['pnl']:.2f}"
            elif t["result"] == "loss":
                status = f"🔴 Lost -${amount:.2f}"
            else:
                status = "⚫ Pending"
            lines.append(f"{emoji} *{asset} {direct}* ${amount:.2f} | {status} | {time}")

        if sport_bets:
            lines.append("─────────────────────")
            for b in sport_bets:
                amount = b["amount"] or 0
                time   = b["placed_at"][:16] if b["placed_at"] else ""
                pick   = (b["outcome_title"] or "")[:20]
                if b["result"] == "win":
                    status = f"🟢 Won +${b['pnl']:.2f}"
                elif b["result"] == "loss":
                    status = f"🔴 Lost -${amount:.2f}"
                else:
                    status = "⚫ Pending"
                lines.append(f"⚽ *{pick}* ${amount:.2f} | {status} | {time}")

        await query.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=main_menu_keyboard(is_owner(uid2)))

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

    elif data == "stats":
        s  = db.get_user_stats(user["id"])
        wr = round(s["wins"] / s["total_trades"] * 100, 1) if s["total_trades"] else 0
        await query.message.reply_text(
            f"📊 *Stats*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Trades  : {s['total_trades']}\n"
            f"Wins    : {s['wins']} ✅  Losses: {s['losses']} ❌\n"
            f"Win Rate: {wr}%\n"
            f"P&L     : ${s['total_pnl'] or 0:.2f}\n"
            f"Volume  : ${s['total_volume'] or 0:.2f}\n"
            f"Points  : ⭐ {user['points']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Balance : *${user['balance']:.2f} USD1*",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "leaderboard":
        rows = db.get_leaderboard(10)
        if not rows:
            await query.message.reply_text("📭 No data yet.")
            return
        lines  = ["🏆 *Top Traders*", "━━━━━━━━━━━━━━━━━━━━"]
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(rows):
            addr  = row["wallet_address"] or "?"
            short = f"{addr[:6]}...{addr[-4:]}"
            medal = medals[i] if i < 3 else f"{i+1}."
            vol   = row["total_volume"] or 0
            pnl   = row["total_profit"] or 0
            sym   = "+" if pnl >= 0 else ""
            lines.append(f"{medal} `{short}` — ${vol:.2f} vol | {sym}${pnl:.2f}")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        await query.message.reply_text(
            "\n".join(lines), parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "points":
        rows  = db.get_points_leaderboard(5)
        rank  = next((i+1 for i, r in enumerate(rows)
                      if r["wallet_address"] == user["wallet_address"]), "N/A")
        count = db.get_referral_count(user["id"])
        lines = [f"⭐ *Points: {user['points']}* | Rank #{rank}",
                 f"Referrals: {count}", "━━━━━━━━━━━━━━━━━━━━",
                 "*Top 5 Points:*"]
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(rows):
            addr  = row["wallet_address"] or "?"
            short = f"{addr[:6]}...{addr[-4:]}"
            medal = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{medal} `{short}` — ⭐ {row['points']}")
        await query.message.reply_text(
            "\n".join(lines), parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "referral":
        count = db.get_referral_count(user["id"])
        await query.message.reply_text(
            f"👥 *Referral*\n"
            f"Code: *{user['referral_code']}*\n"
            f"Referrals: {count} | Points: ⭐ {count * REFERRAL_PTS}\n\n"
            f"👉 t.me/pilotrend_bot?start={user['referral_code']}\n\n"
            f"Earn *{REFERRAL_PTS} points* per referral!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "settings":
        await query.message.reply_text(
            "⚙️ *Settings*\nToggle your preferences:",
            parse_mode="Markdown",
            reply_markup=settings_keyboard(user)
        )

    elif data == "cycle_mode":
        user    = db.get_user(uid)
        current = user["trading_mode"] or "hybrid"
        modes   = ["precision", "sniper", "hybrid"]
        next_mode = modes[(modes.index(current) + 1) % len(modes)] if current in modes else "hybrid"
        db.update_user(uid, trading_mode=next_mode)
        user = db.get_user(uid)
        labels = {"precision": "🎯 Precision — quality signals only",
                  "sniper":    "⚡ Sniper — fast trigger, high frequency",
                  "hybrid":    "🔥 Hybrid — best of both worlds"}
        await query.message.reply_text(
            f"✅ Trading mode: *{labels[next_mode]}*",
            parse_mode="Markdown",
            reply_markup=settings_keyboard(user)
        )

    elif data == "toggle_btc":
        new_val = 0 if user["btc_auto_trade"] else 1
        db.update_user(uid, btc_auto_trade=new_val)
        user = db.get_user(uid)
        status = "✅ ON" if new_val else "❌ OFF"
        await query.message.reply_text(
            f"₿ BTC Auto-trade: *{status}*",
            parse_mode="Markdown",
            reply_markup=settings_keyboard(user)
        )

    elif data == "toggle_sports":
        new_val = 0 if user["sports_betting"] else 1
        db.update_user(uid, sports_betting=new_val)
        user = db.get_user(uid)
        status = "✅ ON" if new_val else "❌ OFF"
        await query.message.reply_text(
            f"⚽ Sports Betting: *{status}*",
            parse_mode="Markdown",
            reply_markup=settings_keyboard(user)
        )

    elif data == "set_sport_amount":
        await query.message.reply_text(
            f"💵 Enter sports bet amount ($1–$500):"
        )
        db.update_user(uid, pending_setting="sport_amount")

    elif data == "set_btc_amount":
        await query.message.reply_text(
            f"₿ Enter BTC bet amount ($1–$500):"
        )
        db.update_user(uid, pending_setting="btc_amount")

    elif data == "deposit":
        await query.message.reply_text(
            f"📥 *Deposit*\n\n"
            f"Send USD1 + ~0.002 BNB to:\n`{user['wallet_address']}`\n\n"
            f"Then use /verify <tx\\_hash>",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "withdraw":
        await query.message.reply_text(
            "💸 Visit myriad.markets → connect wallet → withdraw.",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "admin":
        if not is_owner(uid):
            await query.message.reply_text("❌ Admin only.")
            return
        s = db.get_admin_stats()
        await query.message.reply_text(
            f"🛠 *Admin*\n"
            f"Users: {s['active_users']}/{s['total_users']}\n"
            f"BTC traders: {s['btc_traders']} | Sports: {s['sports_bettors']}\n"
            f"Trades: {s['total_trades']} | Vol: ${s['total_volume']:.2f}\n"
            f"Fees: ${s['total_fees']:.4f}",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(True)
        )

    elif data == "help":
        await query.message.reply_text(
            "🤖 *Trend Pilot*\n/start /menu /verify /signal /sports\n/stats /leaderboard /points /referral /settings",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )

    elif data == "mykey":
        try:
            pk = wm.decrypt_key(user["wallet_key"])
            await query.message.reply_text(f"🔐 `{pk}`\n\n⚠️ Never share.", parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ {e}")

    elif data == "myaddress":
        await query.message.reply_text(
            f"💳 `{user['wallet_address']}`\nBSC", parse_mode="Markdown",
            reply_markup=main_menu_keyboard(is_owner(uid))
        )


# ── Win card sender ───────────────────────────────────────────────────────────
async def send_win_card(app, chat_id: str, username: str, market_title: str,
                        outcome: str, stake: float, payout: float,
                        profit: float, roi: float, rank: int, bet_type: str):
    try:
        card_bytes = wc.generate_win_card(
            username, market_title, outcome,
            stake, payout, profit, roi, rank, bet_type
        )
        if card_bytes:
            await app.bot.send_photo(
                chat_id=chat_id,
                photo=io.BytesIO(card_bytes),
                caption=f"🏆 *You won ${profit:.2f} USD1!*\nROI: +{roi:.1f}%",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Win card error: {e}")


# ── Auto-trader ───────────────────────────────────────────────────────────────
async def auto_trade(app: Application):
    logger.info("Running auto-trade scan...")

    # Run BTC and ETH signals
    signals = []
    try:
        btc_sig = se.generate_signal()
        signals.append(btc_sig)
    except Exception as e:
        logger.error(f"BTC signal error: {e}")

    try:
        eth_sig = se.generate_eth_signal()
        signals.append(eth_sig)
    except Exception as e:
        logger.error(f"ETH signal error: {e}")

    if not signals:
        return

    # Use the highest confidence signal
    sig = max(signals, key=lambda s: s["confidence"])
    logger.info(f"Best signal: {sig.get('asset','BTC')} {sig['confidence']}% {sig['label']}")

    users = db.get_btc_traders()

    if not sig["tradeable"]:
        logger.info(f"Signal {sig['confidence']}% below threshold — skipping")
        return

    users = [u for u in users if (u["trading_mode"] or "hybrid") in ["precision", "hybrid"]]
    for user in users:
        uid = user["telegram_id"]

        # Skip suspended users
        if user["is_suspended"]:
            continue

        # Sync on-chain balance before trading
        try:
            onchain = wm.get_usd1_balance(user["wallet_address"])
            if onchain > 0 and abs(onchain - user["balance"]) > 0.5:
                db.update_user(uid, balance=onchain)
                user = db.get_user(uid)
                logger.info(f"Synced balance for {uid}: ${onchain:.4f}")
        except Exception:
            pass

        if user["balance"] < BET_AMOUNT:
            try:
                await app.bot.send_message(
                    chat_id=uid,
                    text=f"⚠️ Insufficient balance (${user['balance']:.2f}). Deposit more USD1 to continue trading.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            continue

        try:
            pk     = wm.decrypt_key(user["wallet_key"])
            result = trader.place_trade(pk, sig["direction"], BET_AMOUNT, sig.get("asset", "bitcoin").lower())
            tx     = result.get("buy_tx", "pending")
            db.deduct_balance(uid, BET_AMOUNT)
            # Sync on-chain balance after trade
            try:
                onchain = wm.get_usd1_balance(user["wallet_address"])
                if onchain >= 0:
                    db.update_user(uid, balance=onchain)
            except Exception:
                pass
            db.log_trade(
                user["id"], sig["direction"], BET_AMOUNT,
                sig["confidence"], result.get("market_id", 0),
                result.get("outcome_id", 0), tx,
                sig.get("asset", "btc").lower(),
                result.get("market", ""), result.get("outcome", ""),
                bb_regime   = sig.get("bb_regime", ""),
                rsi         = sig.get("rsi", 0),
                bias        = sig.get("bias", 0),
                aggression  = sig.get("aggression", ""),
                vwap_dist   = sig.get("vwap_dist", 0),
                funding     = sig.get("funding", 0)
            )
            await app.bot.send_message(
                chat_id=uid,
                text=(
                    f"✅ *BTC Auto-trade!*\n"
                    f"Direction: {sig['direction'].upper()} | "
                    f"Confidence: {sig['confidence']}%\n"
                    f"Stake: ${BET_AMOUNT} | Tx: `{tx[:16]}...`\n"
                    f"Balance: ${db.get_user(uid)['balance']:.2f}"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Trade failed {uid}: {e}")


# ── Sports scanner ────────────────────────────────────────────────────────────
async def sports_scan(app: Application):
    """Run before major game times — notify sports bettors of best pick."""
    logger.info("Running sports scan...")
    try:
        pick = spe.find_best_sports_bet(min_confidence=60.0)
        if not pick:
            return

        users = db.get_sports_bettors()
        for user in users:
            uid = user["telegram_id"]
            try:
                amount = user["sports_bet_amount"]
                db.save_pending_sport(
                    user["id"], pick["market_id"], pick["network_id"],
                    pick["market_title"], pick["outcome_id"],
                    pick["outcome_title"], pick["confidence"], pick["expires_at"]
                )
                await app.bot.send_message(
                    chat_id=uid,
                    text=spe.format_sports_pick(pick, amount),
                    parse_mode="Markdown",
                    reply_markup=sport_confirm_keyboard()
                )
            except Exception as e:
                logger.error(f"Sports notify error {uid}: {e}")

    except Exception as e:
        logger.error(f"Sports scan error: {e}")


# ── Sniper scanner ───────────────────────────────────────────────────────────
_last_sniper_trade = {}  # uid -> market window they last traded

async def sniper_scan(app: Application):
    """Run every 60 seconds — fires on sniper triggers for sniper/hybrid users.
    Only ONE trade per 5-minute market window per user.
    """
    import time
    from datetime import datetime, timezone

    # Get current 5-minute window key e.g. "2026-03-19-01-45"
    now = datetime.now(timezone.utc)
    window = now.strftime("%Y-%m-%d-%H-") + str((now.minute // 5) * 5).zfill(2)

    sniper_users = [u for u in db.get_btc_traders()
                    if (u["trading_mode"] or "hybrid") in ["sniper", "hybrid"]]
    if not sniper_users:
        return

    best = None
    for asset in ["BTC", "ETH"]:
        try:
            sig = sne.generate_sniper_signal(asset)
            logger.info(f"Sniper {asset}: score={sig['score']} {sig['label']}")
            if sig["tradeable"]:
                if not best or abs(sig["score"]) > abs(best["score"]):
                    best = sig
        except Exception as e:
            logger.error(f"Sniper error {asset}: {e}")

    if not best:
        return

    logger.info(f"Sniper firing: {best['asset']} {best['direction']}")

    for user in sniper_users:
        uid = user["telegram_id"]
        bet = user["btc_bet_amount"] if user["btc_bet_amount"] else BET_AMOUNT
        if user["balance"] < bet:
            continue

        # Skip suspended users
        if user["is_suspended"]:
            continue

        # One trade per 5-minute market window per user (across ALL assets)
        last_window = _last_sniper_trade.get(uid, "")
        if last_window == window:
            logger.info(f"Sniper already traded this window ({window}) for {uid} — skipping")
            continue

        # Verify real on-chain balance before trading
        try:
            onchain = wm.get_usd1_balance(user["wallet_address"])
            if onchain < bet:
                logger.info(f"Insufficient on-chain balance for {uid}: ${onchain:.4f}")
                continue
        except Exception:
            pass

        try:
            pk     = wm.decrypt_key(user["wallet_key"])
            result = trader.place_trade(pk, best["direction"], bet, best["asset"].lower())
            tx     = result.get("buy_tx", "pending")
            try:
                onchain = wm.get_usd1_balance(user["wallet_address"])
                if onchain >= 0:
                    db.update_user(uid, balance=onchain)
            except Exception:
                pass
            db.log_trade(
                user["id"], best["direction"], bet, best["confidence"],
                result.get("market_id", 0), result.get("outcome_id", 0),
                tx, best["asset"].lower(),
                result.get("market", ""), result.get("outcome", "")
            )
            # Mark window as traded AFTER successful trade
            _last_sniper_trade[uid] = window
            triggers_text = "\n".join(best["triggers"]) if best["triggers"] else ""
            await app.bot.send_message(
                chat_id=uid,
                text=(
                    f"🔫 *Sniper Trade Fired!*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Asset    : {best['asset']}\n"
                    f"Direction: {best['direction'].upper()}\n"
                    f"Stake    : ${bet:.2f}\n"
                    f"{triggers_text}\n"
                    f"Tx: `{tx[:20]}...`"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Sniper trade failed {uid}: {e}")


# ── Auto-claim ────────────────────────────────────────────────────────────────
async def auto_claim(app: Application):
    logger.info("Running auto-claim...")
    users = db.get_all_active_users()

    for user in users:
        uid = user["telegram_id"]
        try:
            positions = trader.get_claimable_positions(user["wallet_address"])
            if not positions:
                continue

            pk = wm.decrypt_key(user["wallet_key"])

            # Get leaderboard rank
            lb   = db.get_leaderboard(100)
            rank = next((i+1 for i, r in enumerate(lb)
                         if r["wallet_address"] == user["wallet_address"]), None)

            for pos in positions:
                try:
                    result  = trader.claim_winnings(
                        pk, pos["marketId"], pos["networkId"], pos["outcomeId"]
                    )
                    payout  = round(pos.get("value", 0), 2)
                    profit  = round(pos.get("profit", 0), 2)
                    roi     = round(pos.get("roi", 0) * 100, 1)

                    fee        = round(payout * WINNING_FEE, 4)
                    user_payout = round(payout - fee, 4)

                    # Send fee on-chain
                    try:
                        fee_data = trader.build_transfer_data(OWNER_EVM, int(fee * 10**18))
                        trader.sign_and_send(pk, trader.USD1_ADDRESS, fee_data)
                        db.log_fee(user["id"], fee, 0)
                    except Exception as fe:
                        logger.error(f"Fee error: {fe}")

                    db.add_balance(uid, user_payout)
                    # Sync with on-chain after claim
                    try:
                        onchain = wm.get_usd1_balance(user["wallet_address"])
                        if onchain > 0:
                            db.update_user(uid, balance=onchain)
                    except Exception:
                        pass

                    conn = db.get_conn()
                    conn.execute(
                        "UPDATE trades SET result='win', pnl=? WHERE user_id=? AND market_id=? AND status='pending'",
                        (profit, user["id"], pos["marketId"])
                    )
                    conn.commit()
                    conn.close()

                    # Send win card
                    # Get original stake from trade log
                    conn_s = db.get_conn()
                    trade_row = conn_s.execute(
                        "SELECT amount, trade_type FROM trades WHERE user_id=? AND market_id=? ORDER BY placed_at DESC LIMIT 1",
                        (user["id"], pos["marketId"])
                    ).fetchone()
                    conn_s.close()
                    orig_stake = trade_row["amount"] if trade_row else round(payout / (1 + roi/100), 2)
                    asset_type = (trade_row["trade_type"] or "btc").upper() if trade_row else "BTC"

                    await send_win_card(
                        app, uid,
                        user["telegram_name"] or "Trader",
                        pos["marketTitle"], pos["outcomeTitle"],
                        orig_stake,
                        payout, profit, roi, rank, asset_type
                    )

                    await app.bot.send_message(
                        chat_id=uid,
                        text=(
                            f"💰 *Winnings Claimed!*\n"
                            f"Payout : ${payout:.2f} | Fee: ${fee:.4f}\n"
                            f"You get: *${user_payout:.4f} USD1*\n"
                            f"Balance: ${db.get_user(uid)['balance']:.2f}"
                        ),
                        parse_mode="Markdown"
                    )

                except Exception as e:
                    logger.error(f"Claim error {uid}: {e}")

        except Exception as e:
            logger.error(f"Auto-claim error {uid}: {e}")


# ── Subscription Manager ─────────────────────────────────────────────────────
async def subscription_warning(app: Application):
    """Send warning on 25th — top up by 28th."""
    users = db.get_all_active_users()
    for user in users:
        if user["is_owner"]:
            continue
        uid = user["telegram_id"]
        try:
            await app.bot.send_message(
                chat_id=uid,
                text=(
                    f"⚠️ *Subscription Reminder*\n\n"
                    f"Your monthly subscription of *$2 USD1* is due on the *28th*.\n\n"
                    f"Make sure your balance has at least $2 USD1 or top up before the 28th "
                    f"to avoid service interruption.\n\n"
                    f"Current balance: *${user['balance']:.2f} USD1*"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Warning error {uid}: {e}")


async def subscription_deduct(app: Application):
    """Deduct $2 on 28th — suspend if insufficient."""
    users = db.get_all_active_users()
    for user in users:
        if user["is_owner"]:
            continue
        uid = user["telegram_id"]
        try:
            onchain = wm.get_usd1_balance(user["wallet_address"])

            if onchain >= 2.0:
                # Deduct from internal balance
                db.deduct_balance(uid, 2.0)
                db.update_user(uid, is_suspended=0)

                # Send $2 to owner on-chain
                try:
                    pk = wm.decrypt_key(user["wallet_key"])
                    trader.sign_and_send(
                        pk, trader.USD1_ADDRESS,
                        trader.build_transfer_data(OWNER_EVM, int(2.0 * 10**18))
                    )
                except Exception as fe:
                    logger.error(f"Sub payment error {uid}: {fe}")

                await app.bot.send_message(
                    chat_id=uid,
                    text=(
                        "✅ *Subscription Renewed!*\n\n"
                        "$2.00 USD1 deducted for next month.\n"
                        f"Balance: *${db.get_user(uid)['balance']:.2f} USD1*\n\n"
                        "Your bot continues trading. 🚀"
                    ),
                    parse_mode="Markdown"
                )
            else:
                db.update_user(uid, is_suspended=1)
                await app.bot.send_message(
                    chat_id=uid,
                    text=(
                        "🚫 *Service Suspended*\n\n"
                        "Insufficient balance for monthly subscription ($2 USD1).\n\n"
                        "Your bot has been paused. To reactivate:\n"
                        "1. Deposit $2+ USD1 to your wallet\n"
                        "2. Use /verify <tx_hash>\n\n"
                        "All your positions and history are safe."
                    ),
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Sub deduct error {uid}: {e}")


async def check_reactivation(app: Application):
    """Auto-reactivate suspended users who topped up."""
    conn = db.get_conn()
    suspended = conn.execute(
        "SELECT * FROM users WHERE is_suspended = 1 AND is_active = 1"
    ).fetchall()
    conn.close()

    for user in suspended:
        uid = user["telegram_id"]
        try:
            onchain = wm.get_usd1_balance(user["wallet_address"])
            if onchain >= 2.0:
                db.update_user(uid, is_suspended=0, balance=onchain)
                await app.bot.send_message(
                    chat_id=uid,
                    text=(
                        "✅ *Service Reactivated!*\n\n"
                        f"Your balance is now ${onchain:.2f} USD1.\n"
                        "Bot is trading again. 🚀"
                    ),
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Reactivation error {uid}: {e}")


# ── Daily Report ──────────────────────────────────────────────────────────────
async def daily_report(app: Application):
    users = db.get_all_active_users()
    for user in users:
        try:
            conn  = db.get_conn()
            today = conn.execute(
                "SELECT COUNT(*) as trades, SUM(pnl) as pnl, SUM(amount) as volume "
                "FROM trades WHERE user_id = ? AND DATE(placed_at) = DATE('now')",
                (user["id"],)
            ).fetchone()
            conn.close()
            if not today or today["trades"] == 0:
                continue
            emoji = "📈" if (today["pnl"] or 0) >= 0 else "📉"
            await app.bot.send_message(
                chat_id=user["telegram_id"],
                text=(
                    f"📋 *Daily Report*\n"
                    f"Trades : {today['trades']}\n"
                    f"Volume : ${today['volume'] or 0:.2f}\n"
                    f"P&L    : {emoji} ${today['pnl'] or 0:.2f}\n"
                    f"Balance: *${user['balance']:.2f} USD1*"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Daily report error: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    db.init_db()
    db.migrate()

    app = Application.builder().token(TG_TOKEN)\
        .connect_timeout(60).read_timeout(60)\
        .write_timeout(60).pool_timeout(60)\
        .get_updates_read_timeout(60).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
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

    reg_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_register, pattern="^register$")],
        states={
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
            ASK_FEE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_fee)],
            ASK_TX:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_tx)],
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv)
    app.add_handler(bypass_conv)
    app.add_handler(reg_conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask_btc_amount_msg))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask_sport_amount_msg))
    app.add_handler(CommandHandler("menu",        menu))
    app.add_handler(CommandHandler("verify",      verify_deposit))
    app.add_handler(CommandHandler("mykey",       mykey))
    app.add_handler(CommandHandler("myaddress",   myaddress))
    app.add_handler(CommandHandler("signal",      signal_cmd))
    app.add_handler(CommandHandler("sports",      sports_cmd))
    app.add_handler(CommandHandler("stats",       stats))
    app.add_handler(CommandHandler("history",     history_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    app.add_handler(CommandHandler("points",      points_cmd))
    app.add_handler(CommandHandler("referral",    referral_cmd))
    app.add_handler(CommandHandler("settings",    settings_cmd))
    app.add_handler(CommandHandler("admin",       admin_cmd))
    app.add_handler(CommandHandler("analyze",     analyze_cmd))
    app.add_handler(CommandHandler("help",        help_cmd))
    app.add_handler(CommandHandler("withdraw",    lambda u, c: u.message.reply_text(
        "💸 Visit myriad.markets → connect wallet → withdraw.")))

    async def post_init(application):
        scheduler = AsyncIOScheduler(timezone="UTC")
        # BTC scan every hour
        loop = asyncio.get_event_loop()

        def run(coro):
            asyncio.run_coroutine_threadsafe(coro, loop)

        scheduler.add_job(lambda: run(auto_trade(app)), 'interval', minutes=5)
        scheduler.add_job(lambda: run(sniper_scan(app)), 'interval', minutes=1)
        scheduler.add_job(lambda: run(check_reactivation(app)), 'interval', hours=1)
        scheduler.add_job(lambda: run(subscription_warning(app)), 'cron', day=25, hour=9, minute=0)
        scheduler.add_job(lambda: run(subscription_deduct(app)), 'cron', day=28, hour=0, minute=0)
        scheduler.add_job(lambda: run(sports_scan(app)), 'cron', hour=17, minute=45)
        scheduler.add_job(lambda: run(sports_scan(app)), 'cron', hour=19, minute=45)
        scheduler.add_job(lambda: run(sports_scan(app)), 'cron', hour=20, minute=45)
        scheduler.add_job(lambda: run(auto_claim(app)), 'interval', minutes=10)
        scheduler.add_job(lambda: run(daily_report(app)), 'cron', hour=23, minute=0)
        scheduler.start()
        logger.info("Bot started...")

    app.post_init = post_init
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )


if __name__ == "__main__":
    main()
