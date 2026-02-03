import time
import re
from .data import get_data, reset_warns
from .utils import is_admin, format_text

# --- Actions (Ban/Mute/Unmute/Kick) ---
def perform_action(bot, chat_id, target_user, action_type, message=None):
    try:
        data = get_data(chat_id)
        txt_key = None
        
        if action_type == 'ban':
            bot.ban_chat_member(chat_id, target_user.id)
            txt_key = 'ban'
        
        elif action_type == 'mute':
            # 1 ঘন্টার জন্য মিউট
            bot.restrict_chat_member(chat_id, target_user.id, can_send_messages=False, until_date=time.time()+3600)
            txt_key = 'mute'
            
        elif action_type == 'unmute':
            # সব পারমিশন ফেরত দেওয়া
            bot.restrict_chat_member(
                chat_id, target_user.id,
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
            txt_key = 'unmute'
            
        elif action_type == 'kick':
            bot.unban_chat_member(chat_id, target_user.id)
            # Kick এর জন্য আমরা কোনো টেক্সট মেসেজ রাখিনি, চাইলে এড করতে পারেন
            return

        # মেসেজ পাঠানো
        if message and txt_key:
            raw = data['texts'].get(txt_key, f"Action {action_type} executed.")
            final = format_text(raw, user=target_user, chat_title=message.chat.title)
            bot.send_message(chat_id, final)
            
    except Exception as e:
        if message: bot.reply_to(message, f"❌ Failed: {e}")

# --- Warning System ---
def handle_warning(bot, message, target_user):
    chat_id = message.chat.id
    data = get_data(chat_id)
    
    current = data['warns'].get(target_user.id, 0) + 1
    data['warns'][target_user.id] = current
    limit = data['warn_settings']['limit']
    
    if current >= limit:
        action = data['warn_settings']['action']
        perform_action(bot, chat_id, target_user, action, message)
        bot.send_message(chat_id, f"🛑 **Warning Limit Reached!** Action: {action.upper()}", parse_mode="Markdown")
        reset_warns(chat_id, target_user.id)
    else:
        raw = data['texts']['warn']
        final = format_text(raw, user=target_user, warn_count=current, warn_limit=limit)
        bot.send_message(chat_id, final)

# --- Filters & Checks ---
def check_all_messages(bot, message):
    chat_id = message.chat.id
    data = get_data(chat_id)
    user_id = message.from_user.id
    
    if is_admin(bot, chat_id, user_id): return

    # 1. Anti-Link
    if data['toggles']['antilink']:
        for entity in (message.entities or []):
            if entity.type in ['url', 'text_link', 'mention']:
                bot.delete_message(chat_id, message.message_id)
                return

    # 2. Ban Words (Whole Word Regex)
    if data['banwords']:
        text_lower = (message.text or message.caption or "").lower()
        for word in data['banwords']:
            if re.search(r"\b" + re.escape(word) + r"\b", text_lower):
                bot.delete_message(chat_id, message.message_id)
                return

    # 3. Media Filters
    content_type = message.content_type
    if content_type == 'sticker' and data['toggles']['block_sticker']:
        bot.delete_message(chat_id, message.message_id)
    elif content_type == 'voice' and data['toggles']['block_voice']:
        bot.delete_message(chat_id, message.message_id)
