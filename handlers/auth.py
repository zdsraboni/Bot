import telebot
from config import ADMIN_PASSWORD
from utils.utils import add_admin, is_admin

def register_auth_handlers(bot):
    @bot.message_handler(commands=['admin_login'])
    def login(message):
        user_id = message.from_user.id
        text = message.text.split()
        
        if is_admin(user_id):
            bot.reply_to(message, "✅ You are already an Admin.")
            return

        if len(text) < 2:
            bot.reply_to(message, "⚠️ Usage: `/admin_login PASSWORD`")
            return
            
        if text[1] == ADMIN_PASSWORD:
            # --- PASS CUSTOM COMMIT MESSAGE ---
            if add_admin(user_id, bot=bot, commit_msg="New Admin Added"):
                bot.reply_to(message, "🎉 <b>Success!</b> You are now an Admin.")
            else:
                bot.reply_to(message, "❌ Error.")
        else:
            bot.reply_to(message, "⛔ Wrong Password.")
