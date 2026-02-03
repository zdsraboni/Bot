import json
import os
import time
import threading
from config import SUPER_ADMINS, BACKUP_CHANNEL_ID

# --- TWO SEPARATE FILES ---
CUSTOM_FILE = 'custom_data.json'  # For Settings (Backed up on change)
USERS_FILE = 'users.json'        # For Database (Silent save)

# থ্রেড লক (ডাটা সেফটির জন্য)
user_lock = threading.Lock()

# ==========================================
# SECTION 1: SETTINGS (custom_data.json)
# ==========================================

def load_initial_data():
    """Loads settings from custom_data.json"""
    if os.path.exists(CUSTOM_FILE):
        try:
            with open(CUSTOM_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading settings: {e}")
            return {}
    return {}

# Load settings into RAM once
CACHED_DATA = load_initial_data()

def reload_data():
    """Refreshes settings from disk"""
    global CACHED_DATA
    CACHED_DATA = load_initial_data()
    return True

def send_backup(bot, commit_msg="System Update"):
    """
    Sends ONLY the custom_data.json file to the backup channel.
    """
    if not bot: return
    try:
        with open(CUSTOM_FILE, 'rb') as f:
            bot.send_document(
                BACKUP_CHANNEL_ID, 
                f, 
                caption=f"🔄 <b>{commit_msg}</b>\nTime: <code>Just now</code>",
                visible_file_name="custom_data.json"
            )
    except Exception as e:
        print(f"⚠️ Backup Failed: {e}")

# ==========================================
# SECTION 2: USER DATABASE (users.json)
# ==========================================

def load_users():
    """Reads the separate users file instantly with Lock."""
    if not os.path.exists(USERS_FILE):
        return {}
        
    with user_lock:
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

def save_users(users):
    """Saves user info safely with Lock."""
    with user_lock:
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Error saving user database: {e}")
            return False

def track_user(user):
    """
    Saves user info to users.json separately.
    No backup triggered to prevent spam.
    """
    user_id = str(user.id)
    
    # 1. Load current users
    users = load_users()
    
    # 2. Update/Add User Data
    users[user_id] = {
        "id": user.id,
        "first_name": user.first_name,
        "username": user.username,
        "last_active": time.time()
    }
    
    # 3. Save to disk using safe function
    save_users(users)

# ==========================================
# SECTION 3: GETTERS & SETTERS (Settings)
# ==========================================

def get_text(key, default_text):
    return str(CACHED_DATA.get(key, default_text))

def get_data(key, default_value=None):
    return CACHED_DATA.get(key, default_value)

def is_admin(user_id):
    dynamic_admins = CACHED_DATA.get("admin_ids", [])
    if user_id in dynamic_admins: return True
    if user_id in SUPER_ADMINS: return True
    return False

def set_text(key, new_value, bot=None, commit_msg=None):
    CACHED_DATA[key] = new_value
    try:
        with open(CUSTOM_FILE, 'w', encoding='utf-8') as f:
            json.dump(CACHED_DATA, f, indent=4, ensure_ascii=False)
        
        # Trigger Backup for Settings changes
        if bot:
            final_msg = commit_msg if commit_msg else f"Update: {key}"
            send_backup(bot, final_msg)
        return True
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return False

def add_admin(user_id, bot=None, commit_msg="New Admin Added"):
    current_admins = CACHED_DATA.get("admin_ids", [])
    if user_id not in current_admins:
        current_admins.append(user_id)
        CACHED_DATA["admin_ids"] = current_admins
        try:
            with open(CUSTOM_FILE, 'w', encoding='utf-8') as f:
                json.dump(CACHED_DATA, f, indent=4, ensure_ascii=False)
            
            # Trigger Backup for Admin changes
            if bot: send_backup(bot, commit_msg)
            return True
        except Exception as e:
            return False
    return True
