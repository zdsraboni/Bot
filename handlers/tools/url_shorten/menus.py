from telebot import types

def get_dashboard_menu(s):
    """
    s: user_state[cid] - ইউজারের বর্তমান স্টেট অবজেক্ট
    """
    mk = types.InlineKeyboardMarkup(row_width=2)
    
    # Emoji এবং QR মোড বাটন
    mk.add(
        types.InlineKeyboardButton(f"Emoji: {'ON' if s['emoji'] else 'OFF'}", callback_data="url_set_emoji"),
        types.InlineKeyboardButton(f"QR Mode: {'ON' if s['qr'] else 'OFF'}", callback_data="url_set_qr")
    )
    
    # QR মোড ON থাকলে Color এবং Style বাটন দেখাবে
    if s['qr']:
        mk.add(
            types.InlineKeyboardButton(f"🎨 Color: {s['color'].title()}", callback_data="url_menu_color"),
            types.InlineKeyboardButton(f"💠 {s['style'].title()}", callback_data="url_tog_style")
        )
    
    mk.add(types.InlineKeyboardButton(f"🖼️ Logo: {'Set ✅' if s['logo'] else 'None ❌'}", callback_data="url_up_logo"))

    # Preview & Marketplace Buttons
    mk.add(types.InlineKeyboardButton("👁️ Preview Design", callback_data="url_preview"))
    mk.row(
        types.InlineKeyboardButton("🌐 Browse Themes", callback_data="thm_browse_0"),
        types.InlineKeyboardButton("📂 My Themes", callback_data="thm_mine_0")
    )
    mk.add(types.InlineKeyboardButton("🔙 Back to Tools", callback_data="back_to_tools"))
    
    return mk
