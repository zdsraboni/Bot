def is_admin(bot, chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

def format_text(text, user=None, chat_title=None, warn_count=0, warn_limit=3):
    if user:
        text = text.replace("{name}", user.first_name)
        text = text.replace("{username}", f"@{user.username}" if user.username else "No Username")
        text = text.replace("{id}", str(user.id))
    if chat_title:
        text = text.replace("{chat_title}", chat_title)
    
    # ওয়ার্নিং ভেরিয়েবল
    text = text.replace("{count}", str(warn_count))
    text = text.replace("{limit}", str(warn_limit))
    return text
