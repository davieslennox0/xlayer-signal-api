"""
win_card.py — Generate winner notification images
Dark theme PNG cards sent when a user wins a bet
"""

import io
import math
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def generate_win_card(
    username: str,
    market_title: str,
    outcome: str,
    stake: float,
    payout: float,
    profit: float,
    roi: float,
    rank: int = None,
    bet_type: str = "BTC"
) -> bytes:
    """
    Generate a dark-themed winner card image.
    Returns PNG bytes.
    """
    if not PIL_AVAILABLE:
        return None

    W, H = 800, 500
    img  = Image.new("RGB", (W, H), color=(8, 8, 20))
    draw = ImageDraw.Draw(img)

    # ── Background effects ────────────────────────────────────────────────────
    # Gradient-like dark overlay
    for y in range(H):
        alpha = int(20 * (1 - y / H))
        draw.line([(0, y), (W, y)], fill=(0, 30, alpha))

    # Grid lines
    for x in range(0, W, 60):
        draw.line([(x, 0), (x, H)], fill=(15, 15, 35), width=1)
    for y in range(0, H, 60):
        draw.line([(0, y), (W, y)], fill=(15, 15, 35), width=1)

    # Glow circle in background
    for r in range(180, 80, -10):
        opacity = int(15 * (1 - r / 180))
        draw.ellipse(
            [(W//2 - r, H//2 - r), (W//2 + r, H//2 + r)],
            outline=(0, opacity * 3, opacity)
        )

    # ── Border ────────────────────────────────────────────────────────────────
    draw.rectangle([(2, 2), (W-3, H-3)], outline=(0, 255, 136), width=2)
    draw.rectangle([(6, 6), (W-7, H-7)], outline=(247, 147, 26), width=1)

    # ── Fonts (use default if custom not available) ───────────────────────────
    try:
        font_large  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_small  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        font_tiny   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except Exception:
        font_large  = ImageFont.load_default()
        font_medium = font_large
        font_small  = font_large
        font_tiny   = font_large

    # ── Header ────────────────────────────────────────────────────────────────
    draw.text((W//2, 35), "🏆 WINNER!", font=font_large,
              fill=(0, 255, 136), anchor="mm")

    # Bet type badge
    badge_color = (247, 147, 26) if bet_type == "BTC" else (0, 120, 255)
    badge_text  = f"{'₿ BTC' if bet_type == 'BTC' else '⚽ SPORTS'} PREDICTION"
    draw.rounded_rectangle([(W//2 - 120, 70), (W//2 + 120, 100)],
                           radius=12, fill=badge_color)
    draw.text((W//2, 85), badge_text, font=font_tiny,
              fill=(0, 0, 0), anchor="mm")

    # ── User ──────────────────────────────────────────────────────────────────
    draw.text((W//2, 130), f"@{username}", font=font_medium,
              fill=(200, 200, 255), anchor="mm")

    # ── Market ────────────────────────────────────────────────────────────────
    market_short = market_title[:45] + "..." if len(market_title) > 45 else market_title
    draw.text((W//2, 168), market_short, font=font_small,
              fill=(150, 150, 200), anchor="mm")

    draw.text((W//2, 198), f"✅ {outcome}", font=font_small,
              fill=(0, 255, 136), anchor="mm")

    # ── Divider ───────────────────────────────────────────────────────────────
    draw.line([(60, 220), (W-60, 220)], fill=(0, 255, 136), width=1)

    # ── Stats grid ───────────────────────────────────────────────────────────
    stats = [
        ("STAKE",   f"${stake:.2f}",   (150, 150, 200)),
        ("PAYOUT",  f"${payout:.2f}",  (0, 255, 136)),
        ("PROFIT",  f"+${profit:.2f}", (0, 255, 136)),
        ("ROI",     f"+{roi:.1f}%",    (247, 147, 26)),
    ]

    col_w = (W - 120) // 4
    for i, (label, value, color) in enumerate(stats):
        x = 60 + col_w * i + col_w // 2

        # Box
        draw.rounded_rectangle(
            [(60 + col_w * i + 8, 235), (60 + col_w * (i+1) - 8, 330)],
            radius=10, fill=(15, 20, 40), outline=(30, 40, 80)
        )

        draw.text((x, 268), value, font=font_medium, fill=color, anchor="mm")
        draw.text((x, 310), label, font=font_tiny, fill=(100, 100, 150), anchor="mm")

    # ── Rank ─────────────────────────────────────────────────────────────────
    if rank:
        rank_text = f"🏅 Leaderboard Rank #{rank}"
        draw.text((W//2, 360), rank_text, font=font_small,
                  fill=(247, 147, 26), anchor="mm")

    # ── Divider ───────────────────────────────────────────────────────────────
    draw.line([(60, 385), (W-60, 385)], fill=(30, 30, 60), width=1)

    # ── Footer ────────────────────────────────────────────────────────────────
    draw.text((W//2, 415), "Trend Pilot — AI Trading Bot",
              font=font_small, fill=(80, 80, 120), anchor="mm")
    draw.text((W//2, 445), "t.me/pilotrend_bot",
              font=font_small, fill=(0, 200, 100), anchor="mm")

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    draw.text((W//2, 475), ts, font=font_tiny, fill=(50, 50, 80), anchor="mm")

    # ── Corner accents ────────────────────────────────────────────────────────
    accent = (0, 255, 136)
    size   = 20
    # Top-left
    draw.line([(15, 15), (15, 15+size)], fill=accent, width=2)
    draw.line([(15, 15), (15+size, 15)], fill=accent, width=2)
    # Top-right
    draw.line([(W-15, 15), (W-15, 15+size)], fill=accent, width=2)
    draw.line([(W-15, 15), (W-15-size, 15)], fill=accent, width=2)
    # Bottom-left
    draw.line([(15, H-15), (15, H-15-size)], fill=accent, width=2)
    draw.line([(15, H-15), (15+size, H-15)], fill=accent, width=2)
    # Bottom-right
    draw.line([(W-15, H-15), (W-15, H-15-size)], fill=accent, width=2)
    draw.line([(W-15, H-15), (W-15-size, H-15)], fill=accent, width=2)

    # ── Export ────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
