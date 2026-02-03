import os
import sys
import asyncio
import logging
import json
import importlib.util
import time
import threading
import telebot
from telebot import apihelper

# =========================================================
# 🚀 0. SYSTEM ENVIRONMENT SETUP (FIX FOR FFmpeg)
# =========================================================
os.environ["IMAGEIO_FFMPEG_EXE"] = "/usr/bin/ffmpeg"

try:
    import imageio_ffmpeg
    print(f"DEBUG: FFmpeg found at -> {imageio_ffmpeg.get_ffmpeg_exe()}")
except ImportError:
    print("WARNING: imageio-ffmpeg wrapper not found in Python environment.")

# --- Telethon Imports for Userbot Support ---
try:
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError, AuthKeyUnregistered, UserDeactivatedBanError
    logger_ub = logging.getLogger("telethon")
    logger_ub.setLevel(logging.WARNING) 
except ImportError:
    print("ERROR: Telethon not found. Please run 'pip install telethon'")
    sys.exit(1)

# ✅ MongoDB Manager Import (ডাটাবেস কানেকশনের জন্য)
try:
    from utils.db_manager import get_full_config, save_full_config
except ImportError:
    print("WARNING: utils/db_manager.py not found. Please create it.")

# =========================================================
# ⚙️ 1. LOGGING & CONFIGURATION
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

try:
    from config import BOT_TOKEN, DATA_DIR, USERS_FILE, SHOPS_FILE, CUSTOM_FILE
    logger.info("✅ Loaded settings from config.py")
except ImportError:
    logger.warning("⚠️ config.py not found! Using Environment Variables & Defaults.")
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    DATA_DIR = "data"
    USERS_FILE = os.path.join(DATA_DIR, "users.json")
    SHOPS_FILE = os.path.join(DATA_DIR, "shops.json")
    CUSTOM_FILE = os.path.join(DATA_DIR, "custom.json")

USERBOT_SESSIONS_FILE = os.path.join(DATA_DIR, "userbot_sessions.json")

if not BOT_TOKEN:
    logger.error("❌ CRITICAL ERROR: BOT_TOKEN is missing!")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", use_class_middlewares=True)

# =========================================================
# 🛰️ 2. DYNAMIC USERBOT TASK MANAGER (Optimized)
# =========================================================
active_clients = {} # সচল ক্লায়েন্ট ট্র্যাক করার জন্য

def load_userbot_tasks_for_client(client, bot, user_id, user_config):
    task_base_path = "handlers/plugins/userbot_tasks"
    if not os.path.exists(task_base_path): 
        os.makedirs(task_base_path)
        return

    # ইউজারের সেভ করা টাস্ক কনফিগ
    user_tasks = user_config.get("tasks", {})

    # ফোল্ডার স্ক্যানিং লজিক
    for task_folder in os.listdir(task_base_path):
        folder_path = os.path.join(task_base_path, task_folder)
        
        if os.path.isdir(folder_path):
            # টাস্ক ফোল্ডারের নামই টাস্ক আইডি
            task_id = task_folder
            
            # যদি ইউজার টাস্কটি অন করে রাখে
            if user_tasks.get(task_id, False):
                # ফোল্ডারের ভেতরের ফাইল খোঁজা
                for filename in os.listdir(folder_path):
                    if filename.endswith(".py") and filename != "__init__.py":
                        file_path = os.path.join(folder_path, filename)
                        module_name = f"ub_task_{user_id}_{task_id}"
                        try:
                            spec = importlib.util.spec_from_file_location(module_name, file_path)
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            
                            if hasattr(module, "register_userbot_task"):
                                module.register_userbot_task(client, bot, user_id)
                                logger.info(f"   🤖 Active Task: [{task_id}] for User: {user_id}")
                        except Exception as e:
                            logger.error(f"   ❌ Failed to load Task {task_id}: {e}")

