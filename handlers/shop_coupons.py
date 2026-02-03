import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils_shop import create_coupon, delete_coupon, get_coupons

coupon_cache = {}

def register_coupon_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "shop_coupon_menu")
    def coupon_menu(call):
        show_coupon_menu(bot, call.message.chat.id, call.from_user.id, call.message.message_id)

    def show_coupon_menu(bot, chat_id, user_id, message_id=None):
        coupons = get_coupons(user_id)
        kb = InlineKeyboardMarkup(row_width=1)
        for code, data in coupons.items():
            val = f"{data['value']}%" if data['type'] == 'percent' else f"${data['value']}"
            kb.add(InlineKeyboardButton(f"🗑️ {code} ({val})", callback_data=f"del_coup_{code}"))
        kb.add(InlineKeyboardButton("➕ Create Coupon", callback_data="add_coupon_start"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="my_business"))
        text = f"🎫 <b>Manage Coupons</b>\nYou have {len(coupons)} active coupons."
        try: bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=kb, parse_mode="HTML")
        except: bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("del_coup_"))
    def delete_handler(call):
        code = call.data.replace("del_coup_", "")
        delete_coupon(call.from_user.id, code)
        bot.answer_callback_query(call.id, "Deleted!")
        show_coupon_menu(bot, call.message.chat.id, call.from_user.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "add_coupon_start")
    def start_add(call):
        msg = bot.send_message(call.message.chat.id, "🎫 <b>Step 1/3:</b> Send Coupon Code (e.g. SALE10)")
        bot.register_next_step_handler(msg, process_code, bot)

    def process_code(message, bot):
        code = message.text.upper().strip()
        coupon_cache[message.from_user.id] = {'code': code}
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("Percent (%)", callback_data="coup_type_percent"), InlineKeyboardButton("Flat Amount ($)", callback_data="coup_type_flat"))
        bot.send_message(message.chat.id, "🎫 <b>Step 2/3:</b> Choose Discount Type:", reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("coup_type_"))
    def type_handler(call):
        ctype = call.data.replace("coup_type_", "")
        if call.from_user.id in coupon_cache:
            coupon_cache[call.from_user.id]['type'] = ctype
            msg = bot.send_message(call.message.chat.id, "🎫 <b>Step 3/3:</b> Enter Value (e.g. 10 or 50):")
            bot.register_next_step_handler(msg, process_value, bot)

    def process_value(message, bot):
        user_id = message.from_user.id
        data = coupon_cache.get(user_id)
        if not data: return
        try:
            val = float(message.text.strip())
            create_coupon(user_id, data['code'], data['type'], val)
            bot.send_message(message.chat.id, f"✅ Coupon <b>{data['code']}</b> created!")
            show_coupon_menu(bot, message.chat.id, user_id, None)
        except: bot.send_message(message.chat.id, "❌ Invalid number.")
