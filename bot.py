"""
bot.py — BTC Prediction Telegram Bot
Gated platform with AI auto-trading on Myriad Markets
"""

import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
import signal_engine as se
import wallet_manager as wm
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
PLATFORM_FEE   = float(os.getenv("PLATFORM_FEE", "0.1"))
SIGNAL_THRESH  = float(os.getenv("SIGNAL_THRESH", "70.0"))
BET_AMOUNT     = float(os.getenv("BET_AMOUNT", "5.0"))

# Conversation states
ASK_EMAIL, ASK_TX, ASK_BYPASS = range(3)


# ── Helpers ───────────────────────────────────────────────────────────────────
def is_owner(telegram_id: str) -> bool:
    user = db.get_user(telegram_id)
    return user and user["is_owner"] == 1


def is_active(telegram_id: str) -> bool:
    user = db.get_user(telegram_id)
    return user and user["is_active"] == 1


# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    name = update.effective_user.first_name or "Trader"

    db.create_user(uid, name)
    user = db.get_user(uid)

    if user["is_active"]:
        await update.message.reply_text(
            f"👋 Welcome back *{name}*!\n\n"
            f"Your bot is active and trading automatically.\n\n"
            f"Use /help to see all commands.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"👋 Welcome *{name}*!\n\n"
        f"*BTC Prediction Bot* auto-trades BTC UP/DOWN markets on Myriad when AI confidence is above 70%.\n\n"
        f"To get started:\n"
        f"  1️⃣ Enter your Myriad email\n"
        f"  2️⃣ Deposit $5 USDC to your wallet\n"
        f"  3️⃣ Bot starts trading for you\n\n"
        f"Have a bypass code? Type /bypass\n\n"
        f"Enter your *Myriad email* to begin:",
        parse_mode="Markdown"
    )
    return ASK_EMAIL


