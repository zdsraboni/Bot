import time
import re  # <--- Regex লাইব্রেরি ইমপোর্ট করা হলো
from telebot import TeleBot, types

# ---------------------------------------------
# 1. DATA STORAGE
# ---------------------------------------------
group_data = {}

defaults = {
    'toggles': {'antilink': False, 'welcome': True, 'service': False},
    'texts': {
        'welcome': "👋 হ্যালো {name}! আমাদের গ্রুপে স্বাগতম।",
        'ban': "🚫 {name}-কে গ্রুপ থেকে ব্যান করা হয়েছে।",
        'mute': "🔇 {name}-কে মিউট করা হয়েছে।",
        'unmute': "🔊 {name}-কে আনমিউট করা হয়েছে।",
        'pin': "📌 মেসেজটি পিন করা হয়েছে।",
        'unpin': "📌 মেসেজটি আনপিন করা হয়েছে।"
    },
    'banwords': []
}

def get_group_data(chat_id):
    if chat_id not in group_data:
        group_data[chat_id] = {
            'toggles': defaults['toggles'].copy(),
            'texts': defaults['texts'].copy(),
            'banwords': []
        }
    return group_data[chat_id]

def toggle_setting(chat_id, key):
    data = get_group_data(chat_id)
    if key in data['toggles']:
        data['toggles'][key] = not data['toggles'][key]
        return data['toggles'][key]
    return False

def set_custom_text(chat_id, key, text):
    data = get_group_data(chat_id)
    if key in data['texts']:
        data['texts'][key] = text
        return True
    return False

def get_text(chat_id, key):
    return get_group_data(chat_id)['texts'][key]

# ---------------------------------------------
# 2. HELPER: ADMIN CHECK
# ---------------------------------------------
def is_user_group_admin(bot, chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

def format_text(text, user=None, chat_title=None):
    if user:
        text = text.replace("{name}", user.first_name)
        text = text.replace("{username}", f"@{user.username}" if user.username else "No Username")
        text = text.replace("{id}", str(user.id))
    if chat_title:
        text = text.replace("{chat_title}", chat_title)
    return text

# ---------------------------------------------
# 3. UI GENERATORS
# ---------------------------------------------
def get_dashboard_markup(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        types.InlineKeyboardButton("⚙️ Settings", callback_data="gm_settings"),
        types.InlineKeyboardButton("🛠 Commands Help", callback_data="gm_help")
    )
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="gm_close"))
    return markup

def get_settings_markup(chat_id):
    data = get_group_data(chat_id)
    toggles = data['toggles']
    
    icon_link = "✅" if toggles['antilink'] else "❌"
    icon_wel = "✅" if toggles['welcome'] else "❌"
    icon_svc = "✅" if toggles['service'] else "❌"

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(f"{icon_link} Anti-Link", callback_data="toggle_antilink"),
        types.InlineKeyboardButton(f"{icon_wel} Welcome Msg", callback_data="toggle_welcome")
    )
    markup.add(types.InlineKeyboardButton(f"{icon_svc} Del Join/Left Msg", callback_data="toggle_service"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="open_management"))
    return markup

# ---------------------------------------------
# 4. LOGIC HANDLERS
# ---------------------------------------------

def send_welcome_message(message, bot):
    chat_id = message.chat.id
    data = get_group_data(chat_id)
    if data['toggles']['welcome']:
        for new_member in message.new_chat_members:
            if new_member.is_bot: continue
            raw_text = data['texts']['welcome']
            final_text = format_text(raw_text, user=new_member, chat_title=message.chat.title)
            try: bot.send_message(chat_id, final_text)
            except: pass

def check_antilink(message, bot):
    chat_id = message.chat.id
    data = get_group_data(chat_id)
    if data['toggles']['antilink']:
        if is_user_group_admin(bot, chat_id, message.from_user.id): return
        entities = message.entities or []
        for entity in entities:
            if entity.type in ['url', 'text_link', 'mention']:
                try: 
                    bot.delete_message(chat_id, message.message_id)
                    return 
                except: pass

