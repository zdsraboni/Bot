import os
import requests
import base64
import json
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# প্লাগইন ইনফো
TOOL_INFO = {
    "label": "🐙 My GitHub Manager",
    "callback": "ugh_home"
}

# ডাটা ফাইল পাথ
BASE_DIR = os.path.dirname(__file__)
USER_DATA_FILE = os.path.join(BASE_DIR, "user_gh_data.json")
GH_STATE = {}

# ==========================================
# 💾 DATABASE HELPERS
# ==========================================
def load_user_data(user_id):
    if not os.path.exists(USER_DATA_FILE): return None
    try:
        with open(USER_DATA_FILE, 'r') as f:
            data = json.load(f)
            return data.get(str(user_id))
    except Exception: return None

def save_user_data(user_id, info):
    data = {}
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r') as f:
                data = json.load(f)
        except Exception: pass
    
    if str(user_id) in data:
        data[str(user_id)].update(info)
    else:
        data[str(user_id)] = info

    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f)

def logout_user(user_id):
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f: data = json.load(f)
        if str(user_id) in data:
            del data[str(user_id)]
            with open(USER_DATA_FILE, 'w') as f: json.dump(data, f)

# ==========================================
# 🛠 API HELPERS
# ==========================================
def get_headers(token):
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

def get_repos_list(user_id):
    creds = load_user_data(user_id)
    if not creds: return []
    url = "https://api.github.com/user/repos?sort=pushed&per_page=30"
    try:
        resp = requests.get(url, headers=get_headers(creds['token']))
        return resp.json() if resp.status_code == 200 else []
    except: return []

def api_request(method, user_id, path="", data=None):
    creds = load_user_data(user_id)
    if not creds or 'repo' not in creds: return False, "Login or Repo missing"
    
    path = path.strip("/")
    url = f"https://api.github.com/repos/{creds['user']}/{creds['repo']}/contents/{path}"
    headers = get_headers(creds['token'])
    
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200: return True, resp.json()
            return False, f"HTTP {resp.status_code}"
        
        elif method == "PUT":
            resp = requests.put(url, headers=headers, data=json.dumps(data))
            if resp.status_code in [200, 201]: return True, "Success"
            return False, f"Err: {resp.json().get('message')}"
            
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, data=json.dumps(data))
            if resp.status_code in [200, 201]: return True, "Success"
            return False, str(resp.status_code)

    except Exception as e: return False, str(e)

# ==========================================
# 🖥 UI FUNCTIONS
# ==========================================
def show_login_page(bot, chat_id, message_id=None):
    text = "🐙 **GitHub Connect**\n\nLogin to manage your repositories."
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔐 Login with Token", callback_data="ugh_login_start"))
    kb.add(InlineKeyboardButton("🔙 Cancel", callback_data="gm_tools"))
    if message_id: bot.edit_message_text(text, chat_id, message_id, reply_markup=kb, parse_mode="Markdown")
    else: bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")

def show_repo_list(bot, chat_id, message_id=None):
    repos = get_repos_list(chat_id)
    if not repos: return bot.send_message(chat_id, "⚠️ No repos found or token expired.")

    text = "📦 **Select Repository:**"
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(f"📓 {repo['name']}", callback_data=f"ugh_set_repo:{repo['name']}") for repo in repos]
    kb.add(*buttons)
    kb.row(InlineKeyboardButton("🚪 Logout", callback_data="ugh_logout"), InlineKeyboardButton("❌ Close", callback_data="ugh_close"))

    if message_id: bot.edit_message_text(text, chat_id, message_id, reply_markup=kb, parse_mode="Markdown")
    else: bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")