async def start_userbot_engine():
    """ডাটাবেস (MongoDB) থেকে সব সেশন ডাইনামিকালি চালু বা রিলোড করা"""
    logger.info("🔍 Checking Userbot Sessions from Database...")

    # ✅ MongoDB থেকে লেটেস্ট ডাটা নেওয়া
    try:
        sessions = get_full_config() 
    except Exception as e:
        logger.error(f"❌ Database Read Error: {e}")
        return

    if not sessions: 
        logger.info("ℹ️ No connected userbots found.")
        return

    for uid, data in list(sessions.items()):
        # ডাটা ভ্যালিডেশন
        api_id = data.get("api_id")
        api_hash = data.get("api_hash")
        session_str = data.get("session_string") # আপনার ডাটাবেস কি 'session' নাকি 'session_string' ব্যবহার করে তা নিশ্চিত হোন। সাধারণত 'session_string' স্ট্যান্ডার্ড।

        # যদি সেশন স্ট্রিং না থাকে
        if not session_str and 'session' in data:
             session_str = data['session']

        if not (api_id and api_hash and session_str):
            continue

        # যদি অলরেডি কানেক্টেড থাকে
        if uid in active_clients and active_clients[uid].is_connected():
            load_userbot_tasks_for_client(active_clients[uid], bot, uid, data)
            continue

        try:
            client = TelegramClient(StringSession(session_str), int(api_id), api_hash, sequential_updates=True)
            await client.connect()
            
            if await client.is_user_authorized():
                active_clients[uid] = client
                # টাস্ক লোড করা
                load_userbot_tasks_for_client(client, bot, uid, data)
                # ইভেন্ট লুপে রান করা
                asyncio.create_task(client.run_until_disconnected())
                logger.info(f"✅ Userbot Engine Started for User: {uid}")
            else:
                logger.warning(f"⚠️ User {uid} session is authorized no more. Removing from DB...")
                # সেশন নষ্ট হলে অটোমেটিক ক্লিন করা
                del sessions[uid]
                save_full_config(sessions)
                
        except (AuthKeyUnregistered, UserDeactivatedBanError) as e:
            logger.error(f"❌ Session Invalid for {uid}: {e}")
            del sessions[uid]
            save_full_config(sessions)
        except Exception as e:
            logger.error(f"❌ Userbot Startup Failed for {uid}: {e}")

# =========================================================
# 🛠 3. SYSTEM CHECK & AUTO-FIX
# =========================================================
def check_and_create_files():
    logger.info("🔍 Checking system files...")
    dirs = [DATA_DIR, "handlers/plugins", "handlers/plugins/userbot_tasks", os.path.join(DATA_DIR, "fonts")]
    for d in dirs:
        if not os.path.exists(d): os.makedirs(d)

    files_init = {
        USERS_FILE: {},
        SHOPS_FILE: {},
        CUSTOM_FILE: {"texts": {}, "banwords": [], "warns": {}, "tools_status": {}},
        USERBOT_SESSIONS_FILE: {}
    }

    for file_path, default_content in files_init.items():
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump(default_content, f)
    logger.info("✅ System check passed.")

