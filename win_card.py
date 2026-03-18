import io, math, random
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def generate_win_card(username, market_title, outcome, stake, payout, profit, roi, rank=None, bet_type="BTC"):
    W, H = 420, 520
    img  = Image.new("RGB", (W, H), color=(6, 8, 14))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        r = int(6 * (1-t)); g = int(18 * (1-t) * 0.6); b = int(22 * (1-t))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    glow = Image.new("RGB", (W, H), (0,0,0))
    gd   = ImageDraw.Draw(glow)
    cx, cy = W//4, H//2
    for r in range(220, 0, -10):
        v = int(9 * (1 - r/220))
        col = (0, v*5, v*3) if bet_type=="BTC" else (0, v*2, v*6)
        gd.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(45))
    img  = Image.blend(img, glow, 0.85)
    draw = ImageDraw.Draw(img)

    try:
        f_sym  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110)
        f_xl   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        f_lg   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        f_md   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 19)
        f_sm   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
        f_xs   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        f_sym=f_xl=f_lg=f_md=f_sm=f_xs=ImageFont.load_default()

    NEON=(0,255,110); GREEN=(0,210,85); WHITE=(230,238,255)
    GOLD=(255,190,0); GREY=(100,112,138); DIM=(40,52,68)

    sym = "₿" if bet_type == "BTC" else "Ξ"
    sym_color = (0, 180, 80) if bet_type == "BTC" else (60, 130, 220)

    for r in range(90, 20, -18):
        alpha = int(40 * (1 - r/90))
        draw.ellipse([(cx-r, cy-r-30), (cx+r, cy+r-30)], outline=sym_color, width=1)

    bbox = draw.textbbox((0,0), sym, font=f_sym)
    sw = bbox[2]-bbox[0]; sh = bbox[3]-bbox[1]
    for offset in [4, 3, 2, 1]:
        alpha_col = tuple(int(c * 0.3) for c in sym_color)
        draw.text((cx-sw//2+offset, cy-sh//2-30+offset), sym, font=f_sym, fill=alpha_col)
    draw.text((cx-sw//2, cy-sh//2-30), sym, font=f_sym, fill=sym_color)

    asset_name = "BITCOIN" if bet_type == "BTC" else "ETHEREUM"
    draw.text((cx, cy+80), asset_name, font=f_xs, fill=GREY, anchor="mm")
    multiplier = round(payout/stake, 2) if stake > 0 else 1.0
    draw.text((cx, cy+100), f"{multiplier}x", font=f_lg, fill=NEON, anchor="mm")

    draw.line([(W//2, 20), (W//2, H-20)], fill=(20, 30, 44), width=1)

    rx = W//2 + 14
    draw.text((W-12, 16), "TREND PILOT", font=f_xs, fill=GREY, anchor="ra")
    draw.line([(rx, 30), (W-12, 30)], fill=(20, 30, 44), width=1)
    draw.text((rx, 40), f"@{username}", font=f_md, fill=WHITE)
    pair = "BTC/USD" if bet_type == "BTC" else "ETH/USD"
    draw.text((rx, 66), pair, font=f_sm, fill=GREY)

    roi_text = f"+{roi:.2f}%"
    for offset in [3, 2, 1]:
        draw.text((rx+offset, 88+offset), roi_text, font=f_xl, fill=(0, 80, 35))
    draw.text((rx, 88), roi_text, font=f_xl, fill=NEON)

    mkt_short = market_title.replace("Bitcoin candles from ", "").replace("Ethereum candles from ", "")[:24]
    draw.text((rx, 148), f"⏱  {mkt_short}", font=f_xs, fill=GREY)
    draw.line([(rx, 168), (W-12, 168)], fill=(18, 26, 38), width=1)

    draw.text((rx, 178), "Invested", font=f_xs, fill=GREY)
    draw.text((W-12, 178), "Current Gain", font=f_xs, fill=GREY, anchor="ra")
    draw.text((rx, 196), f"${stake:.2f}", font=f_md, fill=WHITE)
    draw.text((W-12, 196), f"${payout:.2f}", font=f_md, fill=NEON, anchor="ra")
    draw.line([(rx, 225), (W-12, 225)], fill=(18, 26, 38), width=1)

    draw.text((rx, 233), "Profit", font=f_xs, fill=GREY)
    draw.text((W-12, 233), "ROI", font=f_xs, fill=GREY, anchor="ra")
    draw.text((rx, 251), f"+${profit:.2f}", font=f_md, fill=NEON)
    draw.text((W-12, 251), f"+{roi:.1f}%", font=f_md, fill=NEON, anchor="ra")
    draw.line([(rx, 280), (W-12, 280)], fill=(18, 26, 38), width=1)

    draw.text((rx, 289), f"✅  {outcome}", font=f_xs, fill=GREEN)
    if rank:
        medals = {1:"🥇",2:"🥈",3:"🥉"}
        m = medals.get(rank,"🏅")
        draw.text((rx, 310), f"{m} Rank #{rank}", font=f_xs, fill=GOLD)

    qx, qy, qs = W-58, H-68, 46
    draw.rectangle([(qx, qy), (qx+qs, qy+qs)], fill=(10,14,22), outline=DIM)
    cells = 5; cs = qs // cells
    random.seed(99)
    for row in range(cells):
        for col in range(cells):
            if random.random() > 0.45:
                draw.rectangle([(qx+2+col*cs, qy+2+row*cs),
                                (qx+2+col*cs+cs-2, qy+2+row*cs+cs-2)], fill=DIM)
    draw.text((qx+qs//2, qy+qs+8), "SCAN", font=f_xs, fill=DIM, anchor="ma")

    draw.text((rx, H-52), f"@{username}", font=f_xs, fill=GREY)
    draw.text((rx, H-36), "t.me/pilotrend_bot", font=f_xs, fill=GREEN)
    draw.rectangle([(0, 0), (W-1, H-1)], outline=(20, 30, 44), width=1)
    draw.rectangle([(0, 0), (W, 2)], fill=NEON)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
