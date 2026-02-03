import telebot
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils import load_users

def register_broadcast_handlers(bot):

    # 1. Ask for the Message (Entry Point)
    @bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast")
    def ask_broadcast(call):
        msg = bot.send_message(
            call.message.chat.id, 
            "📢 <b>Broadcast Mode</b>\n\n"
            "Send the message (Text, Photo, Video, Sticker, etc.) you want to send to ALL users.\n\n"
            "<i>Type /cancel to stop.</i>"
        )
        bot.register_next_step_handler(msg, review_broadcast, bot)

    # 2. Preview Step
    def review_broadcast(message, bot):
        # Lazy import to avoid circular error
        from handlers.admin_panel import send_admin_panel
        
        if message.text == "/cancel":
            bot.send_message(message.chat.id, "❌ Broadcast Cancelled.")
            send_admin_panel(bot, message.chat.id)
            return

        users = load_users()
        count = len(users)

        kb = InlineKeyboardMarkup()
        # We attach the message_id to the button data to copy it later
        kb.add(
            InlineKeyboardButton(f"✅ Send to {count} Users", callback_data=f"do_cast_{message.message_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="adm_home")
        )

        bot.send_message(message.chat.id, "👇 <b>PREVIEW (Check below):</b>")
        try:
            bot.copy_message(message.chat.id, message.chat.id, message.message_id)
        except:
            bot.send_message(message.chat.id, "⚠️ Error generating preview, but sending might still work.")

        bot.send_message(
            message.chat.id, 
            f"👆 <b>Ready to Broadcast?</b>\nTarget: {count} users.", 
            reply_markup=kb
        )

    # 3. Execution Loop
    @bot.callback_query_handler(func=lambda c: c.data.startswith("do_cast_"))
    def execute_broadcast(call):
        from handlers.admin_panel import send_admin_panel

        try:
            msg_id = int(call.data.split("_")[2])
        except:
            bot.answer_callback_query(call.id, "❌ Error finding message.")
            return

        admin_chat_id = call.message.chat.id
        users = load_users()
        
        sent = 0
        failed = 0
        
        status_msg = bot.edit_message_text(
            f"🚀 <b>Broadcasting...</b>\n0/{len(users)}",
            chat_id=admin_chat_id,
            message_id=call.message.message_id
        )

        for i, user_id in enumerate(users.keys()):
            try:
                bot.copy_message(chat_id=user_id, from_chat_id=admin_chat_id, message_id=msg_id)
                sent += 1
            except:
                failed += 1
            
            time.sleep(0.05) # Anti-flood delay
            
            # Update status every 10 users
            if i % 10 == 0:
                try:
                    bot.edit_message_text(
                        f"🚀 <b>Broadcasting...</b>\n{i}/{len(users)}\n✅ {sent} ❌ {failed}",
                        chat_id=admin_chat_id,
                        message_id=status_msg.message_id
                    )
                except: pass

        bot.edit_message_text(
            f"✅ <b>Broadcast Complete!</b>\n\n"
            f"🎯 <b>Total:</b> {len(users)}\n"
            f"✅ <b>Success:</b> {sent}\n"
            f"🚫 <b>Blocked/Failed:</b> {failed}",
            chat_id=admin_chat_id,
            message_id=status_msg.message_id
        )
        
        time.sleep(2)
        send_admin_panel(bot, admin_chat_id)
