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
def get_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def get_github_content(path=""):
    """গিটহাবের নির্দিষ্ট পাথের লিস্ট আনে"""
    if not GITHUB_TOKEN or not REPO_NAME or not GITHUB_USER: return None
    path = path.strip("/")
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{path}"
    try:
        resp = requests.get(url, headers=get_headers())
        return resp.json() if resp.status_code == 200 else []
    except: return []

def get_file_data(path):
    """ফাইলের কন্টেন্ট এবং SHA আনে"""
    path = path.strip("/")
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{path}"
    try:
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200:
            return resp.json()
    except: pass
    return None

def delete_item(path, sha=None):
    """ফাইল বা ফোল্ডার ডিলিট করে"""
    path = path.strip("/")
    
    # ১. যদি এটি ফাইল হয় (SHA দেওয়া থাকলে বা পাওয়া গেলে)
    if not sha:
        data = get_file_data(path)
        if data and isinstance(data, dict) and "sha" in data:
            sha = data["sha"]
        elif isinstance(data, list): # এটি একটি ফোল্ডার
             # ফোল্ডার ডিলিট (রিকার্সিভ) - গিটহাবে ফোল্ডার মানেই ফাইলস
             for item in data:
                 delete_item(item["path"], item["sha"])
             return True, "Folder Deleted"
        else:
            return False, "Item not found"

    # ২. ফাইল ডিলিট রিকোয়েস্ট
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{path}"
    data = {"message": f"Delete {path}", "sha": sha, "branch": "main"}
    try:
        resp = requests.delete(url, headers=get_headers(), data=json.dumps(data))
        return resp.status_code in [200, 201], "Deleted"
    except Exception as e: return False, str(e)

def rename_item(old_path, new_path):
    """ফাইল রিনেম (Move) করে"""
    # ১. আগের ফাইলের কন্টেন্ট নেওয়া
    data = get_file_data(old_path)
    if not data or "content" not in data: return False, "Source file not found"
    
    content = data["content"] # Base64 encoded
    sha = data["sha"]

    # ২. নতুন ফাইল তৈরি করা
    create_url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{new_path}"
    create_data = {
        "message": f"Rename {old_path} to {new_path}",
        "content": content, # আগের কন্টেন্ট
        "branch": "main"
    }
    
    try:
        # নতুন ফাইল পুশ
        resp = requests.put(create_url, headers=get_headers(), data=json.dumps(create_data))
        if resp.status_code not in [200, 201]:
            return False, f"Create Failed: {resp.status_code}"
        
        # ৩. পুরনো ফাইল ডিলিট করা
        del_url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{old_path}"
        del_data = {"message": "Delete old file (Rename)", "sha": sha, "branch": "main"}
        requests.delete(del_url, headers=get_headers(), data=json.dumps(del_data))
        
        return True, "Renamed Successfully"
    except Exception as e: return False, str(e)

def push_to_github(path, content, msg="Update via Bot"):
    path = path.strip("/")
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{path}"
    
    sha = None
    try:
        check = requests.get(url, headers=get_headers())
        if check.status_code == 200: sha = check.json().get("sha")
    except: pass

    try:
        if isinstance(content, str): content = content.encode('utf-8')
        encoded = base64.b64encode(content).decode("utf-8")
    except: return False, "Encoding Error"

    data = {"message": msg, "content": encoded, "branch": "main"}
    if sha: data["sha"] = sha

    try:
        r = requests.put(url, headers=get_headers(), data=json.dumps(data))
        if r.status_code in [200, 201]: return True, "✅ Success"
        return False, f"Error: {r.status_code}"
    except Exception as e: return False, str(e)

# ==========================================
# 🖥 UI BUILDER
# ==========================================
def show_file_browser(bot, chat_id, message_id=None):
    state = GH_STATE.get(chat_id, {})
    current_path = state.get("path", "")
    
    items = get_github_content(current_path)
    if items is None:
        bot.send_message(chat_id, "❌ GitHub Config Missing!")
        return

    text = f"🐙 **GitHub Browser**\n📂 **Path:** `{current_path if current_path else 'Root'}`\n\n"
    kb = InlineKeyboardMarkup(row_width=2)
    
    if isinstance(items, list):
        # ফোল্ডার আগে, তারপর ফাইল
        folders = [i for i in items if i['type'] == 'dir']
        files = [i for i in items if i['type'] == 'file']
        
        for f in folders: kb.add(InlineKeyboardButton(f"📂 {f['name']}", callback_data=f"gh_nav:dir:{f['name']}"))
        for f in files: kb.add(InlineKeyboardButton(f"📄 {f['name']}", callback_data=f"gh_nav:file:{f['name']}"))
    
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

