from telebot import types
from .data import get_data
from .utils import is_admin

# =========================================================
# 🛠 1. GLOBAL TOOLS CONFIGURATION (ডায়নামিক টুলস লিস্ট)
# =========================================================
# এখানে নতুন কোনো টুল বানালে শুধু তার আইডি এবং নাম যোগ করে দিবেন।
GLOBAL_TOOLS = {
    "shortener": "🔗 URL Shortener",
    "downloader": "📥 Twitter/X Downloader",
    "watermark": "🖼 Watermark Tool",
    "weather": "☁️ Weather Tool",
    "qr_gen": "📱 QR Generator"
}

# =========================================================
# 🎨 2. UI MARKUPS (All Features Included)
# =========================================================

def get_dash_markup(chat_id):
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(
        types.InlineKeyboardButton("⚙️ Settings", callback_data="gm_settings"),
        types.InlineKeyboardButton("🛑 Filters", callback_data="gm_filters")
    )
    mk.add(types.InlineKeyboardButton("🧰 Group Tools (Dynamic)", callback_data="gm_tools"))
    mk.add(types.InlineKeyboardButton("📚 User Guide", callback_data="gm_guide"))
    mk.add(types.InlineKeyboardButton("❌ Close", callback_data="gm_close"))
    return mk

def get_settings_markup(chat_id):
    data = get_data(chat_id)['toggles']
    mk = types.InlineKeyboardMarkup()
    btn_al = types.InlineKeyboardButton(f"{'✅' if data['antilink'] else '❌'} Anti-Link", callback_data="tog_antilink")
    btn_wel = types.InlineKeyboardButton(f"{'✅' if data['welcome'] else '❌'} Welcome", callback_data="tog_welcome")
    btn_svc = types.InlineKeyboardButton(f"{'✅' if data['service'] else '❌'} Service Del", callback_data="tog_service")
    mk.row(btn_al, btn_wel)
    mk.add(btn_svc)
    mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="open_management"))
    return mk

def get_filters_markup(chat_id):
    data = get_data(chat_id)['toggles']
    mk = types.InlineKeyboardMarkup()
    btn_st = types.InlineKeyboardButton(f"{'✅' if data['block_sticker'] else '❌'} Block Sticker", callback_data="tog_block_sticker")
    btn_vc = types.InlineKeyboardButton(f"{'✅' if data['block_voice'] else '❌'} Block Voice", callback_data="tog_block_voice")
    mk.row(btn_st, btn_vc)
    mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="open_management"))
    return mk

# ✅ ১০০% ডায়নামিক টুলস মেনু জেনারেটর
def get_tools_markup(chat_id):
    group_data = get_data(chat_id).get('tools', {})
    mk = types.InlineKeyboardMarkup(row_width=2)
    
    buttons = []
    for key, label in GLOBAL_TOOLS.items():
        is_enabled = group_data.get(key, False)
        status_icon = "✅" if is_enabled else "❌"
        buttons.append(types.InlineKeyboardButton(f"{status_icon} {label}", callback_data=f"tool_tog_{key}"))
    
    mk.add(*buttons) 
    mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="open_management"))
    return mk

# =========================================================
# 🛡️ 3. MAIN DISPATCHER (Exported)
# =========================================================

def handle_group_callbacks(bot, c):
    data = c.data
    chat_id = c.message.chat.id
    user_id = c.from_user.id

    # ১. মেইন ড্যাশবোর্ড ওপেন
    if data == "open_management":
        if c.message.chat.type == 'private':
            bot.answer_callback_query(c.id, "🛡️ এটি শুধু গ্রুপের ভেতরে কাজ করবে।", show_alert=True)
            return
        if is_admin(bot, chat_id, user_id):
            bot.edit_message_text("🛡️ **Group Management Dashboard**", chat_id, c.message.message_id, parse_mode="Markdown", reply_markup=get_dash_markup(chat_id))
        return

    # ২. অ্যাডমিন চেক
    if not is_admin(bot, chat_id, user_id):
        bot.answer_callback_query(c.id, "❌ আপনি এই গ্রুপের অ্যাডমিন নন!", show_alert=True)
        return

    # ৩. সাব-মেনু লজিক
    if data == "gm_settings":
        bot.edit_message_text("⚙️ **General Settings**", chat_id, c.message.message_id, reply_markup=get_settings_markup(chat_id))
    
    elif data == "gm_filters":
        bot.edit_message_text("🛑 **Media Filters**", chat_id, c.message.message_id, reply_markup=get_filters_markup(chat_id))
    
    elif data == "gm_tools":
        bot.edit_message_text("🧰 **Group Tools Control**\nযে টুলসগুলো এই গ্রুপে মেম্বারদের ব্যবহারের অনুমতি দিতে চান সেগুলো সিলেক্ট করুন:", chat_id, c.message.message_id, reply_markup=get_tools_markup(chat_id))
    
    elif data == "gm_guide":
        txt = (
            "📚 **User Guide**\n\n"
            "**Available Tools:**\n"
            "• `/dl <link>` - Download Twitter Media\n"
            "• `/weather <city>` - Get Weather Info\n"
            "• `/short <url>` - URL Shortener\n\n"
            "**Admin Commands:**\n"
            "• `/ban`, `/mute`, `/warn`, `/pin`"
        )
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="open_management"))
        bot.edit_message_text(txt, chat_id, c.message.message_id, parse_mode="Markdown", reply_markup=mk)

    # ৪. সেটিংস ও ফিল্টার টগল লজিক
    elif data.startswith("tog_"):
        key = data.split("tog_")[1]
        db_data = get_data(chat_id)
        if key in db_data['toggles']:
            db_data['toggles'][key] = not db_data['toggles'][key]
            mk = get_filters_markup(chat_id) if key in ['block_sticker', 'block_voice'] else get_settings_markup(chat_id)
            try: bot.edit_message_reply_markup(chat_id, c.message.message_id, reply_markup=mk)
            except: pass

    # ৫. ✅ ডায়নামিক টুলস টগল লজিক
    elif data.startswith("tool_tog_"):
        tool_key = data.replace("tool_tog_", "")
        db_data = get_data(chat_id)
        if 'tools' not in db_data: db_data['tools'] = {}
        
        current_status = db_data['tools'].get(tool_key, False)
        db_data['tools'][tool_key] = not current_status
        
        try:
            bot.edit_message_reply_markup(chat_id, c.message.message_id, reply_markup=get_tools_markup(chat_id))
            status_txt = "এনাবল" if not current_status else "ডিজেবল"
            bot.answer_callback_query(c.id, f"✅ {GLOBAL_TOOLS.get(tool_key)} {status_txt} করা হয়েছে।")
        except: pass

    elif data == "gm_close":
        bot.delete_message(chat_id, c.message.message_id)

def register_callbacks(bot):
    @bot.callback_query_handler(func=lambda c: c.data.startswith(("gm_", "tog_", "tool_tog_", "open_management")))
    def internal_gm_handler(c):
        handle_group_callbacks(bot, c)
