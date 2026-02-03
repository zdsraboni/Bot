import os
import traceback
from telebot import types
import uuid 
from io import BytesIO

# --- IMPORTS FROM LOCAL FILES ---
# ⚠️ তোমার প্রোজেক্টে data.py, engine.py, menus.py ফাইলগুলো থাকতে হবে
from .data import get_wm_settings, save_wm_settings
from .engine import apply_watermark_image, apply_watermark_video, generate_font_preview_image
from .menus import *

# 🔥 CRITICAL IMPORT: Auto Clean & Status Msg
try:
    from utils.utils import delete_msg, StatusMsg, is_admin
except ImportError:
    # Fallback to avoid crash
    def delete_msg(bot, m): pass
    class StatusMsg:
        def __init__(self, bot, cid): pass
        def send(self, t): pass
        def done(self): pass
    def is_admin(uid): return False

# Check other tools state
try:
    from handlers.tools.url_shorten.core import user_state_url
except ImportError:
    user_state_url = {}

# -------------------------------
# CONFIGURATION
# -------------------------------
FONTS_DIR = "data/fonts"
MAX_FONT_SIZE = 3 * 1024 * 1024
MAX_MEDIA_SIZE = 20 * 1024 * 1024

if not os.path.exists(FONTS_DIR): os.makedirs(FONTS_DIR)

user_states_watermark = {}
last_menu_ids = {}

def update_wm(cid, k, v): save_wm_settings(cid, k, v)

# --- Helper to Send/Edit Menu Safely ---
def send_menu(bot, cid, txt, mk, mid=None):
    if mid:
        try:
            bot.edit_message_text(txt, cid, mid, reply_markup=mk, parse_mode="Markdown")
            last_menu_ids[cid] = mid
            return
        except: pass
            
    if cid in last_menu_ids:
        try: bot.delete_message(cid, last_menu_ids[cid])
        except: pass
    
    try:
        sent = bot.send_message(cid, txt, reply_markup=mk, parse_mode="Markdown")
        last_menu_ids[cid] = sent.message_id
    except Exception as e:
        print(f"Send Menu Error: {e}")

def refresh_main_menu(bot, cid, mid=None):
    s = get_wm_settings(cid)
    txt = f"🎛️ **Watermark Studio**\n📝 Text: `{s.get('text','Watermark')}`\n🎨 Font: `{s.get('font_name','Default')}`\n\n👇 **Send Photo, Video or GIF to process.**"
    send_menu(bot, cid, txt, get_main_menu(s), mid)

# --- PROCESS MEDIA (Main Logic with Auto Clean) ---
def process_media(bot, m, file_type):
    cid = m.chat.id
    
    # 🧹 Smart Status: "Processing..." message that auto-deletes
    status = StatusMsg(bot, cid)
    status.send(f"⏳ Processing {file_type.title()}... Please wait.")
    
    t_in = None
    t_out = None

    try:
        if file_type == 'photo': file_id = m.photo[-1].file_id
        elif file_type == 'video': file_id = m.video.file_id
        elif file_type == 'gif': file_id = m.animation.file_id

        file_info = bot.get_file(file_id)
        if file_info.file_size > MAX_MEDIA_SIZE:
            status.done() # লোডিং মেসেজ ডিলিট
            bot.send_message(cid, f"⚠️ File too big! Max size: 20MB")
            return

        downloaded = bot.download_file(file_info.file_path)
        ext_in = ".mp4" if file_type == 'video' else (".gif" if file_type == 'gif' else ".jpg")
        
        t_in = f"wm_in_{cid}{ext_in}"
        t_out = f"wm_out_{cid}{ext_in}"
        
        with open(t_in, 'wb') as f: f.write(downloaded)
        
        s = get_wm_settings(cid)
        if file_type == 'photo':
            success = apply_watermark_image(t_in, t_out, s)
        else:
            # ভিডিওর ক্ষেত্রে একটু বেশি সময় লাগতে পারে
            success = apply_watermark_video(t_in, t_out, s, is_gif=(file_type=='gif'))

        if success:
            with open(t_out, 'rb') as f:
                if file_type == 'photo': bot.send_photo(cid, f, caption="✅ Done")
                elif file_type == 'video': bot.send_video(cid, f, caption="✅ Done")
                elif file_type == 'gif': bot.send_animation(cid, f, caption="✅ Done")
        else:
            bot.send_message(cid, "❌ Processing Failed (Engine Error).")
        
        # সফল হলে মেনু রিফ্রেশ করা
        refresh_main_menu(bot, cid)

    except Exception as e:
        bot.send_message(cid, f"❌ Error: {e}")
    
    finally:
        # 🧹 কাজ শেষে লোডিং মেসেজ এবং টেম্প ফাইল ডিলিট
        status.done() 
        if t_in and os.path.exists(t_in): os.remove(t_in)
        if t_out and os.path.exists(t_out): os.remove(t_out)

