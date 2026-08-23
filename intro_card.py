"""
رسم بطاقة "Reddit Intro Card" بدقة - نسخة مطابقة لمنطق render_engine.js الأصلي
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import arabic_reshaper
from bidi.algorithm import get_display
import requests
import io
import math

WIDTH, HEIGHT = 1080, 1920

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def fix_arabic(text):
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), fix_arabic(test), font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_circle_avatar(base_img, avatar_url, cx, cy, r):
    try:
        resp = requests.get(avatar_url, timeout=10)
        avatar = Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception:
        avatar = Image.new("RGBA", (r * 2, r * 2), (226, 226, 226, 255))

    size = r * 2
    avatar = avatar.resize((size, size))
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, size, size), fill=255)
    base_img.paste(avatar, (int(cx - r), int(cy - r)), mask)


def draw_heart_icon(draw, cx, cy, size, color):
    r = size / 4
    draw.ellipse((cx - r * 2, cy - r, cx, cy + r), fill=color)
    draw.ellipse((cx, cy - r, cx + r * 2, cy + r), fill=color)
    draw.polygon([(cx - r * 2, cy), (cx + r * 2, cy), (cx, cy + r * 2.2)], fill=color)


def draw_comment_icon(draw, cx, cy, size, color):
    r = size / 2
    draw.rounded_rectangle((cx - r, cy - r * 0.8, cx + r, cy + r * 0.6), radius=r * 0.3, outline=color, width=3)
    draw.polygon([(cx - r * 0.3, cy + r * 0.5), (cx - r * 0.6, cy + r * 1.1), (cx + r * 0.1, cy + r * 0.6)], fill=color)


def generate_intro_card(config, output_path):
    """
    config = {
      "theme": "light" | "dark",
      "is_rtl": bool,
      "avatar_url": str,
      "username": str,
      "post_text": str,
    }
    """
    is_dark = config.get("theme") == "dark"
    is_rtl = config.get("is_rtl", True)

    colors = {
        "bg": "#1a1a1b" if is_dark else "#ffffff",
        "border": "#343536" if is_dark else "#cccccc",
        "text": "#d7dadc" if is_dark else "#1c1c1c",
        "sub": "#818384" if is_dark else "#787c7e",
        "pill": "#272729" if is_dark else "#f6f7f8",
    }

    card_w = int(WIDTH * 0.88)
    card_x = (WIDTH - card_w) // 2
    padding = 40
    avatar_r = 38

    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    font_username = ImageFont.truetype(FONT_BOLD, 32)
    font_post = ImageFont.truetype(FONT_REGULAR, 34)
    font_pill = ImageFont.truetype(FONT_BOLD, 26)

    post_text = fix_arabic(config.get("post_text", "")) if is_rtl else config.get("post_text", "")
    lines_raw = wrap_text(draw, config.get("post_text", ""), font_post, card_w - padding * 2)
    line_height = 46

    avatar_bottom_edge = padding + avatar_r * 2
    header_gap = 26
    top_row_h = avatar_bottom_edge + header_gap
    post_text_h = len(lines_raw) * line_height + 20
    actions_h = 80
    card_h = top_row_h + post_text_h + actions_h + padding * 2
    card_y = (HEIGHT - card_h) // 2

    shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    rounded_rect(shadow_draw, (card_x, card_y + 10, card_x + card_w, card_y + card_h + 10), 26, fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(15))
    canvas = Image.alpha_composite(canvas, shadow)
    draw = ImageDraw.Draw(canvas)

    rounded_rect(draw, (card_x, card_y, card_x + card_w, card_y + card_h), 26, fill=colors["bg"], outline=colors["border"], width=2)

    row_y = card_y + padding + avatar_r
    avatar_cx = card_x + card_w - padding - avatar_r if is_rtl else card_x + padding + avatar_r
    draw_circle_avatar(canvas, config.get("avatar_url", ""), avatar_cx, row_y, avatar_r)
    draw = ImageDraw.Draw(canvas)

    username = fix_arabic(config.get("username", "u/ThrowAwayStory")) if is_rtl else config.get("username", "u/ThrowAwayStory")
    name_x = avatar_cx - avatar_r - 20 if is_rtl else avatar_cx + avatar_r + 20
    anchor = "rm" if is_rtl else "lm"
    draw.text((name_x, row_y), username, font=font_username, fill=colors["text"], anchor=anchor)

    text_x = card_x + card_w - padding if is_rtl else card_x + padding
    text_y = card_y + top_row_h
    for line in lines_raw:
        display_line = fix_arabic(line) if is_rtl else line
        anchor = "ra" if is_rtl else "la"
        draw.text((text_x, text_y), display_line, font=font_post, fill=colors["text"], anchor=anchor)
        text_y += line_height

    act_y = card_y + card_h - padding - 30
    pill_h = 54
    like_w, comment_w, share_w = 130, 110, 130
    share_label = "مشاركة" if is_rtl else "Share"

    if is_rtl:
        x_positions = [card_x + card_w - padding - like_w]
        x_positions.append(x_positions[-1] - 10 - comment_w)
        x_positions.append(10)
    else:
        x_positions = [card_x + padding, card_x + padding + like_w + 10]

    x1 = card_x + padding if not is_rtl else card_x + card_w - padding - like_w
    rounded_rect(draw, (x1, act_y - 27, x1 + like_w, act_y - 27 + pill_h), 27, fill=colors["pill"])
    draw_heart_icon(draw, x1 + 24, act_y, 24, colors["sub"])
    draw.text((x1 + 46, act_y), "2.4K", font=font_pill, fill=colors["sub"], anchor="lm")

    x2 = x1 - 10 - comment_w if is_rtl else x1 + like_w + 10
    rounded_rect(draw, (x2, act_y - 27, x2 + comment_w, act_y - 27 + pill_h), 27, fill=colors["pill"])
    draw_comment_icon(draw, x2 + 24, act_y, 24, colors["sub"])
    draw.text((x2 + 46, act_y), "84", font=font_pill, fill=colors["sub"], anchor="lm")

    canvas.save(output_path, "PNG")
    return output_path
