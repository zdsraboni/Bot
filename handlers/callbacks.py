import telebot
from telebot import types
import traceback

# =========================================================
# 👇 TOOL REGISTRY & IMPORTS
# =========================================================
tool_registry = {}

# 1. Group Management Dispatcher Import
try:
    from handlers.tools.group_management.callbacks import handle_group_callbacks
except ImportError:
    handle_group_callbacks = None

# 2. URL Tool Import
try:
    from handlers.tools.url_shorten.core import open_url_tool
    tool_registry['tool_url_shortener'] = lambda bot, call: open_url_tool(bot, call.message, is_edit=True)
except ImportError: pass

# 3. Menu Import
try:
    from keyboards.main_menu import main_menu, tools_layout
except ImportError:
    def main_menu(uid): return None
    def tools_layout(): return "⚠️ Menu Error", None

# =========================================================
# 🎮 CALLBACK HANDLER (STABLE & DYNAMIC)
# =========================================================
def register_callbacks(bot):

    # 🛡️ FILTER: ওয়াটারমার্ক (wm_) এবং ইউআরএল (url_) বাদে বাকি সব হ্যান্ডেল করবে।
    # tool_img কেও বাদ দেওয়া হয়েছে কারণ এটি watermark/core.py হ্যান্ডেল করবে।
    @bot.callback_query_handler(func=lambda call: not (
        call.data.startswith("wm_") or 
        call.data.startswith("url_") or 
        call.data == "tool_img"
    ))
    def handle_global_callbacks(call):
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        data = call.data

        try:
            # 🚨 ১. গ্রুপ ম্যানেজমেন্ট ডিসপ্যাচার (gm_, tog_, tool_tog_)
            if data.startswith(("gm_", "tog_", "tool_tog_", "open_management")):
                if handle_group_callbacks:
                    # answer_callback_query এখানে দিচ্ছি না, হ্যান্ডলার নিজেই দিবে
                    handle_group_callbacks(bot, call)
                else:
                    bot.answer_callback_query(call.id, "⚠️ Module not loaded.", show_alert=True)
                return

            # ২. অন্যান্য রেজিস্টার্ড টুল (URL)
            if data in tool_registry:
                bot.answer_callback_query(call.id)
                tool_registry[data](bot, call)
                return

            # 🛠 ৩. TOOLS MENU NAVIGATION
            if data in ["tools", "back_to_tools"]:
                bot.answer_callback_query(call.id)
                text, kb = tools_layout()
                if kb:
                    if call.message.content_type == 'text':
                        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=kb, parse_mode="Markdown")
                    else:
                        bot.delete_message(chat_id, message_id)
                        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
                else:
                    bot.answer_callback_query(call.id, "⚠️ Menu Error", show_alert=True)
                return

            # 🏠 ৪. MAIN MENU RETURN
            if data == "main_menu_return":
                bot.answer_callback_query(call.id)
                kb = main_menu(call.from_user.id)
                if kb:
                    if call.message.content_type == 'text':
                        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🏠 **Main Menu**\n\nChoose an option below:", reply_markup=kb, parse_mode="Markdown")
                    else:
                        bot.delete_message(chat_id, message_id)
                        bot.send_message(chat_id, "🏠 **Main Menu**\n\nChoose an option below:", reply_markup=kb, parse_mode="Markdown")
                else:
                    bot.delete_message(chat_id, message_id)
                    from handlers.start import send_welcome
                    send_welcome(bot, call.message)
                return

            # ৫. অন্যান্য ফিক্সড ইনফো পপ-আপস
            if data == "tool_weather":
                bot.answer_callback_query(call.id, "ℹ️ Use /weather <city>", show_alert=True)
                return

            if data == "close":
                bot.delete_message(chat_id, message_id)
                return

            # ৬. Unknown Action Catch (Optional)
            # bot.answer_callback_query(call.id, "⚠️ Unknown action.")

        except Exception as e:
            print(f"Callback Error: {e}")
            traceback.print_exc()
            try: bot.answer_callback_query(call.id, "❌ Error")
            except: pass
