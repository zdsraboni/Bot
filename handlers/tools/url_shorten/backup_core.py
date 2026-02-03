import requests
import json
import re
import os
import uuid
from io import BytesIO
from telebot import types
from PIL import Image

# Utils থেকে ইম্পোর্ট
from handlers.tools.url_shorten.qr_utils import load_colors, add_new_color, generate_palette_page, make_qr

# -------------------------------
# CONFIGURATION & DATA FILES
# -------------------------------
TEXT_ENDPOINT = "https://spoo.me/"
EMOJI_ENDPOINT = "https://spoo.me/emoji"

GLOBAL_THEMES_FILE = "data/themes_global.json"
USER_THEMES_FILE = "data/themes_user.json"

QR_STYLES = ['square', 'round', 'diamond', 'vertical', 'horizontal', 'rounded', 'star']

user_state = {}

# -------------------------------
# 1. DATA MANAGEMENT (JSON)
# -------------------------------
def load_json(path, default_val):
    if not os.path.exists(path):
        with open(path, 'w') as f: json.dump(default_val, f)
        return default_val
    try:
        with open(path, 'r') as f: return json.load(f)
    except: return default_val

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=4)

# Global Themes
def get_global_themes(): return load_json(GLOBAL_THEMES_FILE, [])
def add_global_theme(theme):
    data = get_global_themes()
    data.insert(0, theme) # নতুন থিম সবার আগে
    save_json(GLOBAL_THEMES_FILE, data)

# User Themes
def get_user_themes(cid): 
    all_data = load_json(USER_THEMES_FILE, {})
    return all_data.get(str(cid), [])

def add_user_theme(cid, theme):
    all_data = load_json(USER_THEMES_FILE, {})
    if str(cid) not in all_data: all_data[str(cid)] = []
    all_data[str(cid)].insert(0, theme)
    save_json(USER_THEMES_FILE, all_data)

def delete_user_theme(cid, theme_id):
    all_data = load_json(USER_THEMES_FILE, {})
    if str(cid) in all_data:
        all_data[str(cid)] = [t for t in all_data[str(cid)] if t['id'] != theme_id]
        save_json(USER_THEMES_FILE, all_data)

# -------------------------------
# 2. STATE & MENU SYSTEM
# -------------------------------
def init_user(cid):
    if cid not in user_state:
        user_state[cid] = {
            'qr': True, 'emoji': False, 'color': 'black', 'style': 'square', 
            'logo': None, 'action': None, 'page': 0, 'temp_theme': None
        }

def get_dashboard_menu(cid):
    init_user(cid); s = user_state[cid]
    mk = types.InlineKeyboardMarkup(row_width=2)
    
    mk.add(
        types.InlineKeyboardButton(f"Emoji: {'ON' if s['emoji'] else 'OFF'}", callback_data="url_set_emoji"),
        types.InlineKeyboardButton(f"QR Mode: {'ON' if s['qr'] else 'OFF'}", callback_data="url_set_qr")
    )
    
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

def get_color_menu(page):
    colors = load_colors()
    color_keys = list(colors.keys())
    items_per_page = 10
    total_pages = (len(color_keys) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page; end_idx = start_idx + items_per_page
    current_colors = color_keys[start_idx:end_idx]
    
    mk = types.InlineKeyboardMarkup(row_width=3)
    btns = [types.InlineKeyboardButton(name.title(), callback_data=f"url_col_{name}") for name in current_colors]
    mk.add(*btns)
    
    nav_btns = []
    if page > 0: nav_btns.append(types.InlineKeyboardButton("⬅️ Prev", callback_data="url_page_prev"))
    nav_btns.append(types.InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="ignore"))
    if page < total_pages - 1: nav_btns.append(types.InlineKeyboardButton("Next ➡️", callback_data="url_page_next"))
        
    mk.add(*nav_btns)
    mk.add(types.InlineKeyboardButton("➕ Add Color", callback_data="url_add_color"))
    mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="url_home"))
    return mk

# --- MARKETPLACE MENUS ---

