import os
import importlib.util
import asyncio
import threading
import time
from telebot import types

# ✅ মেনু প্যানেলের তথ্য (যাতে মেইন মেনু একে চিনতে পারে)
TOOL_INFO = {
    "label": "🛰 Userbot Tools",
    "callback": "gm_userbot"
}

# ✅ MongoDB Manager ইমপোর্ট
try:
    from utils.db_manager import get_full_config, save_full_config
except ImportError:
    print("Error: utils/db_manager.py missing in userbot_menu.py")

USERBOT_TASKS_DIR = "handlers/plugins/userbot_tasks"

def register_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "gm_userbot")
    def userbot_main_panel(call):
        # কলব্যাক লোডিং বন্ধ করা
        try:
            bot.answer_callback_query(call.id)
        except:
            pass

        u_id = str(call.from_user.id)
        all_data = get_full_config()
        u_data = all_data.get(u_id, {})

        mk = types.InlineKeyboardMarkup(row_width=1)

        if not u_data:
            # টেক্সট সিম্পল রাখা হয়েছে যাতে কোনো ইরোর না হয়
            text = "🛰 Userbot Manager\n\n❌ কোনো একাউন্ট কানেক্ট করা নেই।"
            mk.add(types.InlineKeyboardButton("➕ Connect Userbot", callback_data="connect_userbot"))
        else:
            api_id = u_data.get('api_id', 'N/A')
            # এখানে parse_mode সমস্যা এড়াতে সিম্পল টেক্সট ব্যবহার করা হলো
            text = f"🛰 Userbot Manager\n\n🆔 API ID: {api_id}\n\nনিচ থেকে টাস্কগুলো ম্যানেজ করুন:"

            # ডাইনামিক টাস্ক স্ক্যানিং লজিক
            if os.path.exists(USERBOT_TASKS_DIR):
                for task_folder in os.listdir(USERBOT_TASKS_DIR):
                    folder_path = os.path.join(USERBOT_TASKS_DIR, task_folder)
                    if os.path.isdir(folder_path):
                        for filename in os.listdir(folder_path):
                            if filename.endswith(".py") and filename != "__init__.py":
                                try:
                                    # মডিউল লোড করা
                                    spec = importlib.util.spec_from_file_location("t_mod", os.path.join(folder_path, filename))
                                    mod = importlib.util.module_from_spec(spec)
                                    spec.loader.exec_module(mod)
                                    
                                    # বাটন জেনারেট করা
                                    if hasattr(mod, "TOOL_INFO"):
                                        is_on = u_data.get("tasks", {}).get(task_folder, False)
                                        status_icon = "🟢" if is_on else "🔴"
                                        next_act = "off" if is_on else "on"
                                        btn_text = f"{mod.TOOL_INFO['label']} [{status_icon}]"
                                        mk.add(types.InlineKeyboardButton(btn_text, callback_data=f"utog:{task_folder}:{next_act}"))
                                except:
                                    continue

            mk.add(types.InlineKeyboardButton("❌ Disconnect Userbot", callback_data="force_disconnect_ub"))
            mk.add(types.InlineKeyboardButton("🔄 Refresh List", callback_data="gm_userbot"))

        mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="gm_tools"))
        
        # ✅ FIX: parse_mode="Markdown" সরিয়ে দেওয়া হয়েছে। এটিই আপনার 'Can't parse entities' ইরোর ফিক্স করবে।
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=mk)
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=mk)

    @bot.callback_query_handler(func=lambda c: c.data == "force_disconnect_ub")
    def disconnect_logic(call):
        u_id = str(call.from_user.id)
        
        # ১. ডাটাবেস থেকে ডিলিট
        all_data = get_full_config()
        if u_id in all_data:
            del all_data[u_id]
            save_full_config(all_data)
        
        try:
            bot.answer_callback_query(call.id, "✅ সেশন রিসেট হয়েছে।")
        except:
            pass
        
        # ২. ডাটাবেস আপডেট হওয়ার জন্য সামান্য বিরতি
        time.sleep(0.5)
        
        # ৩. কানেক্ট বাটন ম্যানুয়ালি তৈরি করা (যাতে লোডিং এ না আটকায়)
        mk = types.InlineKeyboardMarkup(row_width=1)
        mk.add(types.InlineKeyboardButton("➕ Connect Userbot", callback_data="connect_userbot"))
        mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="gm_tools"))
        
        reset_text = "🛰 Userbot Manager\n\n❌ একাউন্ট ডিসকানেক্ট করা হয়েছে। আপনি এখন নতুন করে কানেক্ট করতে পারেন।"
        
        try:
            bot.edit_message_text(reset_text, call.message.chat.id, call.message.message_id, reply_markup=mk)
        except:
            bot.send_message(call.message.chat.id, reset_text, reply_markup=mk)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("utog:"))
    def toggle_task(call):
        u_id = str(call.from_user.id)
        all_data = get_full_config()
        
        try:
            _, task_id, next_action = call.data.split(":")
        except:
            return
            
        if u_id not in all_data:
            bot.answer_callback_query(call.id, "❌ একাউন্ট কানেক্ট নেই!")
            return
            
        # টাস্ক অন/অফ লজিক
        if "tasks" not in all_data[u_id]: 
            all_data[u_id]["tasks"] = {}
        all_data[u_id]["tasks"][task_id] = (next_action == "on")
        save_full_config(all_data)
        
        # ইঞ্জিন রিলোড (থ্রেডিং ব্যবহার করে)
        try:
            import main
            def run_reload():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(main.start_userbot_engine())
                loop.close()
                
            threading.Thread(target=run_reload, daemon=True).start()
            bot.answer_callback_query(call.id, "✅ সেটিংস আপডেট হচ্ছে...")
        except:
            bot.answer_callback_query(call.id, "✅ ডাটাবেসে সেভ হয়েছে।")
        
        # প্যানেল রিফ্রেশ
        userbot_main_panel(call)
