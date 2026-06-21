"""Run this once locally to generate PWA icons"""
from PIL import Image, ImageDraw, ImageFont
import os

os.makedirs("frontend/assets", exist_ok=True)

def make_icon(size):
    img  = Image.new("RGB", (size, size), "#1a2e1a")
    draw = ImageDraw.Draw(img)
    # Draw a simple "₹" text icon
    font_size = int(size * 0.55)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()
    text = "₹"
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (size - w) // 2
    y = (size - h) // 2 - int(size * 0.03)
    draw.text((x, y), text, fill="#86efac", font=font)
    img.save(f"frontend/assets/icon-{size}.png")
    print(f"Created icon-{size}.png")

make_icon(192)
make_icon(512)
print("Icons created!")
