import requests
from io import BytesIO
from PIL import Image, ImageDraw

# Import the keyboard menu for buttons
from keyboards.main_menu import tool_url_shorten_menu

# -------------------------------
# User state storage
# -------------------------------
# Stores per-user emoji and QR mode preferences
user_state = {}  # {chat_id: {"emoji": True/False, "qr": True/False}}

# -------------------------------
# API Config
# -------------------------------
API_KEY = "spoo_CNvGgskUPW3TA06XayIPntK3KwbJgViCMAzL9A5z184"

EMOJI_ENDPOINT = "https://spoo.me/emoji"
TEXT_ENDPOINT = "https://spoo.me/"  # Regular shortening

# -------------------------------
# QR generator
# -------------------------------
def generate_designer_qr(url):
    import qrcode
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()

    box_size = 10
    size = (len(matrix) + 2*qr.border) * box_size
    img = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(img)

    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                cx = (x + qr.border) * box_size + box_size // 2
                cy = (y + qr.border) * box_size + box_size // 2
                r = box_size // 2
                draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill="purple")

    bio = BytesIO()
    bio.name = "designer_qr.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

# -------------------------------
# URL processing
# -------------------------------
def process_url(bot, message):
    """
    Shorten URL based on emoji mode, optionally generate QR code.
    """
    chat_id = message.chat.id
    url = message.text.strip()
    

    state = user_state.get(chat_id, {"emoji": True, "qr": True})
    emojimode = state.get("emoji", True)
    qrmode = state.get("qr", True)

    # Validate URL
    if not url.startswith("http"):
        bot.send_message(chat_id, "⚠️ Invalid URL. Must start with http/https.")
        return

    # Determine endpoint and payload
    payload = {"url": url}
    if emojimode:
        endpoint = EMOJI_ENDPOINT
        payload["emoji"] = "true"
    else:
        endpoint = TEXT_ENDPOINT

    try:
        headers = {"Accept": "application/json", "apikey": API_KEY}
        response = requests.post(endpoint, data=payload, headers=headers)
        data = response.json()

        if response.status_code == 200 and "short_url" in data:
            short_url = data["short_url"]
            bot.send_message(chat_id, f"✅ Short URL: {short_url}")

            # QR generation only if qrmode is True
            if qrmode:
                qr_bio = generate_designer_qr(url)
                bot.send_photo(chat_id, qr_bio, caption="📷 Designer QR Code")

        else:
            bot.send_message(chat_id, f"❌ Error: {data.get('message', response.text)}")

    except Exception as e:
        bot.send_message(chat_id, f"❌ System Error: {e}")