import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils_shop import get_shop, create_category, delete_category, get_categories

def register_category_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "shop_cat_menu")
    def category_menu(call):
        show_category_menu(bot, call.message.chat.id, call.from_user.id, message_id=call.message.message_id)

    def show_category_menu(bot, chat_id, user_id, message_id=None):
        cats = get_categories(user_id)
        kb = InlineKeyboardMarkup(row_width=1)
        for cid, name in cats.items():
            kb.add(InlineKeyboardButton(f"🗑️ Delete: {name}", callback_data=f"del_cat_{cid}"))
        kb.add(InlineKeyboardButton("➕ Create New Category", callback_data="add_new_cat"))
        kb.add(InlineKeyboardButton("🔙 Back to Dashboard", callback_data="my_business"))
        text = f"📂 <b>Manage Categories</b>\nYou have {len(cats)} categories."
        if message_id:
            try: bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=kb)
            except: bot.send_message(chat_id, text, reply_markup=kb)
        else: bot.send_message(chat_id, text, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "add_new_cat")
    def start_add_cat(call):
        msg = bot.send_message(call.message.chat.id, "📂 <b>Enter Category Name:</b>")
        bot.register_next_step_handler(msg, process_add_cat, bot)

    def process_add_cat(message, bot):
        if create_category(message.from_user.id, message.text):
            bot.send_message(message.chat.id, f"✅ Category '{message.text}' created!")
            show_category_menu(bot, message.chat.id, message.from_user.id, message_id=None)
        else: bot.send_message(message.chat.id, "❌ Error.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("del_cat_"))
    def process_del_cat(call):
        cat_id = call.data.replace("del_cat_", "")
        if delete_category(call.from_user.id, cat_id):
            bot.answer_callback_query(call.id, "✅ Deleted")
            show_category_menu(bot, call.message.chat.id, call.from_user.id, message_id=call.message.message_id)
        else: bot.answer_callback_query(call.id, "❌ Error")
