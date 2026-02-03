import os
import re
import json
import time
import shutil
import subprocess
import requests
import html
from urllib.parse import urlparse

# 📦 প্রয়োজনীয় প্যাকেজ চেক
required_packages = ["yt_dlp", "deep-translator"]
for package in required_packages:
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        subprocess.check_call(["pip", "install", package])

import yt_dlp
from deep_translator import GoogleTranslator
from telebot import types
from telebot.types import InputMediaPhoto, InputMediaVideo

# ==========================================
# 🧩 ১. কনফিগারেশন ও মিরর (V10 Strategy)
# ==========================================
TOOL_INFO = {
    "label": "🤖 Reddit DL Ultimate",
    "callback": "plugin_reddit_menu"
}

MIRRORS = [
    'https://redlib.catsarch.com',
    'https://redlib.vlingit.com',
    'https://libreddit.kavin.rocks',
    'https://redlib.tux.pizza',
    'https://redlib.ducks.party',
    'https://r.walkx.org'
]
UA_ANDROID = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
SETTINGS_FILE = "plugin_data_reddit.json"

# ==========================================
# ⚙️ ২. ডাটা এক্সট্রাক্টর লজিক
# ==========================================

def resolve_reddit_url(url):
    if "/s/" not in url: return url
    try:
        res = requests.head(url, allow_redirects=True, headers={'User-Agent': UA_ANDROID}, timeout=5)
        return res.url
    except: return url

def get_reddit_metadata(url):
    full_url = resolve_reddit_url(url)
    path_name = urlparse(full_url).path.split('?')[0]
    targets = [full_url.split('?')[0].rstrip('/') + ".json"]
    for m in MIRRORS:
        targets.append(f"{m}{path_name}".rstrip('/') + ".json")

    for target_url in targets:
        try:
            res = requests.get(target_url, headers={'User-Agent': UA_ANDROID}, timeout=6)
            if res.status_code == 200:
                data = res.json()
                return data[0]['data']['children'][0]['data'], full_url
        except: continue
    return None, full_url

# ==========================================
# 📊 ৩. সেটিংস হ্যান্ডলার
# ==========================================

def get_user_config(chat_id):
    if not os.path.exists(SETTINGS_FILE): return {"power": True, "trans": False}
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f).get(str(chat_id), {"power": True, "trans": False})
    except: return {"power": True, "trans": False}

def update_user_config(chat_id, key, value):
    data = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f: data = json.load(f)
    conf = get_user_config(chat_id)
    conf[key] = value
    data[str(chat_id)] = conf
    with open(SETTINGS_FILE, 'w') as f: json.dump(data, f)

# ==========================================
# 📥 ৪. মেইন হ্যান্ডলার
# ==========================================

