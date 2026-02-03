import json
import os
import time
import threading
from config import SUPER_ADMINS, BACKUP_CHANNEL_ID, CUSTOM_FILE, USERS_FILE

# ==========================================
# 📂 SECTION 1: SETTINGS & CACHE (custom_data.json)
# ==========================================

def load_initial_data():
    """Loads settings from custom_data.json into RAM"""
    if os.path.exists(CUSTOM_FILE):
        try:
            with open(CUSTOM_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading settings: {e}")
            return {}
    return {}

# Load settings into RAM once (Global Cache)
CACHED_DATA = load_initial_data()

def reload_data():
    """Refreshes settings from disk"""
    global CACHED_DATA
    CACHED_DATA = load_initial_data()
    return CACHED_DATA

def get_data(key=None, default_value=None):
    """
    Returns the entire data dict if key is None,
    OR returns a specific value if key is provided.
    """
    if key is None:
        return CACHED_DATA
    return CACHED_DATA.get(key, default_value)

def save_data(data):
    """
    ✅ NEW: Saves the entire dictionary to custom_data.json.
    Used by Admin Panel for toggling tools/menus.
    """
    global CACHED_DATA
    try:
        with open(CUSTOM_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        CACHED_DATA = data # Update RAM Cache
        return True
    except Exception as e:
        print(f"❌ Error saving data: {e}")
        return False

# ==========================================
# 📤 SECTION 2: BACKUP SYSTEM
# ==========================================

def send_backup(bot, commit_msg="System Update"):
    """
    Sends ONLY the custom_data.json file to the backup channel.
    """
    if not bot or not BACKUP_CHANNEL_ID: return
    try:
        if os.path.exists(CUSTOM_FILE):
            with open(CUSTOM_FILE, 'rb') as f:
                bot.send_document(
                    BACKUP_CHANNEL_ID, 
                    f, 
                    caption=f"🔄 <b>{commit_msg}</b>\nTime: <code>{time.ctime()}</code>",
                    visible_file_name="custom_data.json"
                )
    except Exception as e:
        print(f"⚠️ Backup Failed: {e}")

# ==========================================
# 👥 SECTION 3: USER DATABASE (users.json)
# ==========================================

def load_users():
    """Reads the separate users file instantly."""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def track_user(user):
    """
    Saves user info to users.json separately.
    """
    user_id = str(user.id)
    users = load_users()
    
    # Update User Data
    users[user_id] = {
        "id": user.id,
        "first_name": user.first_name,
        "username": user.username,
        "last_active": time.time()
    }
    
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error saving user database: {e}")

# ==========================================
# 🛠 SECTION 4: HELPERS (Text & Admin)
# ==========================================

def get_text(key, default_text=""):
    return str(CACHED_DATA.get("texts", {}).get(key, default_text))

def set_text(key, new_value, bot=None, commit_msg=None):
    """Updates a specific text setting and triggers backup"""
    data = get_data()
    if "texts" not in data: data["texts"] = {}
    
    data["texts"][key] = new_value
    
    if save_data(data):
        # Trigger Backup for Settings changes
        if bot:
            final_msg = commit_msg if commit_msg else f"Update Text: {key}"
            send_backup(bot, final_msg)
        return True
    return False

def is_admin(user_id):
    """Checks if user is Super Admin or Dynamic Admin"""
    dynamic_admins = CACHED_DATA.get("admin_ids", [])
    if user_id in dynamic_admins: return True
    if user_id in SUPER_ADMINS: return True
    return False

def add_admin(user_id, bot=None):
    current_admins = CACHED_DATA.get("admin_ids", [])
    if user_id not in current_admins:
        current_admins.append(user_id)
        
        # Get full data to save properly
        data = get_data()
        data["admin_ids"] = current_admins
        
        if save_data(data):
            if bot: send_backup(bot, f"New Admin Added: {user_id}")
            return True
    return False

# ==========================================
# 🧹 SECTION 5: AUTO CLEAN SYSTEM (NEW)
# ==========================================

def delete_msg(bot, message):
    """
    Safely deletes a message.
    """
    try:
        bot.delete_message(message.chat.id, message.message_id)
        return True
    except Exception:
        return False

class StatusMsg:
    """
    Smart Loading Message:
    Sends a 'Loading...' message and automatically deletes it when .done() is called.
    """
    def __init__(self, bot, chat_id):
        self.bot = bot
        self.chat_id = chat_id
        self.msg = None

    def send(self, text):
        try:
            self.msg = self.bot.send_message(self.chat_id, text)
            return self.msg
        except:
            return None

    def done(self):
        if self.msg:
            delete_msg(self.bot, self.msg)
