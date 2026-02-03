# handlers/tools/url_shorten/core.py

import requests
import json
import re
import os
import uuid
from io import BytesIO
from telebot import types
from PIL import Image

# Utils থেকে ইম্পোর্ট
from handlers.tools.url_shorten.qr_utils import (
    load_colors, add_new_color, generate_palette_page, 
    make_qr, generate_gradient_palette_page, load_gradients, add_new_gradient
)

# -------------------------------
# CONFIGURATION & DATA FILES
# -------------------------------
TEXT_ENDPOINT = "https://spoo.me/"
EMOJI_ENDPOINT = "https://spoo.me/emoji"

GLOBAL_THEMES_FILE = "data/themes_global.json"
USER_THEMES_FILE = "data/themes_user.json"

QR_STYLES = ['square', 'round', 'diamond', 'vertical', 'horizontal', 'rounded', 'star']
GRADIENT_LIST = [None, 'sunset', 'ocean', 'forest', 'purple_love', 'fire', 'sky', 'royal']

# গ্লোবাল স্টেট
user_state_url = {}

# -------------------------------
# 1. DATA MANAGEMENT (JSON)
# -------------------------------
def load_json(path, default_val):
    if not os.path.exists(path):
        if not os.path.exists('data'): os.makedirs('data')
        with open(path, 'w') as f: json.dump(default_val, f)
        return default_val
    try:
        with open(path, 'r') as f: return json.load(f)
    except: return default_val

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=4)

def get_global_themes(): return load_json(GLOBAL_THEMES_FILE, [])
def add_global_theme(theme):
    data = get_global_themes(); data.insert(0, theme); save_json(GLOBAL_THEMES_FILE, data)

def get_user_themes(cid): 
    return load_json(USER_THEMES_FILE, {}).get(str(cid), [])

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
    if cid not in user_state_url:
        user_state_url[cid] = {
            'qr': True, 'emoji': False, 'color': 'black', 'style': 'square', 
            'logo': None, 'bg_image': None,
            'action': None, 'page': 0, 'gradient': None, 'bg_color': 'white'
        }

def get_dashboard_menu(cid):
    init_user(cid); s = user_state_url[cid]
    mk = types.InlineKeyboardMarkup(row_width=2)
    
    mk.add(
        types.InlineKeyboardButton(f"Emoji: {'ON' if s['emoji'] else 'OFF'}", callback_data="url_set_emoji"),
        types.InlineKeyboardButton(f"QR Mode: {'ON' if s['qr'] else 'OFF'}", callback_data="url_set_qr")
    )
    
    if s['qr']:
        if not s['gradient']:
            col_btn = types.InlineKeyboardButton(f"🎨 Color: {s['color'].title()}", callback_data="url_menu_color")
        else:
            col_btn = types.InlineKeyboardButton(f"🎨 Color: Locked 🔒", callback_data="url_unlock_color")

        mk.add(col_btn, types.InlineKeyboardButton(f"💠 {s['style'].title()}", callback_data="url_tog_style"))
        
        grad_display = s['gradient'].title() if s['gradient'] else "None (Solid)"
        mk.add(types.InlineKeyboardButton(f"🌈 Gradient: {grad_display}", callback_data="url_menu_grad"))
        
        mk.add(
            types.InlineKeyboardButton(f"🎨 FG: {s['color'].title()}", callback_data="url_menu_color"),
            types.InlineKeyboardButton(f"🖼 BG: {s['bg_color'].title()}", callback_data="url_menu_bg")
        )

        mk.add(types.InlineKeyboardButton(f"🖼️ Logo: {'Set ✅' if s['logo'] else 'None ❌'}", callback_data="url_up_logo"))
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

