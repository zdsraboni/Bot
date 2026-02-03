import os
import requests
import base64
import json
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import GITHUB_TOKEN, REPO_NAME, GITHUB_USER, SUPER_ADMINS

# স্টেট ম্যানেজমেন্ট
GH_STATE = {}

# ==========================================
# 🛠 GITHUB API HELPERS
# ==========================================
def get_github_content(path=""):
    """গিটহাবের নির্দিষ্ট পাথের লিস্ট আনে"""
    if not GITHUB_TOKEN or not REPO_NAME or not GITHUB_USER: return None
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200: return resp.json()
        return []
    except: return []

def get_file_content(path):
    """গিটহাব থেকে ফাইলের কন্টেন্ট ডাউনলোড করে"""
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            if "content" in data:
                return base64.b64decode(data["content"]), data.get("name", "file")
    except: pass
    return None, None

def push_to_github(path, content, msg="Update via Bot"):
    """ফাইল আপলোড বা ক্রিয়েট করে"""
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    sha = None
    try:
        check = requests.get(url, headers=headers)
        if check.status_code == 200: sha = check.json().get("sha")
    except: pass

    if isinstance(content, str): content = content.encode('utf-8')
    encoded = base64.b64encode(content).decode("utf-8")

    data = {"message": msg, "content": encoded, "branch": "main"}
    if sha: data["sha"] = sha

    try:
        r = requests.put(url, headers=headers, data=json.dumps(data))
        return r.status_code in [200, 201]
    except: return False

# ==========================================
# 🖥 UI BUILDER
# ==========================================
def show_file_browser(bot, chat_id, message_id=None):
    user_state = GH_STATE.get(chat_id, {"path": ""})
    current_path = user_state.get("path", "")
    
    items = get_github_content(current_path)
    if items is None:
        bot.send_message(chat_id, "❌ GitHub Config Missing!")
        return

    text = f"🐙 **GitHub Browser**\n📂 **Path:** `{current_path if current_path else 'Root'}`\n\n"
    kb = InlineKeyboardMarkup(row_width=2)
    
    folders = [i for i in items if i['type'] == 'dir']
    files = [i for i in items if i['type'] == 'file']
    
    # 📂 ফোল্ডার বাটন
    for f in folders:
        kb.add(InlineKeyboardButton(f"📂 {f['name']}", callback_data=f"gh_nav:dir:{f['name']}"))
        
    # 📄 ফাইল বাটন (ক্লিক করলে ডাউনলোড হবে)
    for f in files:
        kb.add(InlineKeyboardButton(f"📄 {f['name']}", callback_data=f"gh_nav:file:{f['name']}"))

    controls = []
    if current_path: controls.append(InlineKeyboardButton("⬅️ Back", callback_data="gh_nav:back"))
    controls.append(InlineKeyboardButton("➕ New/Upload", callback_data="gh_act:create"))
    
    kb.row(*controls)
    kb.row(InlineKeyboardButton("❌ Close", callback_data="gh_close"))

    if message_id:
        try: bot.edit_message_text(text, chat_id, message_id, reply_markup=kb, parse_mode="Markdown")
        except: pass
    else:
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")

