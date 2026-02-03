import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils_shop import get_shop, approve_access, deny_access, manual_add_buyer

def register_request_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "shop_req_menu")
    def request_menu(call):
        shop = get_shop(call.from_user.id)
        if not shop: return
        pending = shop.get("pending_requests", [])
        approved = shop.get("approved_users", [])
        text = f"👥 <b>Buyer Management</b>\n\n⏳ Pending Requests: {len(pending)}\n✅ Approved Buyers: {len(approved)}"
        kb = InlineKeyboardMarkup(row_width=1)
        if pending: kb.add(InlineKeyboardButton("🔔 View Pending Requests", callback_data="shop_view_pending"))
        kb.add(InlineKeyboardButton("📜 View Buyer List", callback_data="shop_view_buyers"))
        kb.add(InlineKeyboardButton("➕ Manually Add User", callback_data="shop_add_manual"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="my_business"))
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, text, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "shop_view_pending")
    def view_pending(call):
        shop = get_shop(call.from_user.id)
        pending = shop.get("pending_requests", [])
        if not pending:
            bot.answer_callback_query(call.id, "No pending requests.")
            return
        target_id = pending[0]
        info = shop.get("customers", {}).get(str(target_id), {})
        name = info.get('first_name', 'Unknown')
        username = f"@{info.get('username')}" if info.get('username') else "No Username"
        text = (f"🔔 <b>New Request</b>\n\n👤 <b>Name:</b> {name}\n🔗 <b>User:</b> {username}\n🆔 <b>ID:</b> <code>{target_id}</code>")
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"req_ok_{target_id}"), InlineKeyboardButton("❌ Deny", callback_data=f"req_no_{target_id}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="shop_req_menu"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("req_ok_"))
    def approve_handler(call):
        target_id = int(call.data.replace("req_ok_", ""))
        if approve_access(call.from_user.id, target_id):
            bot.answer_callback_query(call.id, "✅ Approved!")
            try: bot.send_message(target_id, "✅ <b>Access Granted!</b>")
            except: pass
            try: view_pending(call)
            except: pass
        else: bot.answer_callback_query(call.id, "Error.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("req_no_"))
    def deny_handler(call):
        target_id = int(call.data.replace("req_no_", ""))
        if deny_access(call.from_user.id, target_id):
            bot.answer_callback_query(call.id, "❌ Denied.")
            try: view_pending(call)
            except: pass

    @bot.callback_query_handler(func=lambda c: c.data == "shop_view_buyers")
    def view_buyers_list(call):
        shop = get_shop(call.from_user.id)
        approved = shop.get("approved_users", [])
        customers = shop.get("customers", {})
        if not approved:
            bot.answer_callback_query(call.id, "No approved buyers.")
            return
        msg = "📜 <b>Approved Buyers:</b>\n\n"
        count = 1
        for uid in approved:
            info = customers.get(str(uid), {})
            name = info.get('first_name', 'Unknown')
            username = info.get('username', 'None')
            msg += f"{count}. <b>{name}</b> (@{username}) - <code>{uid}</code>\n"
            count += 1
            if count > 20: 
                msg += "\n<i>...and more.</i>"
                break
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="shop_req_menu"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=msg, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "shop_add_manual")
    def start_manual_add(call):
        msg = bot.send_message(call.message.chat.id, "➕ <b>Add Buyer Manually</b>\nSend User ID:")
        bot.register_next_step_handler(msg, process_manual_add, bot)

    def process_manual_add(message, bot):
        try:
            target_id = int(message.text.strip())
            if manual_add_buyer(message.from_user.id, target_id):
                bot.reply_to(message, f"✅ User <code>{target_id}</code> approved!")
            else: bot.reply_to(message, "❌ Already approved or error.")
        except: bot.reply_to(message, "❌ Invalid ID.")