# =========================================================
# 🔌 4. DYNAMIC PLUGIN LOADER
# =========================================================
def load_plugins(bot):
    plugin_base = "handlers/plugins"
    logger.info(f"🔌 Scanning plugins in {plugin_base}...")
    count = 0
    if not os.path.exists(plugin_base): return

    for root, dirs, files in os.walk(plugin_base):
        if "userbot_tasks" in root: continue

        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                relative_path = os.path.relpath(os.path.join(root, filename), ".")
                module_name = relative_path.replace(os.sep, ".")[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(module_name, os.path.join(root, filename))
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    if hasattr(module, "register_handlers"):
                        module.register_handlers(bot)
                        logger.info(f"   ✅ Loaded: {module_name}")
                        count += 1
                except Exception as e:
                    logger.error(f"   ❌ FAILED to load {module_name}: {e}")
    logger.info(f"🔌 Total Plugins Loaded: {count}")

# =========================================================
# 📥 5. HANDLERS REGISTRATION
# =========================================================
logger.info("📥 Loading core handlers...")

try:
    from handlers.start import register_start
    from handlers.auth import register_auth_handlers
    from handlers.admin_panel import register_admin_handlers
    from handlers.plugin_manager import register_plugin_handler
    from handlers.tools.url_shorten.core import register_url_handlers
    from handlers.tools.watermark.core import register_watermark_handlers
    from handlers.tools.group_management import register_group_management_handlers as register_group_tools 
    from handlers.broadcast import register_broadcast_handlers
    from handlers.shop_seller import register_seller_handlers
    from handlers.shop_buyer import register_buyer_handlers
    from handlers.shop_categories import register_category_handlers
    from handlers.shop_requests import register_request_handlers 
    from handlers.shop_social import register_social_handlers, post_product_to_channel
    from handlers.shop_coupons import register_coupon_handlers
    from handlers.shop_orders import register_order_handlers
    from handlers.shop_analytics import register_analytics_handlers
    from handlers.shop_cart import register_cart_handlers 
    from handlers.callbacks import register_callbacks
    from utils.utils_shop import get_and_clear_due_posts
except ImportError as e:
    logger.error(f"Core Import Error: {e}")
    # এখানে exit না করে কন্টিনিউ রাখা হয়েছে যাতে অন্তত বট রান করে
    # sys.exit(1)

# হ্যান্ডলার রেজিস্টার (সেফটি ব্লকের মধ্যে)
try:
    register_start(bot)
    register_auth_handlers(bot)
    register_admin_handlers(bot)
    register_plugin_handler(bot)
    load_plugins(bot) 
    register_url_handlers(bot)
    register_watermark_handlers(bot)
    register_group_tools(bot)
    register_broadcast_handlers(bot)
    register_seller_handlers(bot)
    register_buyer_handlers(bot)
    register_category_handlers(bot)
    register_request_handlers(bot)
    register_social_handlers(bot)
    register_coupon_handlers(bot)
    register_order_handlers(bot)
    register_analytics_handlers(bot)
    register_cart_handlers(bot)
    register_callbacks(bot)
    logger.info("✅ All handlers and plugins registered.")
except Exception as e:
    logger.error(f"❌ Error Registering Handlers: {e}")

# =========================================================
# ⏰ 6. SCHEDULER & MAIN RUNNER
# =========================================================
def scheduler_loop():
    while True:
        try:
            tasks = get_and_clear_due_posts()
            if tasks:
                for t in tasks:
                    try:
                        post_product_to_channel(bot, t['channel_id'], t['product'], t['shop_name'], None, bot.get_me().username)
                    except Exception as e:
                        logger.error(f"Scheduled post failed: {e}")
            time.sleep(60)
        except Exception as e:
            logger.error(f"Scheduler Error: {e}")
            time.sleep(60)

async def start_all():
    check_and_create_files()
    
    # ইউজারবট ইঞ্জিন স্টার্ট (অ্যাসিনক্রোনাস)
    logger.info("🚀 Starting Userbot Engine...")
    await start_userbot_engine()

    # মেইন বটের পোলিং ফাংশন
    def run_polling():
        logger.info("🤖 Bot is starting infinity polling...")
        bot.delete_webhook(drop_pending_updates=True)
        try:
            bot.infinity_polling(timeout=60, skip_pending=True)
        except Exception as e:
            logger.error(f"Polling Error: {e}")

    # থ্রেডিং ব্যবহার করে পোলিং রান করা (যাতে অ্যাসিনক্রোনাস টাস্ক ব্লক না হয়)
    polling_thread = threading.Thread(target=run_polling, daemon=True)
    polling_thread.start()
    
    # শিডিউলার থ্রেড
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()

    # মেইন ইভেন্ট লুপকে জীবিত রাখা
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    # রেলওয়ে সেশন ক্লিয়ারেন্সের জন্য ১০ সেকেন্ড বিরতি
    logger.info("⏳ Waiting 10 seconds for old session to clear...")
    time.sleep(10) 
    
    try:
        # উইন্ডোজ বা লিনাক্স এ লুপ পলিসি সেটআপ (যদি দরকার হয়)
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
        asyncio.run(start_all())
    except KeyboardInterrupt:
        logger.info("🛑 Bot Stopped.")
    except Exception as e:
        logger.error(f"❌ Critical Runtime Error: {e}")
