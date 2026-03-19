import io, math, random
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def generate_win_card(username, market_title, outcome, stake, payout, profit, roi, rank=None, bet_type="BTC"):
    W, H = 820, 460
    
    # ── Light/bright background ───────────────────────────────────────────────
    img  = Image.new("RGB", (W, H), color=(245, 250, 245))
    draw = ImageDraw.Draw(img)

    # Subtle grid
    for x in range(0, W, 40):
        draw.line([(x,0),(x,H)], fill=(230,240,230), width=1)
    for y in range(0, H, 40):
        draw.line([(0,y),(W,y)], fill=(230,240,230), width=1)

    # Green glow left
    glow = Image.new("RGB", (W, H), (245,250,245))
    gd   = ImageDraw.Draw(glow)
    for r in range(300, 0, -15):
        v = int(8 * (1 - r/300))
        gd.ellipse([(-80, H//2-r), (-80+r*2, H//2+r)], fill=(200+v, 245, 210+v))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img  = Image.blend(img, glow, 0.6)
    draw = ImageDraw.Draw(img)

    # ── Fonts ─────────────────────────────────────────────────────────────────
    try:
        f110 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 100)
        f52  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
        f32  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        f22  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        f17  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        f14  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    except:
        f110=f52=f32=f22=f17=f14=ImageFont.load_default()

    # Colors — light mode
    GREEN   = (0, 160, 70)
    DKGREEN = (0, 120, 50)
    WHITE   = (255, 255, 255)
    BLACK   = (20, 30, 20)
    GREY    = (100, 115, 100)
    LGREY   = (210, 225, 210)
    PANEL   = (255, 255, 255)
    ORANGE  = (220, 100, 0)
    GOLD    = (180, 130, 0)

    # ── Left accent bar ───────────────────────────────────────────────────────
    draw.rectangle([(0,0),(5,H)], fill=GREEN)
    draw.rectangle([(0,0),(W,3)], fill=GREEN)
    draw.rectangle([(0,H-3),(W,H)], fill=GREEN)

    # ── Asset symbol — left half ──────────────────────────────────────────────
    cx, cy = W//4, H//2
    sym = "₿" if bet_type == "BTC" else "Ξ"
    sym_color = GREEN if bet_type == "BTC" else (0, 100, 200)

    # Light circle behind symbol
    for r in range(100, 0, -10):
        v = int(15 * (1 - r/100))
        draw.ellipse([(cx-r, cy-r-20),(cx+r, cy+r-20)],
                     fill=(200+v, 240, 210+v))

    # Symbol
    bbox = draw.textbbox((0,0), sym, font=f110)
    sw = bbox[2]-bbox[0]; sh = bbox[3]-bbox[1]
    draw.text((cx-sw//2, cy-sh//2-20), sym, font=f110, fill=sym_color)

    asset_name = "BITCOIN" if bet_type == "BTC" else "ETHEREUM"
    draw.text((cx, cy+65), asset_name, font=f14, fill=GREY, anchor="mm")

    # X multiplier — fix: payout/stake
    multiplier = round(payout/stake, 2) if stake > 0 else 1.0
    draw.text((cx, cy+88), f"{multiplier}x", font=f32, fill=DKGREEN, anchor="mm")

    # ── Divider ───────────────────────────────────────────────────────────────
    draw.line([(W//2-10, 20),(W//2-10, H-20)], fill=LGREY, width=1)

    # ── Right panel ───────────────────────────────────────────────────────────
    rx = W//2 + 10

    # Top branding
    draw.text((W-15, 18), "TREND PILOT", font=f14, fill=GREY, anchor="ra")

    # Asset pill
    pill_col = (0, 140, 60) if bet_type == "BTC" else (0, 80, 180)
    draw.rounded_rectangle([(rx, 15),(rx+100, 38)], radius=10, fill=pill_col)
    pill_txt = "₿ BTC" if bet_type == "BTC" else "Ξ ETH"
    draw.text((rx+50, 26), pill_txt, font=f14, fill=WHITE, anchor="mm")

    # Username
    draw.text((rx, 52), f"@{username}", font=f32, fill=BLACK)

    # Market
    mkt = market_title.replace("Bitcoin candles from ","").replace("Ethereum candles from ","")
    mkt = mkt[:35]+"…" if len(mkt)>35 else mkt
    draw.text((rx, 92), f"⏱ {mkt}", font=f14, fill=GREY)

    # Outcome
    draw.rounded_rectangle([(rx,112),(rx+220,136)], radius=5,
                           fill=(220,245,225), outline=GREEN)
    draw.text((rx+8,124), f"✅  {outcome}", font=f14, fill=DKGREEN, anchor="lm")

    # ── ROI hero ─────────────────────────────────────────────────────────────
    roi_text = f"+{roi:.2f}%"
    draw.text((rx, 148), roi_text, font=f52, fill=GREEN)

    # ── Stats grid — FIXED MATH ───────────────────────────────────────────────
    # stake = what user bet, payout = what they receive back, profit = payout - stake
    stats = [
        ("Invested",  f"${stake:.2f}",    BLACK),
        ("Payout",    f"${payout:.2f}",   GREEN),
        ("Profit",    f"+${profit:.2f}",  GREEN),
        ("ROI",       f"+{roi:.1f}%",     ORANGE),
    ]
    sy = 225
    for i,(lbl,val,col) in enumerate(stats):
        row=i//2; col_i=i%2
        sx = rx + col_i*175
        y  = sy + row*72

        draw.rounded_rectangle([(sx,y),(sx+165,y+58)],
                               radius=8, fill=PANEL,
                               outline=LGREY)
        draw.text((sx+10,y+12), lbl, font=f14, fill=GREY)
        draw.text((sx+10,y+32), val, font=f22, fill=col)

    # ── Rank ─────────────────────────────────────────────────────────────────
    if rank:
        medals={1:"🥇",2:"🥈",3:"🥉"}
        m=medals.get(rank,"🏅")
        draw.text((rx, 375), f"{m} Leaderboard Rank #{rank}", font=f17, fill=GOLD)

    # ── Footer ────────────────────────────────────────────────────────────────
    draw.rectangle([(0,H-42),(W,H)], fill=(230,245,233))
    draw.line([(0,H-42),(W,H-42)], fill=LGREY, width=1)
    ts = datetime.utcnow().strftime("%Y-%m-%d  %H:%M UTC")
    draw.text((15,H-25), ts, font=f14, fill=GREY)
    draw.text((W//2,H-25), "AI-Powered · BNB Chain · Myriad Markets",
              font=f14, fill=GREY, anchor="ma")
    draw.text((W-15,H-25), "t.me/pilotrend_bot", font=f14, fill=DKGREEN, anchor="ra")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()

if __name__ == "__main__":
    data = generate_win_card(
        "syke","Bitcoin candles from 01:05 to 01:10 UTC",
        "More Red", 1.0, 1.94, 0.94, 94.0, 1, "BTC"
    )
    with open("/mnt/user-data/outputs/win_card_bright.png","wb") as f:
        f.write(data)
    print("Done")
