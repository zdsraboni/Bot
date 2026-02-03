from handlers.tools.watermark_engine import DEFAULT_WM_SETTINGS

group_data = {}

def get_default_settings():
    return {
        'toggles': {
            'antilink': False,
            'welcome': True,
            'service': False,
            'block_sticker': False,
            'block_voice': False
        },
        'texts': {
            'welcome': "👋 হ্যালো {name}! আমাদের গ্রুপে স্বাগতম।",
            'rules': "📝 এখনো কোনো রুলস সেট করা হয়নি।",
            'warn': "⚠️ {name}, সাবধানে থাকুন! ({count}/{limit})",
            'ban': "🚫 {name}-কে ব্যান করা হয়েছে।",
            'mute': "🔇 {name}-কে মিউট করা হয়েছে।",
            'unmute': "🔊 {name}-কে আনমিউট করা হয়েছে।",
            'pin': "📌 মেসেজটি পিন করা হয়েছে।",
            'unpin': "📌 মেসেজটি আনপিন করা হয়েছে।"
        },
        'tools': {
            'downloader': False,
            'weather': False,
            'shortener': False,
            'watermark': False 
        },
        # --- WATERMARK SETTINGS (NEW) ---
        'wm_settings': DEFAULT_WM_SETTINGS.copy(), 
        # --------------------------------
        'warn_settings': {
            'limit': 3,
            'action': 'mute' 
        },
        'warns': {}, 
        'banwords': []
    }

def get_data(chat_id):
    if chat_id not in group_data:
        group_data[chat_id] = get_default_settings()
    return group_data[chat_id]

def save_wm_settings(chat_id, key, value):
    data = get_data(chat_id)
    data['wm_settings'][key] = value

def reset_warns(chat_id, user_id):
    data = get_data(chat_id)
    if user_id in data['warns']:
        del data['warns'][user_id]
