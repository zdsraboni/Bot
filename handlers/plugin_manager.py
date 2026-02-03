import os
import sys
import time
import base64
import requests
import json
import shutil
import importlib.util
import logging
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPER_ADMINS, GITHUB_TOKEN, REPO_NAME, GITHUB_USER

# লগিং সেটআপ
logger = logging.getLogger(__name__)

PLUGIN_BASE_DIR = "handlers/plugins"

if not os.path.exists(PLUGIN_BASE_DIR):
    os.makedirs(PLUGIN_BASE_DIR)

CREATION_STATE = {}

# ==========================================
# 🌐 GITHUB SYNC
# ==========================================
def upload_to_github(file_path, content_bytes, commit_msg):
    if not GITHUB_TOKEN or not REPO_NAME or not GITHUB_USER: 
        return False, "Config Missing"
    
    relative_path = file_path.replace("\\", "/") 
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{relative_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    sha = None
    try:
        check = requests.get(url, headers=headers)
        if check.status_code == 200: sha = check.json().get("sha")
    except: pass

    if isinstance(content_bytes, str): content_bytes = content_bytes.encode('utf-8')
    data = {
        "message": commit_msg,
        "content": base64.b64encode(content_bytes).decode("utf-8"),
        "branch": "main",
    }
    if sha: data["sha"] = sha

    try:
        resp = requests.put(url, headers=headers, data=json.dumps(data))
        return resp.status_code in [200, 201], "Synced"
    except Exception as e: return False, str(e)

def restart_bot():
    logger.info("🔄 Restarting bot process...")
    os.execl(sys.executable, sys.executable, *sys.argv)

# ==========================================
# 📥 HANDLERS
# ==========================================
def register_plugin_handler(bot):
    
    @bot.callback_query_handler(func=lambda c: c.data == "gm_tools")
    def back_to_original_tools(call):
        bot.answer_callback_query(call.id)
        try:
            from keyboards.main_menu import tools_layout
            text, kb = tools_layout()
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        except:
            bot.send_message(call.message.chat.id, "🔙 Back to Menu")

    @bot.callback_query_handler(func=lambda c: c.data == "plugin_manager")
    def show_plugin_list(call):
        if call.from_user.id not in SUPER_ADMINS: return
        bot.answer_callback_query(call.id)
        kb = InlineKeyboardMarkup()
        
        if os.path.exists(PLUGIN_BASE_DIR):
            for folder in os.listdir(PLUGIN_BASE_DIR):
                path = os.path.join(PLUGIN_BASE_DIR, folder)
                if os.path.isdir(path) and not folder.startswith("__"):
                    kb.row(InlineKeyboardButton(f"📂 {folder}", callback_data=f"manage_plugin_{folder}"))
        
        kb.row(InlineKeyboardButton("➕ Create New Tool", callback_data="create_new_tool"))
        kb.row(InlineKeyboardButton("🔙 Back to Admin", callback_data="open_admin_panel"))
        bot.edit_message_text("🔌 **Plugin Manager**", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("manage_plugin_"))
    def manage_specific_plugin(call):
        folder_name = call.data.split("manage_plugin_")[1]
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("✏️ Upload/Update File", callback_data=f"upload_file_{folder_name}"))
        kb.row(InlineKeyboardButton("🗑 Delete Tool", callback_data=f"confirm_delete_{folder_name}"))
        kb.row(InlineKeyboardButton("🔙 Back", callback_data="plugin_manager"))
        bot.edit_message_text(f"🛠 **Manage:** `{folder_name}`", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_delete_"))
    def confirm_delete(call):
        folder_name = call.data.split("confirm_delete_")[1]
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton("✅ Yes, Delete", callback_data=f"final_delete_{folder_name}"))
        kb.row(InlineKeyboardButton("❌ Cancel", callback_data=f"manage_plugin_{folder_name}"))
        bot.edit_message_text(f"⚠️ Delete `{folder_name}`?", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("final_delete_"))
    def final_delete_action(call):
        folder_name = call.data.split("final_delete_")[1]
        path = os.path.join(PLUGIN_BASE_DIR, folder_name)
        try:
            if os.path.exists(path): shutil.rmtree(path)
            bot.edit_message_text(f"🗑 Deleted `{folder_name}`. Restarting...", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            time.sleep(1)
            restart_bot()
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {e}")

    @bot.callback_query_handler(func=lambda c: c.data == "create_new_tool")
    def start_creation(call):
        CREATION_STATE[call.from_user.id] = {'step': 'waiting_name'}
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="plugin_manager"))
        bot.edit_message_text("🛠 Enter new tool name (e.g., `qr_gen`):", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("upload_file_"))
    def start_upload_mode(call):
        folder_name = call.data.split("upload_file_")[1]
        CREATION_STATE[call.from_user.id] = {'step': 'uploading', 'folder': folder_name}
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Done / Restart", callback_data="finish_plugin_upload"))
        bot.edit_message_text(f"📂 **Active:** `{folder_name}`\n👉 Send `.py` file now.", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data == "finish_plugin_upload")
    def finish_upload(call):
        if call.from_user.id in CREATION_STATE: del CREATION_STATE[call.from_user.id]
        bot.edit_message_text("✅ Saved. Restarting...", call.message.chat.id, call.message.message_id)
        time.sleep(1)
        restart_bot()

    @bot.message_handler(func=lambda m: m.from_user.id in CREATION_STATE and CREATION_STATE[m.from_user.id]['step'] == 'waiting_name')
    def process_folder_name(message):
        user_id = message.from_user.id
        name = "".join(c for c in message.text.strip().lower() if c.isalnum() or c == "_")
        if not name: return bot.reply_to(message, "❌ Invalid name.")
        
        full_path = os.path.join(PLUGIN_BASE_DIR, name)
        if os.path.exists(full_path): return bot.reply_to(message, "⚠️ Already exists.")

        os.makedirs(full_path)
        init_path = os.path.join(full_path, "__init__.py")
        with open(init_path, 'w') as f: f.write("# Plugin Init")
        upload_to_github(f"handlers/plugins/{name}/__init__.py", b"# Plugin Init", f"Init {name}")
        
        CREATION_STATE[user_id] = {'step': 'uploading', 'folder': name}
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Done", callback_data="finish_plugin_upload"))
        bot.reply_to(message, f"📂 Created `{name}`. Send `.py` file.", reply_markup=kb, parse_mode="Markdown")

    # 👇 FIX: এখানে func ফিল্টার যুক্ত করা হয়েছে যাতে এটি অন্য হ্যান্ডলারে বাধা না দেয়
    @bot.message_handler(content_types=['document'], func=lambda m: m.from_user.id in CREATION_STATE and CREATION_STATE[m.from_user.id].get('step') == 'uploading')
    def save_plugin_file(message):
        user_id = message.from_user.id
        folder = CREATION_STATE[user_id]['folder']
        file_name = message.document.file_name
        
        if not file_name.endswith(".py"):
            return bot.reply_to(message, "❌ Only `.py` files allowed.")

        msg = bot.reply_to(message, "⏳ Saving...")
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded = bot.download_file(file_info.file_path)
            
            save_path = os.path.join(PLUGIN_BASE_DIR, folder, file_name)
            with open(save_path, 'wb') as f: f.write(downloaded)
            
            success, info = upload_to_github(f"handlers/plugins/{folder}/{file_name}", downloaded, f"Update {folder}/{file_name}")
            bot.edit_message_text(f"✅ Saved `{file_name}`\n🌐 GitHub: {info}", message.chat.id, msg.message_id, parse_mode="Markdown")
        except Exception as e:
            bot.edit_message_text(f"❌ Error: {e}", message.chat.id, msg.message_id)

def get_dynamic_tools(only_active=True):
    tools = []
    if not os.path.exists(PLUGIN_BASE_DIR): return []
    
    # os.walk ব্যবহার করা হয়েছে যাতে সাব-ফোল্ডারও স্ক্যান হয়
    for root, dirs, files in os.walk(PLUGIN_BASE_DIR):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                file_path = os.path.join(root, file)
                try:
                    # ডাইনামিক ইমপোর্ট লজিক
                    module_name = f"dynamic_plg_{os.path.basename(file)[:-3]}"
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    
                    if hasattr(mod, "TOOL_INFO"):
                        tools.append([mod.TOOL_INFO["label"], mod.TOOL_INFO["callback"]])
                except Exception as e:
                    logger.error(f"Failed to load plugin from {file_path}: {e}")
                    continue
    return tools
