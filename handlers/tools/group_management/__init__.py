from .commands import register_commands
from .callbacks import register_callbacks
from .logic import check_all_messages, format_text
from .data import get_data, group_data

def register_group_management_handlers(bot):
    
    # ১. কমান্ড এবং কলব্যাক রেজিস্টার করা
    register_commands(bot)
    register_callbacks(bot)
    
    # ২. গ্লোবাল মেসেজ লিসেনার (Anti-link, filters etc এর জন্য)
    @bot.message_handler(content_types=['text', 'caption', 'sticker', 'voice', 'photo', 'video'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def global_message_check(message):
        # কমান্ড হলে চেক করার দরকার নেই
        if message.text and message.text.startswith('/'):
            return
        check_all_messages(bot, message)

    # ৩. ওয়েলকাম মেসেজ
    @bot.message_handler(content_types=['new_chat_members'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def on_join(message):
        data = get_data(message.chat.id)
        if data['toggles']['welcome']:
            for member in message.new_chat_members:
                if not member.is_bot:
                    txt = format_text(data['texts']['welcome'], user=member, chat_title=message.chat.title)
                    try: bot.send_message(message.chat.id, txt)
                    except: pass
        
        # সার্ভিস মেসেজ ডিলিট
        if data['toggles']['service']:
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
            
    # ৪. লিভ মেসেজ ডিলিট
    @bot.message_handler(content_types=['left_chat_member'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def on_leave(message):
        data = get_data(message.chat.id)
        if data['toggles']['service']:
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