def show_file_actions(bot, chat_id, message_id, filename):
    """ফাইলের অপশন মেনু"""
    state = GH_STATE.get(chat_id, {})
    current_path = state.get("path", "")
    full_path = f"{current_path}/{filename}" if current_path else filename
    
    text = f"📄 **File:** `{filename}`\n📂 **Path:** `{full_path}`\n\nকি করতে চান?"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📥 Download", callback_data=f"gh_do:dl:{filename}"))
    kb.add(InlineKeyboardButton("✏️ Rename", callback_data=f"gh_do:rn:{filename}"), 
           InlineKeyboardButton("🗑 Delete", callback_data=f"gh_do:del:{filename}"))
    kb.add(InlineKeyboardButton("⬅️ Back", callback_data="gh_nav:refresh")) # Back to browser
    
    bot.edit_message_text(text, chat_id, message_id, reply_markup=kb, parse_mode="Markdown")

# ==========================================
# 🎮 HANDLERS
# ==========================================
def register_handlers(bot):

    @bot.message_handler(commands=['git'])
    def cmd_git_browser(message):
        if message.from_user.id not in SUPER_ADMINS: return
        GH_STATE[message.chat.id] = {"path": ""}
        show_file_browser(bot, message.chat.id)

    # -----------------------------------
    # 🔥 COMMANDS: /rm & /mv
    # -----------------------------------
    @bot.message_handler(commands=['rm', 'delete'])
    def cmd_delete(message):
        if message.from_user.id not in SUPER_ADMINS: return
        try:
            path = message.text.split(maxsplit=1)[1].strip()
        except: return bot.reply_to(message, "⚠️ Usage: `/rm path/to/item`")
        
        msg = bot.reply_to(message, f"⏳ Deleting `{path}`...")
        success, info = delete_item(path)
        bot.edit_message_text(f"✅ Deleted: `{path}`" if success else f"❌ Error: {info}", message.chat.id, msg.message_id, parse_mode="Markdown")

    @bot.message_handler(commands=['mv', 'rename'])
    def cmd_rename(message):
        if message.from_user.id not in SUPER_ADMINS: return
        try:
            _, old, new = message.text.split()
        except: return bot.reply_to(message, "⚠️ Usage: `/mv old_path new_path`")
        
        msg = bot.reply_to(message, f"⏳ Renaming `{old}` -> `{new}`...")
        success, info = rename_item(old, new)
        bot.edit_message_text(f"✅ Renamed!" if success else f"❌ Error: {info}", message.chat.id, msg.message_id)

    # -----------------------------------
    # 📝 FILE PROCESSORS
    # -----------------------------------
    @bot.message_handler(content_types=['text', 'document'], func=lambda m: m.chat.id in GH_STATE and GH_STATE[m.chat.id].get("step"))
    def process_gh_inputs(message):
        user_id = message.chat.id
        step = GH_STATE[user_id]["step"]
        
        # 1. Upload Logic
        if step == "waiting_filename":
            current_path = GH_STATE[user_id].get("path", "")
            
            # Direct File
            if message.document:
                file_name = message.document.file_name
                full_path = f"{current_path}/{file_name}" if current_path else file_name
                msg = bot.reply_to(message, f"⏳ Uploading `{file_name}`...")
                try:
                    file_info = bot.get_file(message.document.file_id)
                    content = bot.download_file(file_info.file_path)
                    success, info = push_to_github(full_path, content, f"Upload {file_name}")
                    bot.edit_message_text(f"✅ Uploaded: `{full_path}`" if success else f"❌ {info}", user_id, msg.message_id, parse_mode="Markdown")
                    if success: 
                        GH_STATE[user_id]["step"] = None
                        show_file_browser(bot, user_id)
                except Exception as e: bot.edit_message_text(f"❌ Error: {e}", user_id, msg.message_id)
                return

            # Text Name
            if message.text:
                GH_STATE[user_id]["temp_name"] = message.text.strip()
                GH_STATE[user_id]["step"] = "waiting_content"
                bot.reply_to(message, f"📝 Name: `{message.text}`\n👉 Send content now.")
        
        # 2. Content Logic
        elif step == "waiting_content":
            filename = GH_STATE[user_id].get("temp_name", "file.txt")
            current = GH_STATE[user_id].get("path", "")
            path = f"{current}/{filename}" if current else filename
            
            content = message.text if message.text else ""
            if message.document:
                fi = bot.get_file(message.document.file_id)
                content = bot.download_file(fi.file_path)

            msg = bot.reply_to(message, "⏳ Saving...")
            success, info = push_to_github(path, content, f"Create {filename}")
            bot.edit_message_text(f"✅ Saved: `{path}`" if success else f"❌ {info}", user_id, msg.message_id, parse_mode="Markdown")
            GH_STATE[user_id]["step"] = None
            show_file_browser(bot, user_id)

        # 3. Rename Logic (New Name Input)
        elif step == "waiting_rename":
            old_path = GH_STATE[user_id]["target"]
            new_name = message.text.strip()
            
            # যদি ইউজার পুরো পাথ না দেয়, তবে শুধু নাম চেঞ্জ হবে (same folder)
            if "/" not in new_name:
                parent = old_path.rsplit("/", 1)[0] if "/" in old_path else ""
                new_path = f"{parent}/{new_name}" if parent else new_name
            else:
                new_path = new_name # ইউজার পাথ সহ দিয়েছে

            msg = bot.reply_to(message, "⏳ Renaming...")
            success, info = rename_item(old_path, new_path)
            
            bot.edit_message_text(f"✅ Done: `{new_path}`" if success else f"❌ {info}", user_id, msg.message_id, parse_mode="Markdown")
            GH_STATE[user_id]["step"] = None
            show_file_browser(bot, user_id)

    # -----------------------------------
    # 🖱 CALLBACKS
    # -----------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "gh_home")
    def cb_home(call):
        if call.from_user.id not in SUPER_ADMINS: return
        GH_STATE[call.message.chat.id] = {"path": ""}
        show_file_browser(bot, call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("gh_nav:"))
    def cb_nav(call):
        user_id = call.message.chat.id
        action = call.data.split(":")[1]
        state = GH_STATE.setdefault(user_id, {"path": ""})
        current = state["path"]

        if action == "back":
            state["path"] = current.rsplit("/", 1)[0] if "/" in current else ""
            show_file_browser(bot, user_id, call.message.message_id)
        elif action == "refresh":
            show_file_browser(bot, user_id, call.message.message_id)
        elif action == "dir":
            folder = call.data.split(":")[2]
            state["path"] = f"{current}/{folder}" if current else folder
            show_file_browser(bot, user_id, call.message.message_id)
        elif action == "file":
            filename = call.data.split(":")[2]
            # ফাইল ক্লিক করলে এখন অ্যাকশন মেনু দেখাবে
            show_file_actions(bot, user_id, call.message.message_id, filename)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("gh_do:"))
    def cb_actions(call):
        user_id = call.message.chat.id
        action, filename = call.data.split(":")[1], call.data.split(":")[2]
        state = GH_STATE.get(user_id, {})
        current = state.get("path", "")
        full_path = f"{current}/{filename}" if current else filename

        if action == "dl": # Download
            bot.answer_callback_query(call.id, "📥 Downloading...")
            data = get_file_data(full_path)
            if data and "content" in data:
                content = base64.b64decode(data["content"])
                bot.send_document(user_id, content, visible_file_name=filename, caption=f"📂 `{full_path}`", parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "❌ Error!", show_alert=True)
        
        elif action == "del": # Delete Confirm
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("✅ Confirm Delete", callback_data=f"gh_confirm:del:{filename}"))
            kb.add(InlineKeyboardButton("❌ Cancel", callback_data="gh_nav:refresh"))
            bot.edit_message_text(f"⚠️ **Delete File?**\n`{filename}`", user_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

        elif action == "rn": # Rename Start
            GH_STATE[user_id]["step"] = "waiting_rename"
            GH_STATE[user_id]["target"] = full_path
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="gh_nav:refresh"))
            bot.edit_message_text(f"✏️ **Rename:** `{filename}`\n\nনতুন নাম লিখুন (বা পাথ সহ নাম):", user_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("gh_confirm:del:"))
    def cb_confirm_del(call):
        user_id = call.message.chat.id
        filename = call.data.split(":")[2]
        current = GH_STATE.get(user_id, {}).get("path", "")
        full_path = f"{current}/{filename}" if current else filename
        
        bot.edit_message_text("⏳ Deleting...", user_id, call.message.message_id)
        success, info = delete_item(full_path)
        
        if success:
            bot.answer_callback_query(call.id, "🗑 Deleted!")
            show_file_browser(bot, user_id, call.message.message_id)
        else:
            bot.edit_message_text(f"❌ Error: {info}", user_id, call.message.message_id)
            time.sleep(2)
            show_file_browser(bot, user_id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("gh_act:"))
    def cb_act(call):
        user_id = call.message.chat.id
        if call.data == "gh_act:create":
            GH_STATE[user_id]["step"] = "waiting_filename"
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="gh_nav:refresh"))
            bot.edit_message_text("📂 **Upload/Create**\n\n👉 ফাইল (Document) পাঠান।\n👉 অথবা ফাইলের নাম লিখুন।", user_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data == "gh_close")
    def close(call): bot.delete_message(call.message.chat.id, call.message.message_id)
