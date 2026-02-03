import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils_shop import get_shop_analytics

def register_analytics_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "shop_analytics_menu")
    def show_analytics(call):
        stats = get_shop_analytics(call.from_user.id)
        if not stats:
            bot.answer_callback_query(call.id, "No data available.")
            return
            
        text = (
            f"📊 <b>Shop Analytics</b>\n\n"
            f"💰 <b>Total Revenue:</b> {stats['revenue']} BDT\n"
            f"📦 <b>Orders:</b> {stats['total_orders']}\n"
            f"   ├ ✅ Paid: {stats['paid']}\n"
            f"   ├ ⏳ Pending: {stats['pending']}\n"
            f"   └ ❌ Rejected: {stats['rejected']}\n\n"
            f"👥 <b>Members:</b> {stats['members']}\n"
            f"🛍️ <b>Products:</b> {stats['total_products']}\n\n"
            f"🏆 <b>Top Item:</b> {stats['best_seller']}"
        )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔄 Refresh", callback_data="shop_analytics_menu"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="my_business"))
        
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb, parse_mode="HTML")
        except: bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