# ==========================================
# 🎮 HANDLERS
# ==========================================
def register_handlers(bot):

    # ১. ব্রাউজার ওপেন কমান্ড
    @bot.message_handler(commands=['git'])
    def cmd_git_browser(message):
        if message.from_user.id not in SUPER_ADMINS: return
        GH_STATE[message.chat.id] = {"path": ""}
        show_file_browser(bot, message.chat.id)

    # ==========================================
    # 🚀 NEW: COMMAND BASED SYSTEM
    # ==========================================
    
    # কমান্ড: /get <path> (ফাইল ডাউনলোড)
    @bot.message_handler(commands=['get'])
    def cmd_get_file(message):
        if message.from_user.id not in SUPER_ADMINS: return
        try:
            path = message.text.split(maxsplit=1)[1].strip()
        except IndexError:
            bot.reply_to(message, "⚠️ Usage: `/get path/to/file.py`", parse_mode="Markdown")
            return

        msg = bot.reply_to(message, "⏳ Downloading...")
        content, name = get_file_content(path)
        if content:
            bot.send_document(message.chat.id, content, visible_file_name=name, caption=f"📂 Path: `{path}`", parse_mode="Markdown")
            bot.delete_message(message.chat.id, msg.message_id)
        else:
            bot.edit_message_text("❌ File not found or error.", message.chat.id, msg.message_id)

    # কমান্ড: /up <path> (ফাইল আপলোড/এডিট)
    @bot.message_handler(commands=['up', 'upload'])
    def cmd_upload_file(message):
        if message.from_user.id not in SUPER_ADMINS: return
        
        # ১. যদি রিপ্লাই থেকে ফাইল নিয়ে আপলোড করতে চায়
        if message.reply_to_message:
            try:
                path = message.text.split(maxsplit=1)[1].strip()
            except IndexError:
                bot.reply_to(message, "⚠️ Usage: Reply to a file/text with `/up path/filename.ext`", parse_mode="Markdown")
                return

            reply = message.reply_to_message
            content = None
            
            msg = bot.reply_to(message, "⏳ Uploading...")
            
            if reply.document:
                file_info = bot.get_file(reply.document.file_id)
                content = bot.download_file(file_info.file_path)
            elif reply.text:
                content = reply.text
            
            if content:
                if push_to_github(path, content, "Updated via /up Command"):
                    bot.edit_message_text(f"✅ **Success!**\nFile: `{path}`", message.chat.id, msg.message_id, parse_mode="Markdown")
                else:
                    bot.edit_message_text("❌ Upload Failed.", message.chat.id, msg.message_id)
            return

        # ২. যদি নরমাল মোডে আপলোড করতে চায় (স্টেট ব্যবহার করে)
        try:
            path = message.text.split(maxsplit=1)[1].strip()
            GH_STATE[message.chat.id] = {"temp_path": path, "step": "waiting_cmd_upload"}
            bot.reply_to(message, f"📂 Target: `{path}`\n👉 এখন ফাইল বা টেক্সট পাঠান।", parse_mode="Markdown")
        except IndexError:
            bot.reply_to(message, "⚠️ Usage: `/up folder/filename.ext`", parse_mode="Markdown")

    # কমান্ড আপলোড হ্যান্ডলার (পরের মেসেজ ধরার জন্য)
    @bot.message_handler(content_types=['document', 'text'], func=lambda m: m.chat.id in GH_STATE and GH_STATE[m.chat.id].get("step") == "waiting_cmd_upload")
    def process_cmd_upload(message):
        user_id = message.chat.id
        path = GH_STATE[user_id]["temp_path"]
        content = None
        
        msg = bot.reply_to(message, "⏳ Pushing to GitHub...")
        
        if message.document:
            file_info = bot.get_file(message.document.file_id)
            content = bot.download_file(file_info.file_path)
        elif message.text:
            content = message.text

        if push_to_github(path, content, "Uploaded via /up"):
            bot.edit_message_text(f"✅ Uploaded to: `{path}`", user_id, msg.message_id, parse_mode="Markdown")
        else:
            bot.edit_message_text("❌ Failed.", user_id, msg.message_id)
        
        GH_STATE[user_id]["step"] = None # Reset

    # ==========================================
    # 🖱 UI CALLBACKS
    # ==========================================
    @bot.callback_query_handler(func=lambda c: c.data == "open_gh_editor" or c.data == "gh_home")
    def cb_git_home(call):
        if call.from_user.id not in SUPER_ADMINS: return
        GH_STATE[call.message.chat.id] = {"path": ""}
        show_file_browser(bot, call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("gh_nav:"))
    def gh_navigation(call):
        user_id = call.message.chat.id
        action = call.data.split(":")[1]
        
        if user_id not in GH_STATE: GH_STATE[user_id] = {"path": ""}
        current = GH_STATE[user_id]["path"]

        if action == "back":
            if "/" in current: GH_STATE[user_id]["path"] = current.rsplit("/", 1)[0]
            else: GH_STATE[user_id]["path"] = ""
            show_file_browser(bot, user_id, call.message.message_id)
        
        elif action == "dir":
            folder_name = call.data.split(":")[2]
            new_path = f"{current}/{folder_name}" if current else folder_name
            GH_STATE[user_id]["path"] = new_path
            show_file_browser(bot, user_id, call.message.message_id)
            
        elif action == "file":
            # 🔥 ফাইল ডাউনলোড লজিক
            filename = call.data.split(":")[2]
            file_path = f"{current}/{filename}" if current else filename
            
            bot.answer_callback_query(call.id, "📥 Downloading...")
            content, name = get_file_content(file_path)
            if content:
                bot.send_document(user_id, content, visible_file_name=name, caption=f"📂 Path: `{file_path}`", parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "❌ Error fetching file", show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("gh_act:"))
    def gh_actions(call):
        user_id = call.message.chat.id
        action = call.data.split(":")[1]
        current = GH_STATE.get(user_id, {}).get("path", "")

        if action == "create":
            GH_STATE[user_id]["step"] = "waiting_filename"
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="gh_home"))
            bot.edit_message_text(f"📂 **Location:** `{current if current else 'Root'}`\n\nনতুন ফাইলের নাম দিন (উদা: `test.py`):", user_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.message_handler(func=lambda m: m.chat.id in GH_STATE and GH_STATE[m.chat.id].get("step") == "waiting_filename")
    def process_filename(message):
        name = message.text.strip()
        GH_STATE[message.chat.id]["temp_name"] = name
        GH_STATE[message.chat.id]["step"] = "waiting_content"
        bot.reply_to(message, f"📝 File: `{name}`\n👉 কন্টেন্ট পাঠান (Text বা File)।", parse_mode="Markdown")

    @bot.message_handler(content_types=['document', 'text'], func=lambda m: m.chat.id in GH_STATE and GH_STATE[m.chat.id].get("step") == "waiting_content")
    def process_content_ui(message):
        user_id = message.chat.id
        state = GH_STATE[user_id]
        
        path = f"{state['path']}/{state['temp_name']}" if state['path'] else state['temp_name']
        content = None

        if message.document:
            file_info = bot.get_file(message.document.file_id)
            content = bot.download_file(file_info.file_path)
        elif message.text:
            content = message.text
            
        msg = bot.reply_to(message, "⏳ Pushing...")
        if push_to_github(path, content):
            bot.edit_message_text(f"✅ Saved: `{path}`", user_id, msg.message_id, parse_mode="Markdown")
            GH_STATE[user_id]["step"] = None
            show_file_browser(bot, user_id)
        else:
            bot.edit_message_text("❌ Failed.", user_id, msg.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "gh_close")
    def close_browser(call):
        bot.delete_message(call.message.chat.id, call.message.message_id)
