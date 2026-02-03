import time
import os
import threading
from telebot import types
from concurrent.futures import ThreadPoolExecutor

# =========================================================
# ⚙️ CONFIGURATION & PERFORMANCE FIX
# =========================================================
# আগের Threading এর বদলে Executor ব্যবহার করা হচ্ছে (সার্ভার সেফটি)
executor = ThreadPoolExecutor(max_workers=5)
MAX_WM_SIZE = 20 * 1024 * 1024  # 20 MB Limit

# ডাটা এবং ইউটিলিটি ইমপোর্ট (আপনার প্রজেক্ট স্ট্রাকচার অনুযায়ী)
try:
    from utils.utils import get_data, is_admin
except ImportError:
    # ফলব্যাক (যদি utils ফাইলে সমস্যা থাকে)
    def get_data(chat_id): return {
        'tools': {'watermark': True, 'url_shortener': True, 'weather': True, 'downloader': True}, 
        'texts': {}, 
        'banwords': [], 
        'warns': {}
    }
    def is_admin(bot, chat_id, user_id):
        try:
            return bot.get_chat_member(chat_id, user_id).status in ['administrator', 'creator']
        except: return False

# =========================================================
# 👇 IMPORT AREA (Tools Engines)
# =========================================================

# 1. URL Shortener
URL_SHORTENER_AVAILABLE = False
try:
    from handlers.tools.url_shorten.core import process_url
    URL_SHORTENER_AVAILABLE = True
except ImportError:
    print("⚠️ URL Tool module not found.")

# 2. Watermark Engine
apply_watermark_image = None
apply_watermark_video = None
get_wm_settings = None
try:
    from handlers.tools.watermark.engine import apply_watermark_image, apply_watermark_video
    from handlers.tools.watermark.data import get_wm_settings
except ImportError:
    print("⚠️ Watermark Tool module not found.")