def show_browser(bot, chat_id, message_id=None):
    state = GH_STATE.get(chat_id, {})
    current_path = state.get("path", "")
    creds = load_user_data(chat_id)
    
    success, items = api_request("GET", chat_id, current_path)
    if not success:
        return bot.send_message(chat_id, "⚠️ Error loading repo.", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Switch Repo", callback_data="ugh_switch_repo")))

    text = f"📦 **Repo:** `{creds['repo']}`\n📂 **Path:** `{current_path if current_path else 'Root'}`\n\n"
    kb = InlineKeyboardMarkup(row_width=2)
    
    if isinstance(items, list):
        folders = [i for i in items if i['type'] == 'dir']
        files = [i for i in items if i['type'] == 'file']
        for f in folders: kb.add(InlineKeyboardButton(f"📂 {f['name']}", callback_data=f"ugh_nav:dir:{f['name']}"))
        for f in files: kb.add(InlineKeyboardButton(f"📄 {f['name']}", callback_data=f"ugh_nav:file:{f['name']}"))

    controls = []
    if current_path: controls.append(InlineKeyboardButton("⬅️ Back", callback_data="ugh_nav:back"))
    else: controls.append(InlineKeyboardButton("🔙 Repos", callback_data="ugh_switch_repo"))
    controls.append(InlineKeyboardButton("➕ Upload", callback_data="ugh_act:create"))
    
    kb.row(*controls)
    kb.row(InlineKeyboardButton("❌ Close", callback_data="ugh_close"))

    if message_id: bot.edit_message_text(text, chat_id, message_id, reply_markup=kb, parse_mode="Markdown")
    else: bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")

def show_file_options(bot, chat_id, message_id, filename):
    text = f"📄 **File:** `{filename}`\nSelect Action:"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📥 Download", callback_data=f"ugh_do:dl:{filename}"))
    kb.add(InlineKeyboardButton("✏️ Rename", callback_data=f"ugh_do:rn:{filename}"), 
           InlineKeyboardButton("🗑 Delete", callback_data=f"ugh_do:del:{filename}"))
    kb.add(InlineKeyboardButton("⬅️ Back", callback_data="ugh_nav:refresh"))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=kb, parse_mode="Markdown")