def check_banned_words(message, bot):
    chat_id = message.chat.id
    data = get_group_data(chat_id)
    
    if not data['banwords']: return
    if is_user_group_admin(bot, chat_id, message.from_user.id): return

    # Regex ব্যবহার করে Whole Word Check
    # \b মানে Word Boundary (শব্দের শুরু বা শেষ)
    for word in data['banwords']:
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, message.text, re.IGNORECASE):
            try:
                bot.delete_message(chat_id, message.message_id)
                return 
            except: pass

def delete_service_message(message, bot):
    chat_id = message.chat.id
    data = get_group_data(chat_id)
    if data['toggles']['service']:
        try: bot.delete_message(chat_id, message.message_id)
        except: pass

# --- COMMAND HANDLERS ---

def perform_action(message, bot, action_type):
    if not is_user_group_admin(bot, message.chat.id, message.from_user.id): return
    if not message.reply_to_message:
        bot.reply_to(message, f"⚠️ রিপ্লাই দিয়ে কমান্ড দিন।")
        return

    target_user = message.reply_to_message.from_user
    chat_id = message.chat.id
    msg_id = message.reply_to_message.message_id

    try:
        if action_type == 'ban':
            bot.ban_chat_member(chat_id, target_user.id)
        elif action_type == 'mute':
            bot.restrict_chat_member(chat_id, target_user.id, can_send_messages=False, until_date=time.time()+3600)
        elif action_type == 'unmute':
            bot.restrict_chat_member(chat_id, target_user.id, can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
        elif action_type == 'pin':
            bot.pin_chat_message(chat_id, msg_id)
        elif action_type == 'unpin':
            bot.unpin_chat_message(chat_id, msg_id)

        raw_text = get_text(chat_id, action_type)
        final_text = format_text(raw_text, user=target_user, chat_title=message.chat.title)
        bot.send_message(chat_id, final_text)

    except Exception as e:
        bot.reply_to(message, f"❌ ফেইলড: {e}")

def set_text_handler(message, bot, key):
    if not is_user_group_admin(bot, message.chat.id, message.from_user.id): return
    try:
        custom_text = message.text.split(maxsplit=1)[1]
        set_custom_text(message.chat.id, key, custom_text)
        bot.reply_to(message, f"✅ **{key.upper()}** মেসেজ আপডেট করা হয়েছে!")
    except IndexError:
        bot.reply_to(message, f"⚠️ লিখুন: `/set{key} মেসেজ...`")

# --- BAN WORD COMMANDS ---

def handle_banwords_command(message, bot, action):
    if not is_user_group_admin(bot, message.chat.id, message.from_user.id):
        bot.reply_to(message, "⚠️ এডমিন অনলি!")
        return

    data = get_group_data(message.chat.id)
    try:
        word = message.text.split(maxsplit=1)[1].lower()
        
        if action == 'add':
            if word not in data['banwords']:
                data['banwords'].append(word)
                bot.reply_to(message, f"✅ '{word}' ব্যান লিস্টে যোগ করা হয়েছে।")
            else:
                bot.reply_to(message, "⚠️ শব্দটি ইতিমধ্যে আছে।")
                
        elif action == 'remove':
            if word in data['banwords']:
                data['banwords'].remove(word)
                bot.reply_to(message, f"✅ '{word}' রিমুভ করা হয়েছে।")
            else:
                bot.reply_to(message, "⚠️ শব্দটি পাওয়া যায়নি।")
                
    except IndexError:
        bot.reply_to(message, f"⚠️ লিখুন: `/{'addword' if action=='add' else 'delword'} <word>`")

def handle_view_banlist(message, bot):
    if not is_user_group_admin(bot, message.chat.id, message.from_user.id): return
    
    data = get_group_data(message.chat.id)
    if not data['banwords']:
        bot.reply_to(message, "📂 ব্যান ওয়ার্ড লিস্ট খালি।")
        return
        
    # সুন্দর করে লিস্ট দেখানো
    words_str = ", ".join([f"`{w}`" for w in data['banwords']])
    bot.reply_to(message, f"🚫 **Banned Words List:**\n\n{words_str}", parse_mode="Markdown")

# ---------------------------------------------
# 5. REGISTRATION
# ---------------------------------------------
def register_group_management_handlers(bot: TeleBot):
    
    # UI Callbacks
    @bot.callback_query_handler(func=lambda c: c.data == "open_management")
    def _open(c):
        if c.message.chat.type == 'private': return
        if is_user_group_admin(bot, c.message.chat.id, c.from_user.id):
            bot.edit_message_text("🛡️ **Group Management**", c.message.chat.id, c.message.message_id, reply_markup=get_dashboard_markup(c.message.chat.id))

    @bot.callback_query_handler(func=lambda c: c.data == "gm_settings")
    def _set(c):
        if is_user_group_admin(bot, c.message.chat.id, c.from_user.id):
            bot.edit_message_text("⚙️ **Settings**", c.message.chat.id, c.message.message_id, reply_markup=get_settings_markup(c.message.chat.id))

    @bot.callback_query_handler(func=lambda c: c.data.startswith("toggle_"))
    def _tog(c):
        if is_user_group_admin(bot, c.message.chat.id, c.from_user.id):
            toggle_setting(c.message.chat.id, c.data.split("_")[1])
            try: bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=get_settings_markup(c.message.chat.id))
            except: pass

    @bot.callback_query_handler(func=lambda c: c.data == "gm_help")
    def _help(c):
        msg = (
            "📝 **Commands:**\n"
            "• `/setwelcome`, `/setban`, `/setmute`...\n"
            "• `/addword <word>` - শব্দ ব্যান করুন\n"
            "• `/delword <word>` - শব্দ রিমুভ করুন\n"
            "• `/banlist` - ব্যান লিস্ট দেখুন\n"
        )
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="open_management"))
        bot.edit_message_text(msg, c.message.chat.id, c.message.message_id, parse_mode="Markdown", reply_markup=mk)

    @bot.callback_query_handler(func=lambda c: c.data == "gm_close")
    def _close(c):
        bot.delete_message(c.message.chat.id, c.message.message_id)

    # Actions
    @bot.message_handler(commands=['ban'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def h_ban(m): perform_action(m, bot, 'ban')

    @bot.message_handler(commands=['mute'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def h_mute(m): perform_action(m, bot, 'mute')

    @bot.message_handler(commands=['unmute'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def h_unmute(m): perform_action(m, bot, 'unmute')

    @bot.message_handler(commands=['pin'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def h_pin(m): perform_action(m, bot, 'pin')

    @bot.message_handler(commands=['unpin'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def h_unpin(m): perform_action(m, bot, 'unpin')

    # Text Settings
    @bot.message_handler(commands=['setwelcome'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_wel(m): set_text_handler(m, bot, 'welcome')

    @bot.message_handler(commands=['setban'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_ban(m): set_text_handler(m, bot, 'ban')

    @bot.message_handler(commands=['setmute'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_mute(m): set_text_handler(m, bot, 'mute')
    
    @bot.message_handler(commands=['setunmute'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_unmute(m): set_text_handler(m, bot, 'unmute')

    @bot.message_handler(commands=['setpin'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_pin(m): set_text_handler(m, bot, 'pin')

    @bot.message_handler(commands=['setunpin'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def s_unpin(m): set_text_handler(m, bot, 'unpin')

    # Ban Words
    @bot.message_handler(commands=['addword'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_add(m): handle_banwords_command(m, bot, 'add')

    @bot.message_handler(commands=['delword'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_del(m): handle_banwords_command(m, bot, 'remove')

    @bot.message_handler(commands=['banlist'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def cmd_list(m): handle_view_banlist(m, bot)

    # Listeners
    @bot.message_handler(content_types=['text', 'caption'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def handle_msg(m):
        if not m.text.startswith('/'):
            check_antilink(m, bot)
            check_banned_words(m, bot)

    @bot.message_handler(content_types=['new_chat_members', 'left_chat_member'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def handle_svc(m):
        if m.new_chat_members:
            send_welcome_message(m, bot)
            delete_service_message(m, bot)
        elif m.left_chat_member:
            delete_service_message(m, bot)
