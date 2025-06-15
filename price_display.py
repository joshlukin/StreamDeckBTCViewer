import time
import requests
from PIL import Image, ImageDraw, ImageFont
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
import os
import sys

os.environ["HIDAPI_FORCE_BACKEND"] = "pywinusb"

# -----------------------------
# CONFIGURATION
# -----------------------------
REFRESH_INTERVAL = 30  # seconds between API refreshes
FONT_PATH = "DejaVuSansCondensed.ttf"
KEY_WIDTH, KEY_HEIGHT = 72, 72

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# -----------------------------
# FETCH BITCOIN PRICE
# -----------------------------
def fetch_price_and_trend():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
        headers = {"accept": "application/json"}
        response = requests.get(url, headers=headers)

        if response.status_code == 429:
            print("🚫 Rate limit hit. Backing off for 60 seconds.")
            time.sleep(60)
            return None, 0, 0

        data = response.json()
        btc = data.get("bitcoin", {})
        price = btc.get("usd")
        change_24h = btc.get("usd_24h_change")

        if price is None or change_24h is None:
            print("❌ Unexpected API response:", data)
            return None, 0, 0

        trend = 1 if change_24h > 0 else -1 if change_24h < 0 else 0
        return price, trend, change_24h

    except Exception as e:
        print("❌ Error fetching price:", e)
        return None, 0, 0

def create_tile_image(text, color, font_path, font_size, key_width, key_height, y_offset=0):
    img = Image.new("RGB", (key_width, key_height), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(resource_path(font_path), font_size)

    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    x = (key_width - text_width) // 2
    y = (key_height - text_height) // 2 - y_offset
    draw.text((x, y), text, fill=color, font=font)
    return img

def create_price_images(price, trend, percent_change):
    price_str = f"{price:,.2f}"
    arrow = "▲" if trend > 0 else "▼" if trend < 0 else "-"

    integer_part, decimal_part = price_str.split(".")
    integer_digits = integer_part.replace(",", "")

    tile1_text = f"${integer_digits[0]}"
    comma_index = integer_part.find(",")
    if comma_index != -1:
        tile2_text = integer_part[1:comma_index + 1]
    else:
        tile2_text = integer_part[1:] + ","

    tile3_start_index = 1 + len(tile2_text.replace(",", ""))
    tile3_digits = integer_digits[tile3_start_index:]
    tile3_text = tile3_digits
    tile4_text = "." + decimal_part
    tile5_text = f"{percent_change:+.2f}%"
    tile6_text = arrow

    font_sizes = [42, 42, 37, 39, 20, 48]
    color = (0, 255, 0) if trend > 0 else (255, 0, 0) if trend < 0 else (255, 255, 255)

    tile_texts = [tile1_text, tile2_text, tile3_text, tile4_text, tile5_text, tile6_text]
    images = []

    y_offset_for_price_and_arrow = 6

    for i, text in enumerate(tile_texts):
        if i in [0, 1, 2, 3, 5]:
            img = create_tile_image(text, color, FONT_PATH, font_sizes[i], KEY_WIDTH, KEY_HEIGHT, y_offset=y_offset_for_price_and_arrow)
        else:
            img = create_tile_image(text, color, FONT_PATH, font_sizes[i], KEY_WIDTH, KEY_HEIGHT)
        images.append(img)

    return images

def push_to_streamdeck_tile_images(deck, tile_images):
    key_map = [5, 6, 7, 8, 4, 9]

    for i, img in enumerate(tile_images):
        key_index = key_map[i]
        key_img = PILHelper.to_native_format(deck, img)
        deck.set_key_image(key_index, key_img)

def update_timer(deck, seconds_left):
    font = ImageFont.truetype(resource_path(FONT_PATH), 20)
    img = Image.new("RGB", (KEY_WIDTH, KEY_HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    text = f"{seconds_left}s"

    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    x = (KEY_WIDTH - text_width) // 2
    y = (KEY_HEIGHT - text_height) // 2

    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    key_img = PILHelper.to_native_format(deck, img)
    deck.set_key_image(10, key_img)

def fill_unused_keys(deck, used_keys):
    blank_img = Image.new("RGB", (KEY_WIDTH, KEY_HEIGHT), (0, 0, 0))
    blank_native = PILHelper.to_native_format(deck, blank_img)

    for key in range(deck.key_count()):
        if key not in used_keys:
            deck.set_key_image(key, blank_native)

def main():
    decks = DeviceManager().enumerate()
    if not decks:
        print("❌ No Stream Decks detected.")
        return

    deck = decks[0]
    deck.open()

    while True:
        price, trend, percent_change = fetch_price_and_trend()
        if price is None:
            time.sleep(REFRESH_INTERVAL)
            continue

        print(f"💰 BTC: ${price:,.2f} | 24h: {percent_change:+.2f}% | Trend: {'▲' if trend > 0 else '▼' if trend < 0 else '-'}")

        tile_images = create_price_images(price, trend, percent_change)
        push_to_streamdeck_tile_images(deck, tile_images)

        used_keys = [4, 5, 6, 7, 8, 9, 10]
        fill_unused_keys(deck, used_keys)

        for i in range(REFRESH_INTERVAL, 0, -1):
            update_timer(deck, i)
            time.sleep(1)

    deck.close()

if __name__ == "__main__":
    main()