def get_theme_list_menu(themes, page, prefix, allow_create=False):
    mk = types.InlineKeyboardMarkup(row_width=1)
    items_per_page = 5
    total_pages = (len(themes) + items_per_page - 1) // items_per_page
    start = page * items_per_page; end = start + items_per_page
    chunk = themes[start:end]

    if allow_create:
        mk.add(types.InlineKeyboardButton("➕ Save Current as New Theme", callback_data="thm_create_new"))

    for t in chunk:
        mk.add(types.InlineKeyboardButton(f"🎨 {t['name']} (by {t.get('author', 'Unknown')})", callback_data=f"{prefix}_view_{t['id']}"))

    # Pagination
    nav = []
    if page > 0: nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"{prefix}_pg_{page-1}"))
    nav.append(types.InlineKeyboardButton(f"📄 {page+1}/{max(1, total_pages)}", callback_data="ignore"))
    if page < total_pages - 1: nav.append(types.InlineKeyboardButton("➡️", callback_data=f"{prefix}_pg_{page+1}"))
    mk.row(*nav)
    
    mk.add(types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="url_home"))
    return mk

def open_url_tool(bot, message, is_edit=False):
    cid = message.chat.id
    init_user(cid)
    text = "🔗 **URL Shortener & QR Studio**\n\nConfigure your style below, then **Send any Link** to process."
    markup = get_dashboard_menu(cid)
    
    if is_edit:
        try:
            if message.content_type == 'photo':
                bot.delete_message(cid, message.message_id)
                bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.edit_message_text(text, cid, message.message_id, reply_markup=markup, parse_mode="Markdown")
        except:
            bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")