# ==========================================
# 🎮 HANDLERS
# ==========================================
def register_handlers(bot):

    # -----------------------------------
    # 🔥 COMMANDS (NEW FEATURE)
    # -----------------------------------
    @bot.message_handler(commands=['mygit'])
    def cmd_mygit(message):
        """ওপেন মেনু"""
        if load_user_data(message.chat.id):
            GH_STATE[message.chat.id] = {"path": ""}
            show_browser(bot, message.chat.id)
        else:
            show_login_page(bot, message.chat.id)

    @bot.message_handler(commands=['gdl'])
    def cmd_gdl(message):
        """ডাউনলোড ফাইল: /gdl path/file.py"""
        try: path = message.text.split(maxsplit=1)[1].strip()
        except: return bot.reply_to(message, "⚠️ Usage: `/gdl path/to/file`", parse_mode="Markdown")
        
        msg = bot.reply_to(message, "📥 Downloading...")
        s, data = api_request("GET", message.chat.id, path)
        if s and "content" in data:
            bot.send_document(message.chat.id, base64.b64decode(data["content"]), visible_file_name=path.split('/')[-1])
            bot.delete_message(message.chat.id, msg.message_id)
        else: bot.edit_message_text("❌ Not found.", message.chat.id, msg.message_id)

    @bot.message_handler(commands=['grm'])
    def cmd_grm(message):
        """ডিলিট ফাইল: /grm path/file.py"""
        try: path = message.text.split(maxsplit=1)[1].strip()
        except: return bot.reply_to(message, "⚠️ Usage: `/grm path/to/file`", parse_mode="Markdown")
        
        msg = bot.reply_to(message, f"⏳ Deleting `{path}`...")
        
        # SHA পাওয়ার জন্য
        s, data = api_request("GET", message.chat.id, path)
        if s and "sha" in data:
            res, txt = api_request("DELETE", message.chat.id, path, {"message": "Del via Cmd", "sha": data["sha"]})
            bot.edit_message_text(f"✅ Deleted: `{path}`" if res else f"❌ {txt}", message.chat.id, msg.message_id, parse_mode="Markdown")
        else: bot.edit_message_text("❌ File not found.", message.chat.id, msg.message_id)

    @bot.message_handler(commands=['gmv'])
    def cmd_gmv(message):
        """রিনেম ফাইল: /gmv old new"""
        try: _, old, new = message.text.split()
        except: return bot.reply_to(message, "⚠️ Usage: `/gmv old_path new_path`", parse_mode="Markdown")
        
        msg = bot.reply_to(message, "⏳ Moving...")
        # 1. Get Old
        s, data = api_request("GET", message.chat.id, old)
        if s and "content" in data:
            # 2. Create New
            s2, _ = api_request("PUT", message.chat.id, new, {"message": "Renamed", "content": data["content"]})
            if s2:
                # 3. Delete Old
                api_request("DELETE", message.chat.id, old, {"message": "Del Old", "sha": data["sha"]})
                bot.edit_message_text(f"✅ Moved: `{old}` -> `{new}`", message.chat.id, msg.message_id, parse_mode="Markdown")
            else: bot.edit_message_text("❌ Creation failed.", message.chat.id, msg.message_id)
        else: bot.edit_message_text("❌ Source file not found.", message.chat.id, msg.message_id)

    @bot.message_handler(commands=['gup'])
    def cmd_gup(message):
        """আপলোড ফাইল: /gup path (reply or text)"""
        user_id = message.chat.id
        # 1. Reply থেকে ফাইল আপলোড
        if message.reply_to_message:
            try: path = message.text.split(maxsplit=1)[1].strip()
            except: 
                # নাম না দিলে ফাইলের নাম নিবে
                if message.reply_to_message.document: path = message.reply_to_message.document.file_name
                else: return bot.reply_to(message, "⚠️ Usage: `/gup path` or reply to file", parse_mode="Markdown")
            
            reply = message.reply_to_message
            content = None
            if reply.document:
                content = bot.download_file(bot.get_file(reply.document.file_id).file_path)
            elif reply.text:
                content = reply.text.encode()
            
            if content:
                msg = bot.reply_to(message, "⏳ Uploading...")
                # SHA চেক (আপডেটের জন্য)
                s, d = api_request("GET", user_id, path)
                sha = d.get("sha") if s else None
                
                encoded = base64.b64encode(content if isinstance(content, bytes) else content.encode()).decode()
                res, info = api_request("PUT", user_id, path, {"message": "Up via Cmd", "content": encoded, "sha": sha})
                bot.edit_message_text(f"✅ Uploaded: `{path}`" if res else f"❌ {info}", user_id, msg.message_id, parse_mode="Markdown")
            return

        # 2. শুধু পাথ সেট করা
        try: path = message.text.split(maxsplit=1)[1].strip()
        except: return bot.reply_to(message, "⚠️ Usage: `/gup folder/filename.ext`", parse_mode="Markdown")
        
        # State Set
        GH_STATE[user_id] = {"path": os.path.dirname(path), "temp_name": os.path.basename(path), "step": "content_wait"}
        bot.reply_to(message, f"📂 Target: `{path}`\n👉 Send content (File or Text) now.")

    # -----------------------------------
    # 🖱 BUTTON HANDLERS (EXISTING)
    # -----------------------------------
    @bot.callback_query_handler(func=lambda c: c.data == "ugh_home")
    def entry_point(call):
        creds = load_user_data(call.from_user.id)
        if creds and creds.get("token"):
            if creds.get("repo"):
                GH_STATE[call.from_user.id] = {"path": ""}
                show_browser(bot, call.message.chat.id, call.message.message_id)
            else: show_repo_list(bot, call.message.chat.id, call.message.message_id)
        else: show_login_page(bot, call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "ugh_login_start")
    def start_login(call):
        GH_STATE[call.from_user.id] = {"step": "waiting_gh_user"}
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="ugh_home"))
        bot.edit_message_text("👤 **GitHub Username:**", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.message_handler(func=lambda m: m.chat.id in GH_STATE and GH_STATE[m.chat.id].get("step") == "waiting_gh_user")
    def get_gh_user(message):
        GH_STATE[message.chat.id]["temp_user"] = message.text.strip()
        GH_STATE[message.chat.id]["step"] = "waiting_gh_token"
        bot.reply_to(message, "🔑 **Token:**")

    @bot.message_handler(func=lambda m: m.chat.id in GH_STATE and GH_STATE[m.chat.id].get("step") == "waiting_gh_token")
    def get_gh_token(message):
        user_id = message.chat.id
        token = message.text.strip()
        username = GH_STATE[user_id]["temp_user"]
        
        headers = {"Authorization": f"token {token}"}
        check = requests.get("https://api.github.com/user", headers=headers)
        
        if check.status_code == 200:
            save_user_data(user_id, {"user": username, "token": token})
            GH_STATE[user_id] = {} 
            bot.reply_to(message, "✅ **Login Successful!**")
            show_repo_list(bot, user_id)
        else: bot.reply_to(message, "❌ **Login Failed!**")

    @bot.callback_query_handler(func=lambda c: c.data == "ugh_switch_repo")
    def switch_repo(call): show_repo_list(bot, call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ugh_set_repo:"))
    def set_repo(call):
        repo_name = call.data.split(":")[1]
        save_user_data(call.from_user.id, {"repo": repo_name})
        GH_STATE[call.from_user.id] = {"path": ""}
        show_browser(bot, call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "ugh_logout")
    def logout(call):
        logout_user(call.from_user.id)
        bot.answer_callback_query(call.id, "Logged Out")
        show_login_page(bot, call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ugh_nav:"))
    def navigation(call):
        user_id = call.message.chat.id
        action = call.data.split(":")[1]
        state = GH_STATE.setdefault(user_id, {"path": ""})
        
        if action == "back":
            state["path"] = state["path"].rsplit("/", 1)[0] if "/" in state["path"] else ""
            show_browser(bot, user_id, call.message.message_id)
        elif action == "dir":
            folder = call.data.split(":")[2]
            state["path"] = f"{state['path']}/{folder}" if state['path'] else folder
            show_browser(bot, user_id, call.message.message_id)
        elif action == "file": show_file_options(bot, user_id, call.message.message_id, call.data.split(":")[2])
        elif action == "refresh": show_browser(bot, user_id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ugh_do:"))
    def file_actions(call):
        user_id = call.message.chat.id
        action, filename = call.data.split(":")[1], call.data.split(":")[2]
        path = GH_STATE[user_id].get("path", "")
        full_path = f"{path}/{filename}" if path else filename
        
        if action == "dl":
            bot.answer_callback_query(call.id, "📥 Downloading...")
            s, data = api_request("GET", user_id, full_path)
            if s and "content" in data:
                bot.send_document(user_id, base64.b64decode(data["content"]), visible_file_name=filename)
            else: bot.answer_callback_query(call.id, "Failed!")

        elif action == "del":
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("✅ Yes", callback_data=f"ugh_cf:del:{filename}"), InlineKeyboardButton("❌ No", callback_data="ugh_nav:refresh"))
            bot.edit_message_text(f"⚠️ Delete `{filename}`?", user_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

        elif action == "rn":
            GH_STATE[user_id]["step"] = "rn_wait"
            GH_STATE[user_id]["target"] = full_path
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="ugh_nav:refresh"))
            bot.edit_message_text(f"✏️ Rename `{filename}` to:", user_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ugh_cf:del:"))
    def confirm_del(call):
        user_id = call.message.chat.id
        filename = call.data.split(":")[2]
        path = GH_STATE[user_id].get("path", "")
        full_path = f"{path}/{filename}" if path else filename
        
        s, data = api_request("GET", user_id, full_path)
        if s and "sha" in data:
            bot.edit_message_text("⏳ Deleting...", user_id, call.message.message_id)
            res, msg = api_request("DELETE", user_id, full_path, {"message": "Del", "sha": data["sha"]})
            if res: show_browser(bot, user_id, call.message.message_id)
            else: bot.edit_message_text(f"❌ {msg}", user_id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "ugh_act:create")
    def start_upload(call):
        GH_STATE[call.message.chat.id]["step"] = "up_wait"
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="ugh_nav:refresh"))
        bot.edit_message_text("📂 **Upload:** Send File or Filename.", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.message_handler(content_types=['document', 'text'], func=lambda m: m.chat.id in GH_STATE and GH_STATE[m.chat.id].get("step") in ["up_wait", "rn_wait", "content_wait"])
    def process_inputs(message):
        user_id = message.chat.id
        step = GH_STATE[user_id]["step"]
        path = GH_STATE[user_id].get("path", "")

        # Rename
        if step == "rn_wait":
            old_path = GH_STATE[user_id]["target"]
            new_name = message.text.strip()
            parent = old_path.rsplit("/", 1)[0] if "/" in old_path else ""
            new_path = f"{parent}/{new_name}" if parent else new_name
            
            msg = bot.reply_to(message, "⏳ Renaming...")
            s, data = api_request("GET", user_id, old_path)
            if s and "content" in data:
                s2, _ = api_request("PUT", user_id, new_path, {"message": "Renamed", "content": data["content"]})
                if s2:
                    api_request("DELETE", user_id, old_path, {"message": "Del Old", "sha": data["sha"]})
                    bot.edit_message_text("✅ Renamed!", user_id, msg.message_id)
                    GH_STATE[user_id]["step"] = None
                    show_browser(bot, user_id)

        # Upload (File)
        elif step == "up_wait" and message.document:
            fname = message.document.file_name
            fpath = f"{path}/{fname}" if path else fname
            msg = bot.reply_to(message, "⏳ Uploading...")
            fi = bot.get_file(message.document.file_id)
            content = bot.download_file(fi.file_path)
            
            s, d = api_request("GET", user_id, fpath)
            sha = d.get("sha") if s else None
            encoded = base64.b64encode(content).decode("utf-8")
            s2, info = api_request("PUT", user_id, fpath, {"message": "Up", "content": encoded, "sha": sha})
            bot.edit_message_text("✅ Uploaded!" if s2 else f"❌ {info}", user_id, msg.message_id)
            if s2: 
                GH_STATE[user_id]["step"] = None
                show_browser(bot, user_id)

        # Upload (Name)
        elif step == "up_wait" and message.text:
            GH_STATE[user_id]["temp_name"] = message.text.strip()
            GH_STATE[user_id]["step"] = "content_wait"
            bot.reply_to(message, "👉 Send Content.")

        # Content
        elif step == "content_wait":
            fname = GH_STATE[user_id]["temp_name"]
            fpath = f"{path}/{fname}" if path else fname # Path from button click state OR command state
            if GH_STATE[user_id].get("path") is None: # If path wasn't set by state, use root
                 pass # path default empty

            content = message.text if message.text else bot.download_file(bot.get_file(message.document.file_id).file_path)
            encoded = base64.b64encode(content.encode() if isinstance(content, str) else content).decode()
            
            msg = bot.reply_to(message, "⏳ Saving...")
            s, info = api_request("PUT", user_id, fpath, {"message": "New", "content": encoded})
            bot.edit_message_text("✅ Saved!" if s else f"❌ {info}", user_id, msg.message_id)
            GH_STATE[user_id]["step"] = None
            if load_user_data(user_id).get("repo"): show_browser(bot, user_id) # Refresh browser if active

    @bot.callback_query_handler(func=lambda c: c.data == "ugh_close")
    def close(call): bot.delete_message(call.message.chat.id, call.message.message_id)