def get_gradient_menu(page):
    all_grads = load_gradients()
    grad_keys = list(all_grads.keys())
    items_per_page = 10
    total_pages = (len(grad_keys) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page; end_idx = start_idx + items_per_page
    current_grads = grad_keys[start_idx:end_idx]
    
    mk = types.InlineKeyboardMarkup(row_width=2)
    if page == 0: mk.add(types.InlineKeyboardButton("🚫 None (Solid Color)", callback_data="url_set_grad_None"))
    btns = [types.InlineKeyboardButton(g.title(), callback_data=f"url_set_grad_{g}") for g in current_grads]
    mk.add(*btns)
    
    nav_btns = []
    if page > 0: nav_btns.append(types.InlineKeyboardButton("⬅️ Prev", callback_data=f"url_grad_pg_{page-1}"))
    nav_btns.append(types.InlineKeyboardButton(f"📄 {page + 1}/{max(1, total_pages)}", callback_data="ignore"))
    if page < total_pages - 1: nav_btns.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"url_grad_pg_{page+1}"))
    mk.row(*nav_btns)
    
    mk.add(types.InlineKeyboardButton("➕ Add New Gradient", callback_data="url_add_grad"))
    mk.add(types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="url_home"))
    return mk

def get_theme_list_menu(themes, page, prefix, allow_create=False):
    mk = types.InlineKeyboardMarkup(row_width=1)
    items_per_page = 5
    total_pages = (len(themes) + items_per_page - 1) // items_per_page
    start = page * items_per_page; end = start + items_per_page
    chunk = themes[start:end]
    
    if allow_create: mk.add(types.InlineKeyboardButton("✨ Create Premium Theme", callback_data="thm_create_new"))
    
    for t in chunk:
        s = t['settings']
        icon = "🌈" if s.get('gradient') else "🎨"
        display_text = f"{icon} {t['name']} [{s['style'].title()}]"
        mk.add(types.InlineKeyboardButton(display_text, callback_data=f"{prefix}_view_{t['id']}"))
    
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
        except: bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")
    else: bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")

# -------------------------------
# 3. CORE LOGIC
# -------------------------------
def process_url(bot, message):
    cid = message.chat.id
    url = message.text.strip()
    init_user(cid); s = user_state_url[cid]
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
                    qr_img = make_qr(short, s['style'], s['color'], s['logo'], 
                                     gradient_name=s['gradient'], bg_color_name=s['bg_color'], bg_image_data=s['bg_image'])
                    if qr_img:
                        bot.delete_message(cid, msg.message_id)
                        bot.send_photo(cid, qr_img, caption=text, parse_mode="Markdown", reply_markup=get_dashboard_menu(cid))
                    else: bot.edit_message_text(text, cid, msg.message_id, parse_mode="Markdown", reply_markup=get_dashboard_menu(cid))
                else: bot.edit_message_text(text, cid, msg.message_id, parse_mode="Markdown", reply_markup=get_dashboard_menu(cid))
            else:
                err = r.json().get('message', 'API Error'); bot.edit_message_text(f"❌ Failed: {err}", cid, msg.message_id)
        else: bot.edit_message_text(f"❌ Server Error: {r.status_code}", cid, msg.message_id)
    except Exception as e: bot.edit_message_text(f"❌ Error: {str(e)[:50]}", cid, msg.message_id)

