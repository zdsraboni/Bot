import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils_shop import update_order_status, approve_access

def register_order_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ord_pay_ok_"))
    def approve_order(call):
        parts = call.data.split("_")
        shop_id = parts[3]
        order_id = "_".join(parts[4:])
        
        order = update_order_status(shop_id, order_id, "paid")
        
        if order:
            bot.answer_callback_query(call.id, "✅ Order Approved!")
            bot.edit_message_caption(caption=call.message.caption + "\n\n✅ <b>STATUS: PAID</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
            
            # --- AUTO MEMBERSHIP GRANT ---
            if order.get("type") == "subscription":
                approve_access(shop_id, order['buyer_id'])
                try:
                    bot.send_message(order['buyer_id'], f"🎉 <b>Membership Approved!</b>\nYou now have access to the shop.", parse_mode="HTML")
                except: pass
            else:
                # Regular Product
                try:
                    bot.send_message(order['buyer_id'], f"🎉 <b>Payment Accepted!</b>\nYour order for <b>{order['item']}</b> is confirmed.", parse_mode="HTML")
                except: pass
        else:
            bot.answer_callback_query(call.id, "Error updating.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ord_pay_no_"))
    def reject_order(call):
        parts = call.data.split("_")
        shop_id = parts[3]
        order_id = "_".join(parts[4:])
        
        order = update_order_status(shop_id, order_id, "rejected")
        
        if order:
            bot.answer_callback_query(call.id, "❌ Order Rejected.")
            bot.edit_message_caption(caption=call.message.caption + "\n\n❌ <b>STATUS: REJECTED</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
            
            try:
                bot.send_message(order['buyer_id'], f"❌ <b>Payment Rejected</b>\nYour order for <b>{order['item']}</b> was declined.", parse_mode="HTML")
            except: pass
