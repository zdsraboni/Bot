# keyboards/url_shortener.py
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def url_shortener_menu(is_emoji_on: bool):
    """
    Builds the URL Shortener menu with toggle button
    """
    kb = InlineKeyboardMarkup(row_width=1)

    emoji_text = "😀 Emoji Mode: ON" if is_emoji_on else "🔤 Emoji Mode: OFF"

    kb.add(
        InlineKeyboardButton(
            emoji_text,
            callback_data="toggle_emoji_mode"
        ),
        InlineKeyboardButton(
            "🔗 Send URL",
            callback_data="ask_for_url"
        ),
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="tools"
        )
    )

    text = (
        "🔗 <b>URL Shortener</b>\n\n"
        f"Emoji Mode is currently: <b>{'ON' if is_emoji_on else 'OFF'}</b>\n"
        "Send a URL to generate short link & QR code."
    )

    return text, kb
