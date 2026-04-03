#!/usr/bin/env python3
"""Create branded opening and closing slides for FactPay demo video."""

from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1920, 1080
BG_COLOR = (26, 26, 46)  # #1a1a2e — matches video bg
ACCENT = (0, 180, 130)   # Teal accent
WHITE = (255, 255, 255)
GRAY = (180, 180, 190)
LIGHT_GRAY = (140, 140, 155)

FRAMES_DIR = "/opt/autonomous-ai/factpay/demo_frames"

def get_font(size, bold=False):
    """Try to load a decent font, fallback to default."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()

def center_text(draw, text, y, font, fill=WHITE):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)

def create_opening():
    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Accent line at top
    draw.rectangle([(W//2 - 100, 280), (W//2 + 100, 283)], fill=ACCENT)

    # Project name
    title_font = get_font(72, bold=True)
    center_text(draw, "FactPay", 310, title_font, WHITE)

    # Tagline
    tagline_font = get_font(32)
    center_text(draw, "Truth has a price. Pay only for proven answers.", 410, tagline_font, GRAY)

    # Accent line below tagline
    draw.rectangle([(W//2 - 100, 470), (W//2 + 100, 473)], fill=ACCENT)

    # Description
    desc_font = get_font(24)
    center_text(draw, "x402 micropayment protocol  |  OWS wallet policy engine  |  AI-native fact verification", 510, desc_font, LIGHT_GRAY)

    # Track info
    track_font = get_font(20)
    center_text(draw, "OWS Hackathon  \u2022  Track 03: Build a Paid Digital Service", 580, track_font, ACCENT)

    img.save(os.path.join(FRAMES_DIR, "opening_slide.png"), "PNG")
    print("Created opening_slide.png")

def create_closing():
    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Project name
    title_font = get_font(56, bold=True)
    center_text(draw, "FactPay", 300, title_font, WHITE)

    # Tagline
    tagline_font = get_font(28)
    center_text(draw, "A new x402 primitive for the agent economy", 380, tagline_font, ACCENT)

    # Accent line
    draw.rectangle([(W//2 - 80, 430), (W//2 + 80, 433)], fill=ACCENT)

    # Tech stack
    tech_font = get_font(22)
    center_text(draw, "x402  \u2022  OWS CLI v1.25.1  \u2022  MoonPay x402 Skill  \u2022  Base L2  \u2022  USDC", 470, tech_font, GRAY)

    # GitHub link
    link_font = get_font(26)
    center_text(draw, "github.com/marchantdev/factpay", 530, link_font, WHITE)

    # Track
    track_font = get_font(20)
    center_text(draw, "OWS Hackathon Track 03", 590, track_font, LIGHT_GRAY)

    img.save(os.path.join(FRAMES_DIR, "closing_slide.png"), "PNG")
    print("Created closing_slide.png")

if __name__ == "__main__":
    create_opening()
    create_closing()