# =========================================================
# 🎮 MAIN HANDLERS
# =========================================================

def register_watermark_handlers(bot):

    def safe_handle(call, func):
        try:
            bot.answer_callback_query(call.id)
            func()
        except Exception as e:
            traceback.print_exc()

    # --- ১. ইনপুট ফিল্টার ফাংশন ---
    def wm_input_filter(m):
        cid = m.chat.id
        if user_state_url.get(cid, {}).get('action') is not None:
            return False
        return True

    # --- ২. মেইন ইনপুট হ্যান্ডলার (ফটো, ভিডিও, টেক্সট) ---
    @bot.message_handler(content_types=['text', 'photo', 'video', 'animation', 'document'], func=wm_input_filter)
    def handle_wm_inputs(m):
        cid = m.chat.id
        st = user_states_watermark.get(cid)
        
        # 🧹 AUTO CLEAN: ইউজারের ইনপুট মেসেজ সাথে সাথে ডিলিট
        delete_msg(bot, m)
        
        # টেক্সট ইনপুট (সেটিংস পরিবর্তন)
        if m.content_type == 'text':
            if st == "waiting_text":
                update_wm(cid, "text", m.text)
                user_states_watermark[cid] = "waiting_media"
                refresh_main_menu(bot, cid)
            elif st and st.startswith("waiting_col_"):
                update_wm(cid, "text_color" if "text" in st else "bg_color", m.text)
                user_states_watermark[cid] = "waiting_media"
                refresh_main_menu(bot, cid)
            return

        # মিডিয়া ইনপুট (ওয়াটারমার্ক প্রয়োগ)
        if m.photo: process_media(bot, m, 'photo')
        elif m.video: process_media(bot, m, 'video')
        elif m.animation: process_media(bot, m, 'gif')
        elif m.document and m.document.mime_type and 'video' in m.document.mime_type:
            process_media(bot, m, 'video')

    # --- ৩. কলব্যাক হ্যান্ডলারস (ড্যাশবোর্ড ও সেটিংস) ---
    # এখানে tool_img যোগ করা হয়েছে কারণ callbacks.py থেকে এটি বাদ দেওয়া হয়েছে
    @bot.callback_query_handler(func=lambda c: c.data.startswith("wm_") or c.data == "tool_img")
    def handle_wm_callbacks(c):
        cid, mid = c.message.chat.id, c.message.message_id
        data = c.data

        def action():
            if data == "tool_img" or data == "wm_menu_main":
                user_states_watermark[cid] = "waiting_media"
                refresh_main_menu(bot, cid, mid if data=="wm_menu_main" else None)
            
            elif data == "wm_menu_fonts":
                send_menu(bot, cid, "🔠 **Font Manager**", get_font_menu(get_wm_settings(cid), c.from_user.id, "main"), mid)
            
            elif data.startswith("wm_font_list_"):
                view = data.replace("wm_font_list_", "")
                s = get_wm_settings(cid)
                bot.answer_callback_query(c.id, "⌛ Loading Previews...")
                target_fonts = [f for f in os.listdir(FONTS_DIR) if f.endswith(('.ttf', '.otf'))] if view=="all" else s.get('favorites', [])
                preview_img = generate_font_preview_image(FONTS_DIR, target_fonts)
                markup = get_font_menu(s, c.from_user.id, view)
                if preview_img:
                    try: bot.delete_message(cid, mid)
                    except: pass
                    sent = bot.send_photo(cid, preview_img, caption=f"🌐 **Library Preview**", reply_markup=markup)
                    last_menu_ids[cid] = sent.message_id
                else: send_menu(bot, cid, "📂 No fonts found.", markup, mid)

            elif data.startswith("wm_fset_"):
                fname = data.replace("wm_fset_", "")
                update_wm(cid, "font_name", fname)
                update_wm(cid, "font_path", os.path.join(FONTS_DIR, fname))
                update_wm(cid, "font_custom", True)
                send_menu(bot, cid, "🔠 **Font Manager**", get_font_menu(get_wm_settings(cid), c.from_user.id, "main"), mid)

            elif data == "wm_font_upload":
                user_states_watermark[cid] = "waiting_font"
                bot.send_message(cid, "📤 **Send .ttf/.otf file (Max 3MB):**")

            elif data == "wm_do_preview":
                from PIL import Image
                t_in, t_out = f"p_in_{cid}.jpg", f"p_out_{cid}.jpg"
                Image.new('RGB', (1280, 720), (200, 200, 200)).save(t_in)
                apply_watermark_image(t_in, t_out, get_wm_settings(cid))
                with open(t_out, 'rb') as f: bot.send_photo(cid, f, caption="👁️ Preview")
                os.remove(t_in); os.remove(t_out)
                refresh_main_menu(bot, cid)

            elif data == "wm_toggle_mode":
                curr = get_wm_settings(cid).get('mode', 'text')
                update_wm(cid, "mode", "logo" if curr=="text" else "text")
                refresh_main_menu(bot, cid, mid)

            elif data == "wm_menu_col_target":
                send_menu(bot, cid, "🎨 **Select Target:**", get_color_target_menu(), mid)

            elif data.startswith("wm_col_menu_"):
                target = data.split("_")[-1]
                send_menu(bot, cid, f"🎨 **Pick {target.title()} Color:**", get_color_palette_menu(target), mid)

            elif data.startswith("wm_setcol_"):
                p = data.split("_"); t, v = p[2], p[3]
                if v == "cust":
                    user_states_watermark[cid] = f"waiting_col_{t}"
                    bot.send_message(cid, f"🎨 **Send Hex for {t}:**")
                else:
                    update_wm(cid, "text_color" if t=="text" else "bg_color", v)
                    refresh_main_menu(bot, cid, mid)

            elif data == "wm_set_text":
                user_states_watermark[cid] = "waiting_text"
                bot.send_message(cid, "✍️ **Send Watermark Text:**")

            elif data == "wm_tog_bg":
                curr = get_wm_settings(cid).get('bg_enabled', True)
                update_wm(cid, "bg_enabled", not curr)
                refresh_main_menu(bot, cid, mid)

            elif data == "wm_menu_style":
                send_menu(bot, cid, "✨ **Style & Rotation**", get_style_menu(), mid)

            elif data == "wm_menu_tile":
                send_menu(bot, cid, "💠 **Layout / Position**", get_tile_menu(get_wm_settings(cid)), mid)

        safe_handle(c, action)

    # --- ৪. ফন্ট ফাইল আপলোড হ্যান্ডলার ---
    @bot.message_handler(content_types=['document'], func=lambda m: user_states_watermark.get(m.chat.id) == "waiting_font")
    def handle_font_upload(m):
        # 🧹 Auto Clean
        delete_msg(bot, m)
        
        if not m.document.file_name.lower().endswith(('.ttf', '.otf')):
            return bot.reply_to(m, "⚠️ Please send a .ttf or .otf file.")
        try:
            path = os.path.join(FONTS_DIR, m.document.file_name)
            with open(path, 'wb') as f:
                f.write(bot.download_file(bot.get_file(m.document.file_id).file_path))
            update_wm(m.chat.id, "font_name", m.document.file_name)
            update_wm(m.chat.id, "font_path", path)
            update_wm(m.chat.id, "font_custom", True)
            
            msg = bot.send_message(m.chat.id, f"✅ Font '{m.document.file_name}' uploaded!")
            user_states_watermark[m.chat.id] = "waiting_media"
            refresh_main_menu(bot, m.chat.id)
            
            # ক্লিনআপ মেসেজ (২ সেকেন্ড পর ডিলিট)
            import time
            time.sleep(2)
            delete_msg(bot, msg)
            
        except Exception as e:
            bot.send_message(m.chat.id, f"❌ Upload failed: {e}")