# -------------------------------
# 4. HANDLERS REGISTER
# -------------------------------
def register_url_handlers(bot):

    # --- ১. ফটো হ্যান্ডলার (Strict Filtered) ---
    # এটি শুধু লোগো বা ব্যাকগ্রাউন্ড আপলোডের সময় কাজ করবে, ওয়াটারমার্কের ফটো খাবে না।
    @bot.message_handler(content_types=['photo'], func=lambda m: user_state_url.get(m.chat.id, {}).get('action') in ['waiting_bg_img', 'waiting_logo'])
    def handle_url_tool_photos(m):
        cid = m.chat.id; init_user(cid); action = user_state_url[cid].get('action')
        try:
            file_info = bot.get_file(m.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            if action == 'waiting_bg_img':
                user_state_url[cid]['bg_image'] = downloaded_file
                msg_txt = "✅ **Background Image successfully set!**"
            else:
                user_state_url[cid]['logo'] = downloaded_file
                msg_txt = "✅ **Logo successfully set!**"
            user_state_url[cid]['action'] = None
            bot.reply_to(m, msg_txt, reply_markup=get_dashboard_menu(cid), parse_mode="Markdown")
        except: bot.reply_to(m, "❌ Error saving image.")

    # --- ২. টেক্সট ইনপুট হ্যান্ডলার (Strict Filtered) ---
    # কালার, গ্রেডিয়েন্ট বা থিমের নাম ইনপুট নেয়ার জন্য
    @bot.message_handler(func=lambda m: user_state_url.get(m.chat.id, {}).get('action') in ['waiting_grad_input', 'waiting_theme_name', 'waiting_color_input'])
    def handle_url_tool_text_inputs(m):
        cid = m.chat.id; init_user(cid); action = user_state_url[cid].get('action'); text = m.text.strip()
        
        if action == 'waiting_grad_input':
            added = []
            for line in text.split('\n'):
                match = re.search(r'^([a-zA-Z0-9_ ]+?)\s+(#?[0-9a-fA-F]{6})\s+(#?[0-9a-fA-F]{6})$', line.strip())
                if match: add_new_gradient(match.group(1).strip(), match.group(2), match.group(3)); added.append(match.group(1).title())
            user_state_url[cid]['action'] = None
            bot.reply_to(m, f"✅ Added: {', '.join(added)}" if added else "❌ Wrong Format!", reply_markup=get_dashboard_menu(cid))

        elif action == 'waiting_theme_name':
            import datetime
            name = text[:20]; s = user_state_url[cid]
            new_theme = {"id": str(uuid.uuid4())[:8], "name": name, "author": m.from_user.first_name, "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "uses": 0, "settings": {"color": s['color'], "bg_color": s['bg_color'], "style": s['style'], "gradient": s.get('gradient'), "logo_enabled": bool(s['logo'])}}
            add_user_theme(cid, new_theme); user_state_url[cid]['action'] = None
            bot.reply_to(m, f"✅ Theme **{name}** saved!", reply_markup=get_dashboard_menu(cid))

        elif action == 'waiting_color_input':
            added = []
            for line in text.split('\n'):
                match = re.search(r'^([a-zA-Z0-9_ ]+?)\s+(#?[0-9a-fA-F]{6})$', line.strip())
                if match: add_new_color(match.group(1), match.group(2)); added.append(match.group(1))
            user_state_url[cid]['action'] = None
            bot.reply_to(m, f"✅ Added {len(added)} colors!", reply_markup=get_dashboard_menu(cid))

    # --- ৩. মেইন লিঙ্ক হ্যান্ডলার (Strictly for Links) ---
    @bot.message_handler(regexp=r"^https?://", func=lambda m: m.chat.type == "private")
    def handle_link_private(m): process_url(bot, m)

    # --- ৪. কলব্যাক হ্যান্ডলারস ---
    def show_color_page(cid, page, message_id=None, is_edit=False):
        img_bio = generate_palette_page(page); markup = get_color_menu(page)
        if img_bio:
            if is_edit and message_id:
                try: bot.edit_message_media(media=types.InputMediaPhoto(img_bio, caption="🎨 **Select a Color:**"), chat_id=cid, message_id=message_id, reply_markup=markup)
                except: bot.send_photo(cid, img_bio, caption="🎨 **Select a Color:**", reply_markup=markup)
            else: bot.send_photo(cid, img_bio, caption="🎨 **Select a Color:**", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("url_"))
    def handle_url_callbacks(c):
        cid = c.message.chat.id; init_user(cid); data = c.data
        
        if data == "url_home": open_url_tool(bot, c.message, is_edit=True)
        elif data == "url_set_emoji": 
            user_state_url[cid]['emoji'] = not user_state_url[cid]['emoji']
            bot.edit_message_reply_markup(cid, c.message.message_id, reply_markup=get_dashboard_menu(cid))
        elif data == "url_set_qr": 
            user_state_url[cid]['qr'] = not user_state_url[cid]['qr']
            bot.edit_message_reply_markup(cid, c.message.message_id, reply_markup=get_dashboard_menu(cid))
        elif data == "url_tog_style": 
            user_state_url[cid]['style'] = QR_STYLES[(QR_STYLES.index(user_state_url[cid]['style'])+1)%len(QR_STYLES)]
            bot.edit_message_reply_markup(cid, c.message.message_id, reply_markup=get_dashboard_menu(cid))
        elif data == "url_menu_color": 
            user_state_url[cid]['page'] = 0; show_color_page(cid, 0, c.message.message_id, True)
        elif data == "url_unlock_color":
            user_state_url[cid]['gradient'] = None; show_color_page(cid, 0, c.message.message_id, True)
        elif data == "url_menu_bg":
            img_bio = generate_palette_page(0); mk = get_color_menu(0)
            for row in mk.keyboard:
                for btn in row:
                    if btn.callback_data.startswith("url_col_"): btn.callback_data = btn.callback_data.replace("url_col_", "url_setbg_")
            mk.row(types.InlineKeyboardButton("📷 Upload Background Image", callback_data="url_up_bg_img"))
            if user_state_url[cid]['bg_image']: mk.row(types.InlineKeyboardButton("🗑️ Remove BG Image", callback_data="url_rm_bg_img"))
            bot.edit_message_media(media=types.InputMediaPhoto(img_bio, caption="🖼 **Background Settings:**"), chat_id=cid, message_id=c.message.message_id, reply_markup=mk)
        elif data == "url_up_bg_img":
            user_state_url[cid]['action'] = 'waiting_bg_img'; bot.delete_message(cid, c.message.message_id)
            bot.send_message(cid, "🖼️ **Please send the photo now.**")
        elif data == "url_rm_bg_img":
            user_state_url[cid]['bg_image'] = None; bot.answer_callback_query(c.id, "🗑️ BG Removed"); open_url_tool(bot, c.message, True)
        elif data.startswith("url_setbg_"):
            user_state_url[cid]['bg_color'] = data.split("_")[-1]; open_url_tool(bot, c.message, True)
        elif data == "url_up_logo":
            if user_state_url[cid]['logo']: user_state_url[cid]['logo'] = None; open_url_tool(bot, c.message, True)
            else: user_state_url[cid]['action'] = 'waiting_logo'; bot.send_message(cid, "🖼️ **Send Logo now.**")
        elif data == "url_preview":
            qr_img = make_qr("https://t.me/MissZeba_bot", user_state_url[cid]['style'], user_state_url[cid]['color'], user_state_url[cid]['logo'], user_state_url[cid]['gradient'], user_state_url[cid]['bg_color'], user_state_url[cid]['bg_image'])
            if qr_img:
                bot.delete_message(cid, c.message.message_id)
                bot.send_photo(cid, qr_img, caption="👁️ **Preview**", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Back", callback_data="url_home")), parse_mode="Markdown")
        elif data == "url_menu_grad":
            img_bio = generate_gradient_palette_page(0); mk = get_gradient_menu(0)
            bot.edit_message_media(media=types.InputMediaPhoto(img_bio, caption="🌈 **Select a Gradient Style:**"), chat_id=cid, message_id=c.message.message_id, reply_markup=mk)
        elif data.startswith("url_grad_pg_"):
            pg = int(data.split("_")[-1]); img_bio = generate_gradient_palette_page(pg); mk = get_gradient_menu(pg)
            bot.edit_message_media(media=types.InputMediaPhoto(img_bio, caption="🌈 **Select a Gradient Style:**"), chat_id=cid, message_id=c.message.message_id, reply_markup=mk)
        elif data == "url_add_grad":
            user_state_url[cid]['action'] = 'waiting_grad_input'; bot.delete_message(cid, c.message.message_id)
            bot.send_message(cid, "➕ **Add New Gradient:**\nFormat: `Name #Hex1 #Hex2`", parse_mode="Markdown")
        elif data.startswith("url_set_grad_"):
            val = data.replace("url_set_grad_", ""); user_state_url[cid]['gradient'] = None if val=="None" else val
            open_url_tool(bot, c.message, True)
        elif data.startswith("url_col_"):
            user_state_url[cid]['color'] = data.split("_")[-1]; open_url_tool(bot, c.message, True)
        elif data in ["url_page_prev", "url_page_next"]:
            colors = load_colors(); total = (len(colors)+9)//10; curr = user_state_url[cid].get('page', 0)
            new_pg = max(0, curr-1) if data=="url_page_prev" else min(total-1, curr+1)
            user_state_url[cid]['page'] = new_pg; show_color_page(cid, new_pg, c.message.message_id, True)
        elif data == "url_add_color":
            user_state_url[cid]['action'] = 'waiting_color_input'; bot.delete_message(cid, c.message.message_id)
            bot.send_message(cid, "➕ **Add Colors:**\nFormat: `Name Hex`", parse_mode="Markdown")

    # --- ৫. থিম কলব্যাক হ্যান্ডলারস ---
    @bot.callback_query_handler(func=lambda c: c.data.startswith("thm_") or any(x in c.data for x in ["gthm_", "mthm_"]))
    def handle_theme_callbacks(c):
        cid = c.message.chat.id; init_user(cid); data = c.data
        if data.startswith("thm_browse_"):
            pg = int(data.split("_")[-1]); mk = get_theme_list_menu(get_global_themes(), pg, "gthm")
            bot.edit_message_text("🌐 **Global Theme Gallery:**", cid, c.message.message_id, reply_markup=mk, parse_mode="Markdown")
        elif data.startswith("thm_mine_"):
            pg = int(data.split("_")[-1]); mk = get_theme_list_menu(get_user_themes(cid), pg, "mthm", True)
            bot.edit_message_text("📂 **My Saved Themes:**", cid, c.message.message_id, reply_markup=mk, parse_mode="Markdown")
        elif "_view_" in data:
            tid = data.split("_")[-1]; is_g = data.startswith("gthm")
            theme = next((t for t in (get_global_themes() if is_g else get_user_themes(cid)) if t['id'] == tid), None)
            if theme:
                s = theme['settings']; qr_img = make_qr("https://t.me/MissZeba_bot", s['style'], s['color'], None, s.get('gradient'), s.get('bg_color', 'white'))
                mk = types.InlineKeyboardMarkup()
                if is_g: mk.add(types.InlineKeyboardButton("⭐ Add Favorites", callback_data=f"thm_save_{tid}"), types.InlineKeyboardButton("🔙 Back", callback_data="thm_browse_0"))
                else: mk.add(types.InlineKeyboardButton("🚀 Apply", callback_data=f"thm_apply_{tid}"), types.InlineKeyboardButton("🌍 Publish", callback_data=f"thm_pub_{tid}"), types.InlineKeyboardButton("🗑️ Delete", callback_data=f"thm_del_{tid}"), types.InlineKeyboardButton("🔙 Back", callback_data="thm_mine_0"))
                bot.delete_message(cid, c.message.message_id)
                bot.send_photo(cid, qr_img, caption=f"🎨 **Theme:** {theme['name']}\n👤 **Author:** {theme.get('author','Unknown')}", reply_markup=mk, parse_mode="Markdown")
        elif data.startswith("thm_save_"):
            tid = data.split("_")[-1]; theme = next((t for t in get_global_themes() if t['id'] == tid), None)
            if theme: 
                nt = theme.copy(); nt['id'] = str(uuid.uuid4())[:8]; add_user_theme(cid, nt)
                bot.answer_callback_query(c.id, "✅ Saved!")
        elif data.startswith("thm_apply_"):
            tid = data.split("_")[-1]; all_t = load_json(USER_THEMES_FILE, {})
            if str(cid) in all_t:
                for t in all_t[str(cid)]:
                    if t['id'] == tid:
                        user_state_url[cid].update({'color': t['settings']['color'], 'style': t['settings']['style'], 'gradient': t['settings'].get('gradient')})
                        t['uses'] = t.get('uses', 0) + 1; save_json(USER_THEMES_FILE, all_t)
                        bot.answer_callback_query(c.id, "✅ Applied!"); open_url_tool(bot, c.message, False); return
        elif data.startswith("thm_pub_"):
            tid = data.split("_")[-1]; theme = next((t for t in get_user_themes(cid) if t['id'] == tid), None)
            if theme: pt = theme.copy(); pt['author'] = c.from_user.first_name; add_global_theme(pt); bot.answer_callback_query(c.id, "🌍 Published!")
        elif data.startswith("thm_del_"):
            delete_user_theme(cid, data.split("_")[-1]); bot.answer_callback_query(c.id, "🗑️ Deleted"); open_url_tool(bot, c.message, False)
        elif data == "thm_create_new":
            user_state_url[cid]['action'] = 'waiting_theme_name'; bot.delete_message(cid, c.message.message_id)
            bot.send_message(cid, "📝 **Enter Theme Name:**")

# এই ফাইলটি কপি করে পেস্ট করলে আপনার URL Tool এখন একদম সুরক্ষিতভাবে কাজ করবে।