def register_commands(bot):
    
    # ---------------------------------------------
    # 🔥 GHOST MODE HELPER (Safe Auto-Delete)
    # ---------------------------------------------
    def delete_task(chat_id, msg_ids, delay):
        """ব্যাকগ্রাউন্ডে মেসেজ ডিলিট করার টাস্ক"""
        time.sleep(delay)
        for mid in msg_ids:
            try:
                bot.delete_message(chat_id, mid)
            except: pass

    def reply_temp(message, text, delay=5):
        """Sends a reply and auto-deletes it safely using Executor."""
        try:
            sent_msg = bot.reply_to(message, text, parse_mode="Markdown")
            # ✅ ফিক্স: Thread এর বদলে Executor ব্যবহার করা হচ্ছে
            executor.submit(delete_task, message.chat.id, [message.message_id, sent_msg.message_id], delay)
        except Exception as e:
            print(f"Ghost reply error: {e}")

    # =============================================
    # 1. GROUP TOOLS COMMANDS
    # =============================================

    # --- A. WATERMARK TOOL (/wm) ---
    @bot.message_handler(commands=['wm', 'watermark'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_tool_wm(m):
        if apply_watermark_image is None:
            return reply_temp(m, "⚠️ Watermark module missing.")

        # Check Reply
        reply = m.reply_to_message
        if not reply:
            return reply_temp(m, "⚠️ Reply to a Photo/Video/GIF with `/wm`.")

        file_type = None
        if reply.photo: file_type = 'photo'
        elif reply.video: file_type = 'video'
        elif reply.animation: file_type = 'gif'
        else:
            return reply_temp(m, "⚠️ Supported: Photo, Video, GIF.")

        status_msg = bot.reply_to(m, f"⏳ Processing {file_type}...")

        # Background Process
        def process_watermark_task():
            in_path = None
            out_path = None
            try:
                # File ID Get
                if file_type == 'photo': file_id = reply.photo[-1].file_id
                elif file_type == 'video': file_id = reply.video.file_id
                else: file_id = reply.animation.file_id

                # Size Check
                file_info = bot.get_file(file_id)
                if file_info.file_size > MAX_WM_SIZE:
                    bot.edit_message_text("❌ File too large (Max 20MB).", m.chat.id, status_msg.message_id)
                    return

                # Download
                downloaded = bot.download_file(file_info.file_path)
                ext = ".mp4" if file_type == 'video' else (".gif" if file_type == 'gif' else ".jpg")
                in_path = f"temp_{m.chat.id}_{m.message_id}{ext}"
                out_path = f"out_{m.chat.id}_{m.message_id}{ext}"

                with open(in_path, 'wb') as f: f.write(downloaded)

                # Settings
                settings = get_wm_settings(m.chat.id).copy() if get_wm_settings else {'type': 'text', 'text': 'Watermark'}
                
                # Custom Text Override
                parts = m.text.split(maxsplit=1)
                if len(parts) > 1: settings['text'] = parts[1]

                # Process
                success = False
                if file_type == 'photo':
                    success = apply_watermark_image(in_path, out_path, settings)
                else:
                    bot.edit_message_text("🎬 Rendering... Please wait.", m.chat.id, status_msg.message_id)
                    success = apply_watermark_video(in_path, out_path, settings, is_gif=(file_type=='gif'))

                # Upload
                if success and os.path.exists(out_path):
                    with open(out_path, 'rb') as f:
                        if file_type == 'photo': bot.send_photo(m.chat.id, f, reply_to_message_id=reply.message_id)
                        elif file_type == 'video': bot.send_video(m.chat.id, f, reply_to_message_id=reply.message_id)
                        elif file_type == 'gif': bot.send_animation(m.chat.id, f, reply_to_message_id=reply.message_id)
                    bot.delete_message(m.chat.id, status_msg.message_id)
                else:
                    bot.edit_message_text("❌ Processing Failed.", m.chat.id, status_msg.message_id)

            except Exception as e:
                bot.edit_message_text(f"❌ Error: {e}", m.chat.id, status_msg.message_id)
            finally:
                if in_path and os.path.exists(in_path): os.remove(in_path)
                if out_path and os.path.exists(out_path): os.remove(out_path)

        executor.submit(process_watermark_task)

    # --- B. URL SHORTENER (/short) ---
    @bot.message_handler(commands=['short', 'url'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def handle_short_command(message):
        if not URL_SHORTENER_AVAILABLE:
            return reply_temp(message, "⚠️ Tool unavailable.")
        
        target_text = None
        if len(message.text.split()) > 1:
            target_text = message.text.split(maxsplit=1)[1]
        elif message.reply_to_message and message.reply_to_message.text:
            target_text = message.reply_to_message.text
        
        if target_text:
            message.text = target_text
            process_url(bot, message)
        else:
            reply_temp(message, "⚠️ Usage: `/short <link>` or reply to a link.")

    # --- C. DOWNLOADER (Placeholder) ---
    @bot.message_handler(commands=['dl', 'download'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_tool_dl(m):
        data = get_data(m.chat.id)
        # if not data['tools']['downloader']: return # (Optional check)
        
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            reply_temp(m, "🔗 Link required. Example: `/dl <link>`")
            return
        
        bot.reply_to(m, f"🔍 Processing... {parts[1]}") 

    # --- D. WEATHER (Placeholder) ---
    @bot.message_handler(commands=['weather'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_tool_weather(m):
        data = get_data(m.chat.id)
        # if not data['tools']['weather']: return # (Optional check)

        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            reply_temp(m, "🌤 City name required. Example: `/weather Dhaka`")
            return
            
        bot.reply_to(m, f"🌤 Checking weather for {parts[1]}...") 

    # =============================================
    # 2. ADMIN MANAGEMENT COMMANDS
    # =============================================
    
    # Helper for Text Updates
    def update_text_safely(message, key):
        if not is_admin(bot, message.chat.id, message.from_user.id): return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            reply_temp(message, f"⚠️ Usage: `/set{key} <text>`")
            return
        get_data(message.chat.id)['texts'][key] = parts[1].strip()
        reply_temp(message, f"✅ **{key.upper()}** message updated!")

    @bot.message_handler(commands=['rules'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_rules(m):
        rules = get_data(m.chat.id)['texts'].get('rules', "No rules set.")
        bot.reply_to(m, rules, parse_mode="Markdown")

    # --- Ban/Kick/Warn/Mute Handlers ---
    @bot.message_handler(commands=['ban'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_ban(m):
        if not is_admin(bot, m.chat.id, m.from_user.id): return
        if not m.reply_to_message: return reply_temp(m, "⚠️ Reply to a user.")
        
        target = m.reply_to_message.from_user
        if is_admin(bot, m.chat.id, target.id): return reply_temp(m, "⚠️ Cannot ban admin.")

        try:
            bot.ban_chat_member(m.chat.id, target.id)
            reply_temp(m, f"🚫 Banned **{target.first_name}**.", 10)
        except Exception as e: reply_temp(m, f"❌ Error: {e}")

    @bot.message_handler(commands=['unban'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_unban(m):
        if not is_admin(bot, m.chat.id, m.from_user.id): return
        if not m.reply_to_message: return reply_temp(m, "⚠️ Reply to a user.")
        target = m.reply_to_message.from_user
        try:
            bot.unban_chat_member(m.chat.id, target.id, only_if_banned=True)
            reply_temp(m, f"✅ Unbanned **{target.first_name}**.", 10)
        except Exception as e: reply_temp(m, f"❌ Error: {e}")

    @bot.message_handler(commands=['mute'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_mute(m):
        if not is_admin(bot, m.chat.id, m.from_user.id): return
        if not m.reply_to_message: return reply_temp(m, "⚠️ Reply to a user.")
        target = m.reply_to_message.from_user
        try:
            bot.restrict_chat_member(m.chat.id, target.id, can_send_messages=False)
            reply_temp(m, f"🔇 Muted **{target.first_name}**.", 10)
        except Exception as e: reply_temp(m, f"❌ Error: {e}")

    @bot.message_handler(commands=['unmute'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_unmute(m):
        if not is_admin(bot, m.chat.id, m.from_user.id): return
        if not m.reply_to_message: return reply_temp(m, "⚠️ Reply to a user.")
        target = m.reply_to_message.from_user
        try:
            perms = types.ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_polls=True)
            bot.restrict_chat_member(m.chat.id, target.id, permissions=perms)
            reply_temp(m, f"🔊 Unmuted **{target.first_name}**.", 10)
        except Exception as e: reply_temp(m, f"❌ Error: {e}")

    @bot.message_handler(commands=['warn'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_warn(m):
        if not is_admin(bot, m.chat.id, m.from_user.id): return
        if not m.reply_to_message: return reply_temp(m, "⚠️ Reply to a user.")
        target = m.reply_to_message.from_user
        
        # Simple Warn Logic
        data = get_data(m.chat.id)
        uid = target.id
        if uid not in data['warns']: data['warns'][uid] = 0
        data['warns'][uid] += 1
        
        reply_temp(m, f"⚠️ Warned **{target.first_name}** ({data['warns'][uid]}/3).", 10)
        if data['warns'][uid] >= 3:
            try:
                bot.ban_chat_member(m.chat.id, uid)
                reply_temp(m, f"🚫 **{target.first_name}** banned for reaching 3 warnings.")
                del data['warns'][uid]
            except: pass

    @bot.message_handler(commands=['unwarn'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_unwarn(m):
        if not is_admin(bot, m.chat.id, m.from_user.id): return
        if not m.reply_to_message: return reply_temp(m, "⚠️ Reply to a user.")
        
        data = get_data(m.chat.id)
        uid = m.reply_to_message.from_user.id
        if uid in data['warns']:
            del data['warns'][uid]
            reply_temp(m, "✅ Warning reset.")
        else:
            reply_temp(m, "⚠️ No warnings found.")

    # Pin/Unpin
    @bot.message_handler(commands=['pin'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_pin(m):
        if not is_admin(bot, m.chat.id, m.from_user.id): return
        if not m.reply_to_message: return
        try:
            bot.pin_chat_message(m.chat.id, m.reply_to_message.message_id)
            reply_temp(m, "📌 Pinned.")
        except: reply_temp(m, "❌ Failed.")

    @bot.message_handler(commands=['unpin'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_unpin(m):
        if not is_admin(bot, m.chat.id, m.from_user.id): return
        try:
            if m.reply_to_message: bot.unpin_chat_message(m.chat.id, m.reply_to_message.message_id)
            else: bot.unpin_chat_message(m.chat.id)
            reply_temp(m, "📌 Unpinned.")
        except: pass

    # Text Settings
    @bot.message_handler(commands=['setwelcome'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_wel(m): update_text_safely(m, 'welcome')

    @bot.message_handler(commands=['setrules'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_rul(m): update_text_safely(m, 'rules')

    @bot.message_handler(commands=['setban'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_ban(m): update_text_safely(m, 'ban')

    @bot.message_handler(commands=['setmute'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_mute(m): update_text_safely(m, 'mute')
    
    @bot.message_handler(commands=['setunmute'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_unmute(m): update_text_safely(m, 'unmute')

    @bot.message_handler(commands=['setwarn'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_warn(m): update_text_safely(m, 'warn')

    # Ban Words Management
    @bot.message_handler(commands=['addword'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_addword(m):
        if not is_admin(bot, m.chat.id, m.from_user.id): return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2: 
            reply_temp(m, "⚠️ Usage: `/addword xyz`")
            return
        word = parts[1].strip().lower()
        data = get_data(m.chat.id)
        if word not in data['banwords']:
            data['banwords'].append(word)
            reply_temp(m, f"✅ '{word}' added to banlist.")
        else:
             reply_temp(m, "⚠️ Word already exists.")

    @bot.message_handler(commands=['delword'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_delword(m):
        if not is_admin(bot, m.chat.id, m.from_user.id): return
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2: 
            reply_temp(m, "⚠️ Usage: `/delword xyz`")
            return
        word = parts[1].strip().lower()
        data = get_data(m.chat.id)
        if word in data['banwords']:
            data['banwords'].remove(word)
            reply_temp(m, f"✅ '{word}' removed.")
        else:
            reply_temp(m, "⚠️ Word not found.")

    @bot.message_handler(commands=['banlist'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_banlist(m):
        if not is_admin(bot, m.chat.id, m.from_user.id): return
        data = get_data(m.chat.id)
        if not data['banwords']: 
            reply_temp(m, "📂 Banlist is empty.")
        else: 
            reply_temp(m, f"🚫 **Banned Words:**\n" + ", ".join([f"`{w}`" for w in data['banwords']]), delay=10)

    print("✅ All Group Commands Registered.")