def register_handlers(bot):
    
    @bot.callback_query_handler(func=lambda c: c.data == "plugin_reddit_menu")
    def reddit_menu(call):
        conf = get_user_config(call.message.chat.id)
        msg = (
            "🤖 **Reddit DL PRO (Custom Caption)**\n\n"
            f"⚡ **Status:** `{'🟢 ON' if conf['power'] else '🔴 OFF'}`\n"
            f"🌐 **Translation:** `{'✅ ON' if conf['trans'] else '❌ OFF'}`\n"
            "📦 **Mode:** `Mirror + Fallback`"
        )
        mk = types.InlineKeyboardMarkup(row_width=2)
        mk.add(
            types.InlineKeyboardButton("🔴 Turn OFF" if conf['power'] else "🟢 Turn ON", callback_data="rd_toggle_power"),
            types.InlineKeyboardButton(f"🌐 Translate: {'ON' if conf['trans'] else 'OFF'}", callback_data="rd_toggle_trans")
        )
        mk.add(types.InlineKeyboardButton("🔙 Back to Tools", callback_data="gm_tools"))
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=mk)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("rd_"))
    def settings_handler(call):
        chat_id = call.message.chat.id
        conf = get_user_config(chat_id)
        if call.data == "rd_toggle_power": update_user_config(chat_id, "power", not conf['power'])
        elif call.data == "rd_toggle_trans": update_user_config(chat_id, "trans", not conf['trans'])
        reddit_menu(call)

    @bot.message_handler(func=lambda m: m.text and ("reddit.com" in m.text or "v.redd.it" in m.text or "i.redd.it" in m.text) and get_user_config(m.chat.id).get('power', True))
    def handle_reddit_dl(message):
        chat_id = message.chat.id
        conf = get_user_config(chat_id)
        
        # কাস্টম ক্যাপশন প্রসেসিং
        parts = message.text.split(maxsplit=1)
        url = parts[0].strip()
        custom_caption = parts[1].strip() if len(parts) > 1 else None
        
        status = bot.reply_to(message, "🔍 **Resolving & Analyzing...**")
        dl_dir = f"downloads/rd_{chat_id}_{int(time.time())}"
        os.makedirs(dl_dir, exist_ok=True)

        try:
            # ১. মেটাডাটা এক্সট্রাক্ট করা
            post, full_url = get_reddit_metadata(url)
            media_list = []
            title = post.get('title', 'Reddit Media') if post else "Reddit Media"
            
            # ২. ক্যাপশন লজিক: কাস্টম > (অনুবাদ ? বাংলা : অরিজিনাল)
            if custom_caption:
                final_caption = custom_caption
            elif conf['trans']:
                try: final_caption = GoogleTranslator(source='auto', target='bn').translate(title[:4500])
                except: final_caption = title
            else:
                final_caption = title

            # ৩. মিডিয়া ডাউনলোড (Gallery/Image/Video)
            if post and post.get('is_gallery') and 'media_metadata' in post:
                bot.edit_message_text("📚 **Gallery detected! Fetching...**", chat_id, status.message_id)
                gallery_items = post.get('gallery_data', {}).get('items', [])
                for item in gallery_items:
                    meta = post['media_metadata'].get(item['media_id'])
                    if meta and meta.get('status') == 'valid':
                        u = meta['s'].get('u', meta['s'].get('gif', '')).replace('&amp;', '&')
                        res = requests.get(u, headers={'User-Agent': UA_ANDROID}, timeout=10)
                        ext = "jpg" if "jpg" in u or "jpeg" in u else "png"
                        with open(os.path.join(dl_dir, f"{item['media_id']}.{ext}"), 'wb') as f: f.write(res.content)
            
            elif post and (re.search(r'\.(jpeg|jpg|png|gif)$', post.get('url', ''), re.I) or post.get('post_hint') == 'image'):
                img_url = post['url']
                res = requests.get(img_url, headers={'User-Agent': UA_ANDROID}, timeout=10)
                ext = img_url.split('.')[-1].split('?')[0] or "jpg"
                if len(ext) > 4: ext = "jpg"
                with open(os.path.join(dl_dir, f"image.{ext}"), 'wb') as f: f.write(res.content)
            
            else:
                video_source = post.get('secure_media', {}).get('reddit_video', {}).get('fallback_url', full_url) if post else full_url
                ydl_opts = {'outtmpl': f'{dl_dir}/%(title)s.%(ext)s', 'quiet': True, 'user_agent': UA_ANDROID}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([video_source])

            # ৪. মিডিয়া গ্রুপ তৈরি ও আপলোড
            files = sorted([os.path.join(dl_dir, f) for f in os.listdir(dl_dir)])
            for i, f_path in enumerate(files):
                cap = final_caption[:1000] if i == 0 else None
                with open(f_path, 'rb') as f:
                    if f_path.endswith(('.mp4', '.mkv', '.webm', '.gif')):
                        media_list.append(InputMediaVideo(f.read(), caption=cap))
                    else:
                        media_list.append(InputMediaPhoto(f.read(), caption=cap))

            if media_list:
                bot.send_media_group(chat_id, media_list, reply_to_message_id=message.message_id)
                bot.delete_message(chat_id, status.message_id)
            else:
                bot.edit_message_text("❌ No supported media found.", chat_id, status.message_id)

        except Exception as e:
            err = html.escape(str(e))[:150] # পার্সিং এরর ফিক্স
            bot.edit_message_text(f"❌ **Error:** `{err}`", chat_id, status.message_id, parse_mode="Markdown")
        finally:
            if os.path.exists(dl_dir): shutil.rmtree(dl_dir) # রেলওয়ে মেমরি ক্লিনআপ