# -------------------------------
# 3. CORE LOGIC
# -------------------------------
def process_url(bot, message):
    cid = message.chat.id
    url = message.text.strip()
    init_user(cid); s = user_state[cid]
    msg = bot.reply_to(message, "⏳ **Generating...**", parse_mode="Markdown")

    try:
        target = EMOJI_ENDPOINT if s['emoji'] else TEXT_ENDPOINT
        payload = {'url': url}
        if s['emoji']: payload['emoji'] = "true"
        
        headers = {"content-type": "application/x-www-form-urlencoded", "Accept": "application/json", "User-Agent": "Mozilla/5.0"}
        r = requests.post(target, data=payload, headers=headers, timeout=10)
        
        if r.status_code == 200:
            try: short = r.json().get("short_url")
            except: short = None

            if short:
                disp = url[:100] + "..." if len(url)>100 else url
                text = f"✅ **Link Ready!**\n\n🔗 {disp}\n🚀 `{short}`"

                if s['qr']:
                    qr_img = make_qr(short, s['style'], s['color'], s['logo'])
                    if qr_img:
                        bot.delete_message(cid, msg.message_id)
                        bot.send_photo(cid, qr_img, caption=text, parse_mode="Markdown", reply_markup=get_dashboard_menu(cid))
                    else:
                        bot.edit_message_text(text, cid, msg.message_id, parse_mode="Markdown", reply_markup=get_dashboard_menu(cid))
                else:
                    bot.edit_message_text(text, cid, msg.message_id, parse_mode="Markdown", reply_markup=get_dashboard_menu(cid))
            else:
                err = r.json().get('message', 'API Error')
                bot.edit_message_text(f"❌ Failed: {err}", cid, msg.message_id)
        else:
            bot.edit_message_text(f"❌ Server Error: {r.status_code}", cid, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Error: {str(e)[:50]}", cid, msg.message_id)

# -------------------------------
# 4. HANDLERS REGISTER
# -------------------------------
def register_url_handlers(bot):
    
    # --- HELPER: COLOR MENU ---
    def show_color_page(cid, page, message_id=None, is_edit=False):
        img_bio = generate_palette_page(page)
        markup = get_color_menu(page)
        if img_bio:
            if is_edit and message_id:
                try:
                    media = types.InputMediaPhoto(img_bio, caption="🎨 **Select a Color:**")
                    bot.edit_message_media(media=media, chat_id=cid, message_id=message_id, reply_markup=markup)
                except:
                    try: bot.delete_message(cid, message_id)
                    except: pass
                    bot.send_photo(cid, img_bio, caption="🎨 **Select a Color:**", reply_markup=markup)
            else:
                bot.send_photo(cid, img_bio, caption="🎨 **Select a Color:**", reply_markup=markup)
        else:
            bot.send_message(cid, "❌ No colors found.", reply_markup=markup)

    # --- MARKETPLACE HANDLERS ---
    
    # 1. Browse Global Themes
    @bot.callback_query_handler(func=lambda c: c.data.startswith("thm_browse_"))
    def browse_global(c):
        page = int(c.data.split("_")[-1]) if "browse" in c.data else 0
        themes = get_global_themes()
        mk = get_theme_list_menu(themes, page, "gthm", allow_create=False)
        
        # Edit Text Menu (If photo exists, remove it)
        try:
            if c.message.content_type == 'photo':
                bot.delete_message(c.message.chat.id, c.message.message_id)
                bot.send_message(c.message.chat.id, "🌐 **Global Theme Gallery:**", reply_markup=mk, parse_mode="Markdown")
            else:
                bot.edit_message_text("🌐 **Global Theme Gallery:**", c.message.chat.id, c.message.message_id, reply_markup=mk, parse_mode="Markdown")
        except:
             bot.send_message(c.message.chat.id, "🌐 **Global Theme Gallery:**", reply_markup=mk, parse_mode="Markdown")

    # 2. My Themes
    @bot.callback_query_handler(func=lambda c: c.data.startswith("thm_mine_"))
    def browse_mine(c):
        cid = c.message.chat.id
        page = int(c.data.split("_")[-1]) if "mine" in c.data else 0
        themes = get_user_themes(cid)
        mk = get_theme_list_menu(themes, page, "mthm", allow_create=True)
        
        text = "📂 **My Saved Themes:**\nSelect a theme to Apply or Publish."
        try:
            if c.message.content_type == 'photo':
                bot.delete_message(cid, c.message.message_id)
                bot.send_message(cid, text, reply_markup=mk, parse_mode="Markdown")
            else:
                bot.edit_message_text(text, cid, c.message.message_id, reply_markup=mk, parse_mode="Markdown")
        except:
             bot.send_message(cid, text, reply_markup=mk, parse_mode="Markdown")

    # 3. View Theme Details (Preview)
    @bot.callback_query_handler(func=lambda c: "_view_" in c.data)
    def view_theme(c):
        cid = c.message.chat.id
        theme_id = c.data.split("_")[-1]
        is_global = c.data.startswith("gthm")
        
        # Find theme
        source = get_global_themes() if is_global else get_user_themes(cid)
        theme = next((t for t in source if t['id'] == theme_id), None)
        
        if not theme:
            bot.answer_callback_query(c.id, "❌ Theme not found.")
            return

        # Generate Preview
        s = theme['settings']
        qr_img = make_qr("https://t.me/MissZeba_bot", s['style'], s['color'], None) # Logo not stored in theme for simplicity
        
        if qr_img:
            mk = types.InlineKeyboardMarkup()
            if is_global:
                mk.add(types.InlineKeyboardButton("⬇️ Add to My Themes", callback_data=f"thm_save_{theme_id}"))
                mk.add(types.InlineKeyboardButton("🔙 Back to Gallery", callback_data="thm_browse_0"))
            else:
                mk.add(types.InlineKeyboardButton("✅ Apply Theme", callback_data=f"thm_apply_{theme_id}"))
                mk.row(
                    types.InlineKeyboardButton("🌍 Publish", callback_data=f"thm_pub_{theme_id}"),
                    types.InlineKeyboardButton("🗑️ Delete", callback_data=f"thm_del_{theme_id}")
                )
                mk.add(types.InlineKeyboardButton("🔙 Back to My Themes", callback_data="thm_mine_0"))
            
            caption = f"🎨 **Theme:** {theme['name']}\n👤 **Author:** {theme.get('author','Unknown')}\n\nStyle: `{s['style']}` | Color: `{s['color']}`"
            
            try: bot.delete_message(cid, c.message.message_id)
            except: pass
            bot.send_photo(cid, qr_img, caption=caption, reply_markup=mk, parse_mode="Markdown")

    # 4. Actions: Save, Apply, Delete, Publish
    @bot.callback_query_handler(func=lambda c: c.data.startswith("thm_save_"))
    def save_theme_to_mine(c):
        cid = c.message.chat.id
        theme_id = c.data.split("_")[-1]
        theme = next((t for t in get_global_themes() if t['id'] == theme_id), None)
        if theme:
            # Clone theme with new unique ID for user
            new_theme = theme.copy()
            new_theme['id'] = str(uuid.uuid4())[:8]
            add_user_theme(cid, new_theme)
            bot.answer_callback_query(c.id, "✅ Saved to My Themes!", show_alert=True)
        else:
            bot.answer_callback_query(c.id, "❌ Error saving.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("thm_apply_"))
    def apply_theme(c):
        cid = c.message.chat.id
        theme_id = c.data.split("_")[-1]
        theme = next((t for t in get_user_themes(cid) if t['id'] == theme_id), None)
        if theme:
            s = theme['settings']
            init_user(cid)
            user_state[cid].update({'color': s['color'], 'style': s['style']})
            bot.answer_callback_query(c.id, "✅ Theme Applied!")
            open_url_tool(bot, c.message, is_edit=False) # Back to editor
        else:
            bot.answer_callback_query(c.id, "❌ Error.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("thm_del_"))
    def delete_theme_action(c):
        cid = c.message.chat.id
        theme_id = c.data.split("_")[-1]
        delete_user_theme(cid, theme_id)
        bot.answer_callback_query(c.id, "🗑️ Theme Deleted.")
        # Refresh List
        browse_mine(c)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("thm_pub_"))
    def publish_theme_action(c):
        cid = c.message.chat.id
        theme_id = c.data.split("_")[-1]
        theme = next((t for t in get_user_themes(cid) if t['id'] == theme_id), None)
        if theme:
            # Check if already exists in global (simple check)
            # For now, just duplicate is fine or add as new
            pub_theme = theme.copy()
            pub_theme['author'] = c.from_user.first_name
            add_global_theme(pub_theme)
            bot.answer_callback_query(c.id, "🌍 Published to Global Gallery!", show_alert=True)
        else:
            bot.answer_callback_query(c.id, "❌ Error.")

    # 5. Create New Theme (Save Current)
    @bot.callback_query_handler(func=lambda c: c.data == "thm_create_new")
    def create_new_theme(c):
        cid = c.message.chat.id
        init_user(cid)
        user_state[cid]['action'] = 'waiting_theme_name'
        
        try: bot.delete_message(cid, c.message.message_id)
        except: pass
        bot.send_message(cid, "📝 **Enter a Name for your Theme:**", parse_mode="Markdown")

    @bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get('action') == 'waiting_theme_name')
    def save_theme_name(m):
        cid = m.chat.id
        name = m.text.strip()
        if len(name) > 20: name = name[:20]
        
        s = user_state[cid]
        new_theme = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "author": m.from_user.first_name,
            "settings": {
                "color": s['color'],
                "style": s['style']
            }
        }
        add_user_theme(cid, new_theme)
        user_state[cid]['action'] = None
        bot.reply_to(m, f"✅ Theme **{name}** saved!", reply_markup=get_dashboard_menu(cid))

    # --- EXISTING HANDLERS (UPDATED) ---

    @bot.callback_query_handler(func=lambda c: c.data == "url_preview")
    def show_preview(c):
        cid = c.message.chat.id
        init_user(cid); s = user_state[cid]
        qr_img = make_qr("https://t.me/MissZeba_bot", s['style'], s['color'], s['logo'])
        if qr_img:
            try: bot.delete_message(cid, c.message.message_id)
            except: pass
            back_mk = types.InlineKeyboardMarkup()
            back_mk.add(types.InlineKeyboardButton("🔙 Back to Editor", callback_data="url_home"))
            caption = f"👁️ **Design Preview**\n\n🎨 Color: `{s['color'].title()}`\n💠 Style: `{s['style'].title()}`"
            bot.send_photo(cid, qr_img, caption=caption, reply_markup=back_mk, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data == "url_home")
    def go_home(c):
        open_url_tool(bot, c.message, is_edit=True)

    @bot.callback_query_handler(func=lambda c: c.data in ["url_set_emoji", "url_set_qr", "url_tog_style"])
    def toggles(c):
        cid = c.message.chat.id; init_user(cid)
        if c.data == "url_set_emoji": user_state[cid]['emoji'] = not user_state[cid]['emoji']
        elif c.data == "url_set_qr": user_state[cid]['qr'] = not user_state[cid]['qr']
        elif c.data == "url_tog_style": 
            current = user_state[cid]['style']
            try:
                curr_idx = QR_STYLES.index(current)
                next_idx = (curr_idx + 1) % len(QR_STYLES)
                user_state[cid]['style'] = QR_STYLES[next_idx]
            except: user_state[cid]['style'] = 'square'
        bot.edit_message_reply_markup(cid, c.message.message_id, reply_markup=get_dashboard_menu(cid))

    @bot.callback_query_handler(func=lambda c: c.data == "url_menu_color")
    def col_menu_start(c):
        cid = c.message.chat.id
        init_user(cid); user_state[cid]['page'] = 0
        show_color_page(cid, 0, message_id=c.message.message_id, is_edit=True)

    @bot.callback_query_handler(func=lambda c: c.data in ["url_page_prev", "url_page_next"])
    def handle_pagination(c):
        cid = c.message.chat.id
        init_user(cid)
        colors = load_colors(); total_pages = (len(colors) + 9) // 10
        current = user_state[cid].get('page', 0)
        if c.data == "url_page_prev": new_page = max(0, current - 1)
        elif c.data == "url_page_next": new_page = min(total_pages - 1, current + 1)
        if new_page != current:
            user_state[cid]['page'] = new_page
            show_color_page(cid, new_page, message_id=c.message.message_id, is_edit=True)
        else: bot.answer_callback_query(c.id, "End of list.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("url_col_"))
    def set_col(c):
        cid = c.message.chat.id
        init_user(cid)
        col = c.data.split("_")[-1]
        user_state[cid]['color'] = col
        try: bot.delete_message(cid, c.message.message_id)
        except: pass
        bot.send_message(cid, f"✅ Color set to **{col.title()}**", reply_markup=get_dashboard_menu(cid), parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data == "url_add_color")
    def ask_new_color(c):
        cid = c.message.chat.id
        init_user(cid)
        user_state[cid]['action'] = 'waiting_color_input'
        try: bot.delete_message(cid, c.message.message_id)
        except: pass
        bot.send_message(cid, "➕ **Add Colors:**\n`Name Hex`\nEx: `Lime #00FF00`", parse_mode="Markdown")

    @bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get('action') == 'waiting_color_input')
    def save_new_color(m):
        cid = m.chat.id
        text = m.text.strip()
        added = []
        for line in text.split('\n'):
            line = line.strip(); 
            if not line: continue
            match = re.search(r'^([a-zA-Z0-9_ ]+?)\s+(#?[0-9a-fA-F]{6})$', line)
            if match:
                name, hex_code = match.groups()
                if not hex_code.startswith('#'): hex_code = '#' + hex_code
                add_new_color(name, hex_code)
                added.append(name)
        user_state[cid]['action'] = None
        bot.reply_to(m, f"✅ Added {len(added)} colors!", reply_markup=get_dashboard_menu(cid))

    @bot.callback_query_handler(func=lambda c: c.data == "url_up_logo")
    def logo_h(c):
        cid = c.message.chat.id; init_user(cid)
        if user_state[cid]['logo']:
            user_state[cid]['logo'] = None
            bot.answer_callback_query(c.id, "Removed")
            bot.edit_message_reply_markup(cid, c.message.message_id, reply_markup=get_dashboard_menu(cid))
        else:
            user_state[cid]['action'] = 'waiting_logo'
            bot.send_message(cid, "🖼️ **Send Logo now.**")

    @bot.message_handler(content_types=['photo'], func=lambda m: user_state.get(m.chat.id, {}).get('action') == 'waiting_logo')
    def get_logo(m):
        try:
            data = bot.download_file(bot.get_file(m.photo[-1].file_id).file_path)
            user_state[m.chat.id]['logo'] = data
            user_state[m.chat.id]['action'] = None
            bot.reply_to(m, "✅ Logo Set!", reply_markup=get_dashboard_menu(m.chat.id))
        except: pass

    @bot.message_handler(regexp=r"^https?://", func=lambda m: m.chat.type == "private")
    def handle_link_private(m): process_url(bot, m)