async def ask_email(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = str(update.effective_user.id)
    email = update.message.text.strip().lower()

    if "@" not in email or "." not in email:
        await update.message.reply_text("❌ Invalid email. Please enter a valid email address:")
        return ASK_EMAIL

    # Check email not already taken by another user
    conn = db.get_conn()
    existing = conn.execute(
        "SELECT telegram_id FROM users WHERE email = ? AND telegram_id != ?",
        (email, uid)
    ).fetchone()
    conn.close()

    if existing:
        await update.message.reply_text("❌ That email is already registered. Use a different one:")
        return ASK_EMAIL

    # Generate wallet for this user
    wallet = wm.generate_wallet()
    db.update_user(uid,
        email          = email,
        wallet_address = wallet["address"],
        wallet_key     = wallet["private_key"]
    )

    await update.message.reply_text(
        f"✅ *Email saved!*\n\n"
        f"🔐 *Your trading wallet has been created:*\n"
        f"`{wallet['address']}`\n\n"
        f"📤 Send exactly *$5.00 USDC* to this address on *Abstract chain*.\n\n"
        f"Once sent, paste the *transaction hash* here to activate your account.",
        parse_mode="Markdown"
    )
    return ASK_TX


async def ask_tx(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    tx_hash = update.message.text.strip()

    if not tx_hash.startswith("0x") or len(tx_hash) < 60:
        await update.message.reply_text(
            "❌ That doesn't look like a valid tx hash.\n"
            "It should start with `0x` and be 66 characters long.\n\n"
            "Please paste the correct transaction hash:",
            parse_mode="Markdown"
        )
        return ASK_TX

    if db.tx_already_used(tx_hash):
        await update.message.reply_text("❌ This transaction has already been used.")
        return ASK_TX

    await update.message.reply_text("⏳ Verifying transaction on-chain...")

    result = wm.verify_tx_payment(tx_hash, OWNER_EVM, MIN_DEPOSIT)

    if not result["valid"]:
        await update.message.reply_text(
            f"❌ *Verification failed*\n{result['error']}\n\n"
            f"Please check and try again:",
            parse_mode="Markdown"
        )
        return ASK_TX

    user = db.get_user(uid)
    db.log_deposit(user["id"], tx_hash, result["amount"])
    db.update_user(uid, is_active=1, balance=result["amount"])

    await update.message.reply_text(
        f"🎉 *Account Activated!*\n\n"
        f"💰 Balance: *${result['amount']:.2f} USDC*\n\n"
        f"Your bot is now live. It will automatically trade BTC UP/DOWN when AI confidence exceeds 70%.\n\n"
        f"Use /help to see all commands.",
        parse_mode="Markdown"
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
        await update.message.reply_text("❌ Bypass code has been fully used.")
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
        await update.message.reply_text("❌ Wrong code. Try again or use /start to pay normally.")
        return ConversationHandler.END

    # Check if this user already used bypass
    conn = db.get_conn()
    already = conn.execute(
        "SELECT id FROM bypass_uses WHERE telegram_id = ?", (uid,)
    ).fetchone()
    conn.close()

    if already:
        await update.message.reply_text("❌ You've already used a bypass code.")
        return ConversationHandler.END

    db.log_bypass_use(uid)
    db.update_user(uid, is_active=1, is_owner=1, balance=999999)

    remaining = BYPASS_MAX - db.count_bypass_uses()
    await update.message.reply_text(
        f"✅ *Owner bypass activated!*\n"
        f"Remaining uses: {remaining}/{BYPASS_MAX}\n\n"
        f"Use /help to see all commands.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ── /balance ──────────────────────────────────────────────────────────────────
async def balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)

    if not user or not is_active(uid):
        await update.message.reply_text("❌ Account not active. Use /start to register.")
        return

    # Refresh on-chain balance
    onchain = wm.get_usdc_balance(user["wallet_address"])

    await update.message.reply_text(
        f"💰 *Your Wallet*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Address  : `{user['wallet_address']}`\n"
        f"Balance  : *${user['balance']:.2f} USDC* (bot tracking)\n"
        f"On-chain : *${onchain:.2f} USDC*\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )


# ── /deposit ──────────────────────────────────────────────────────────────────
async def deposit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)

    if not user or not is_active(uid):
        await update.message.reply_text("❌ Use /start first.")
        return

    await update.message.reply_text(
        f"📥 *Top Up Your Balance*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Send *USDC* on *Abstract chain* to:\n\n"
        f"`{user['wallet_address']}`\n\n"
        f"Minimum: $5 USDC\n"
        f"After sending, use /verify <tx\\_hash> to credit your balance.",
        parse_mode="Markdown"
    )


# ── /verify <tx_hash> ─────────────────────────────────────────────────────────
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
    result = wm.verify_tx_payment(tx_hash, OWNER_EVM, 1.0)

    if not result["valid"]:
        await update.message.reply_text(f"❌ {result['error']}")
        return

    db.log_deposit(user["id"], tx_hash, result["amount"])
    db.add_balance(uid, result["amount"])

    await update.message.reply_text(
        f"✅ *${result['amount']:.2f} USDC credited!*\n"
        f"New balance: *${db.get_user(uid)['balance']:.2f} USDC*",
        parse_mode="Markdown"
    )


# ── /withdraw ─────────────────────────────────────────────────────────────────
async def withdraw(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💸 *Withdrawals*\n\n"
        "To withdraw your funds, visit:\n"
        "👉 https://myriad.markets\n\n"
        "Connect your trading wallet and withdraw directly from the platform.",
        parse_mode="Markdown"
    )


# ── /stats ────────────────────────────────────────────────────────────────────
async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    user = db.get_user(uid)

    if not user or not is_active(uid):
        await update.message.reply_text("❌ Account not active. Use /start.")
        return

    s = db.get_user_stats(user["id"])
    win_rate = round(s["wins"] / s["total_trades"] * 100, 1) if s["total_trades"] else 0

    await update.message.reply_text(
        f"📊 *Your Trading Stats*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Total Trades : {s['total_trades']}\n"
        f"Wins         : {s['wins']} ✅\n"
        f"Losses       : {s['losses']} ❌\n"
        f"Win Rate     : {win_rate}%\n"
        f"Total P&L    : ${s['total_pnl'] or 0:.2f}\n"
        f"Volume       : ${s['total_volume'] or 0:.2f}\n"
        f"Fees Paid    : ${s['total_fees'] or 0:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Balance      : *${user['balance']:.2f} USDC*",
        parse_mode="Markdown"
    )


# ── /signal ───────────────────────────────────────────────────────────────────
async def signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if not is_active(uid):
        await update.message.reply_text("❌ Account not active. Use /start.")
        return

    await update.message.reply_text("⏳ Analyzing BTC...")
    try:
        sig = se.generate_signal()
        await update.message.reply_text(se.format_signal(sig), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Signal error: {e}")


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
        f"👥 Total Users   : {s['total_users']}\n"
        f"✅ Active Users  : {s['active_users']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 Total Trades  : {s['total_trades']}\n"
        f"📊 Total Volume  : ${s['total_volume']:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Today Trades  : {s['today_trades']}\n"
        f"💵 Today Volume  : ${s['today_volume']:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Total Fees    : ${s['total_fees']:.4f}\n"
        f"🏦 Owner Wallet  : `{OWNER_EVM[:16]}...`\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )


# ── /help ─────────────────────────────────────────────────────────────────────
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    owner_section = "\n*Admin*\n  /admin — dashboard\n" if is_owner(uid) else ""

    await update.message.reply_text(
        f"🤖 *BTC Prediction Bot*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Account*\n"
        f"  /start — register / onboard\n"
        f"  /bypass — use owner bypass code\n"
        f"  /balance — check wallet balance\n"
        f"  /deposit — get deposit address\n"
        f"  /verify <tx> — credit a deposit\n"
        f"  /withdraw — withdrawal info\n\n"
        f"*Trading*\n"
        f"  /signal — run AI analysis now\n"
        f"  /stats — your P&L and trade history\n"
        f"{owner_section}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Auto-trading fires when AI confidence > 70%_",
        parse_mode="Markdown"
    )


# ── Auto-trader (scheduler) ───────────────────────────────────────────────────
async def auto_trade(app: Application):
    """Run every hour — trade if confidence > 70%."""
    logger.info("Running auto-trade scan...")

    try:
        sig = se.generate_signal()
    except Exception as e:
        logger.error(f"Signal error: {e}")
        return

    # Broadcast signal to all active users
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
        logger.info(f"Signal below threshold: {sig['confidence']}% — skipping trade")
        return

    logger.info(f"Signal {sig['confidence']}% → trading {sig['direction'].upper()}")

    # Get market
    try:
        market = mc.get_btc_market()
        if not market:
            logger.error("No BTC market found")
            return
        odds = mc.get_market_odds(market)
        outcome = odds["outcomes"].get(sig["direction"])
        if not outcome:
            logger.error("No matching outcome")
            return
    except Exception as e:
        logger.error(f"Market fetch error: {e}")
        return

    # Trade for each active user
    for user in users:
        uid = user["telegram_id"]
        total_cost = BET_AMOUNT + PLATFORM_FEE  # $5 bet + $0.1 fee

        if user["balance"] < total_cost:
            try:
                await app.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"⚠️ *Insufficient balance*\n"
                        f"Need ${total_cost:.2f} — have ${user['balance']:.2f}\n"
                        f"Use /deposit to top up."
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            continue

        try:
            # Deduct fee first
            db.deduct_balance(uid, PLATFORM_FEE)
            db.log_fee(user["id"], PLATFORM_FEE, 0)

            # Place bet
            result  = mc.place_bet(odds["market_id"], outcome["id"], BET_AMOUNT)
            tx_hash = result.get("transactionHash", "pending")
            shares  = round(result.get("shares", 0), 4)
            payout  = round(shares * 1.0, 2)

            # Deduct bet amount
            db.deduct_balance(uid, BET_AMOUNT)

            # Log trade
            db.log_trade(
                user["id"], sig["direction"], BET_AMOUNT,
                sig["confidence"], odds["market_id"], outcome["id"], tx_hash
            )

            await app.bot.send_message(
                chat_id=uid,
                text=(
                    f"✅ *Auto-trade Placed!*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Direction  : BTC {sig['direction'].upper()}\n"
                    f"Confidence : {sig['confidence']}%\n"
                    f"Stake      : ${BET_AMOUNT}\n"
                    f"Fee        : $0.10\n"
                    f"Shares     : {shares}\n"
                    f"Potential  : ~${payout}\n"
                    f"Tx         : `{tx_hash[:20]}...`\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Balance    : ${db.get_user(uid)['balance']:.2f}"
                ),
                parse_mode="Markdown"
            )

        except Exception as e:
            # Refund fee if trade failed
            db.add_balance(uid, PLATFORM_FEE)
            logger.error(f"Trade failed for {uid}: {e}")
            try:
                await app.bot.send_message(
                    chat_id=uid,
                    text=f"⚠️ Auto-trade failed: {str(e)[:100]}"
                )
            except Exception:
                pass


# ── Daily P&L report (23:00 UTC) ──────────────────────────────────────────────
async def daily_report(app: Application):
    logger.info("Sending daily P&L reports...")
    users = db.get_all_active_users()

    for user in users:
        try:
            conn = db.get_conn()
            today = conn.execute("""
                SELECT
                    COUNT(*) as trades,
                    SUM(pnl) as pnl,
                    SUM(amount) as volume,
                    SUM(fee_charged) as fees
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
                    f"Fees paid    : ${today['fees'] or 0:.2f}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Balance      : *${user['balance']:.2f} USDC*"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Daily report error for {user['telegram_id']}: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    db.init_db()

    app = Application.builder().token(TG_TOKEN).build()

    # Onboarding conversation
conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
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
