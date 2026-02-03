import asyncio
from telebot import types
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

# ✅ আমাদের তৈরি করা DB Manager ইমপোর্ট
try:
    from utils.db_manager import get_full_config, save_full_config
except ImportError:
    print("Error: utils/db_manager.py missing")

# টেম্পোরারি স্টোরেজ (লগইন প্রসেস চলাকালীন ডাটা রাখার জন্য)
temp_login_data = {}

def register_handlers(bot):
    
    # ১. কানেক্ট বাটন হ্যান্ডলার
    @bot.callback_query_handler(func=lambda c: c.data == "connect_userbot")
    def start_connect(call):
        msg = bot.send_message(call.message.chat.id, "Please send your **API ID**:\n(Get it from my.telegram.org)", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_api_id, bot)

    def process_api_id(message, bot):
        api_id = message.text.strip()
        if not api_id.isdigit():
            bot.send_message(message.chat.id, "❌ Invalid API ID. Please try again.")
            return
        
        temp_login_data[message.chat.id] = {"api_id": int(api_id)}
        msg = bot.send_message(message.chat.id, "Great! Now send your **API HASH**:")
        bot.register_next_step_handler(msg, process_api_hash, bot)

    def process_api_hash(message, bot):
        api_hash = message.text.strip()
        temp_login_data[message.chat.id]["api_hash"] = api_hash
        
        msg = bot.send_message(message.chat.id, "Now send your **Phone Number** (with country code, e.g., +88017...):")
        bot.register_next_step_handler(msg, process_phone, bot)

    def process_phone(message, bot):
        phone = message.text.strip()
        temp_login_data[message.chat.id]["phone"] = phone
        
        msg = bot.send_message(message.chat.id, "🔄 Sending OTP... Please wait.")
        
        # Asyncio লুপে টেলিথন চালানো
        asyncio.run(send_otp(message.chat.id, bot, msg))

    async def send_otp(chat_id, bot, status_msg):
        data = temp_login_data.get(chat_id)
        if not data: return

        client = TelegramClient(StringSession(), data["api_id"], data["api_hash"])
        await client.connect()
        
        if not await client.is_user_authorized():
            try:
                phone_code_hash = await client.send_code_request(data["phone"])
                data["client"] = client  # ক্লায়েন্ট অবজেক্ট টেম্পোরারি সেভ (মেমোরিতে)
                data["phone_code_hash"] = phone_code_hash.phone_code_hash
                
                bot.edit_message_text("✅ OTP Sent! Please enter the OTP (format: `1 2 3 4 5` with spaces or normally):", chat_id, status_msg.message_id)
                bot.register_next_step_handler(status_msg, process_otp, bot, client)
            except Exception as e:
                bot.edit_message_text(f"❌ Error sending OTP: {e}", chat_id, status_msg.message_id)
        else:
            bot.edit_message_text("✅ Already authorized!", chat_id, status_msg.message_id)

    def process_otp(message, bot, client):
        otp = message.text.replace(" ", "")
        chat_id = message.chat.id
        
        asyncio.run(authorize_user(chat_id, otp, bot, client))

    async def authorize_user(chat_id, otp, bot, client):
        data = temp_login_data.get(chat_id)
        try:
            await client.sign_in(data["phone"], otp, phone_code_hash=data["phone_code_hash"])
            
            # ✅ লগইন সফল! সেশন সেভ করা হচ্ছে
            session_string = client.session.save()
            save_session_to_db(chat_id, data["api_id"], data["api_hash"], session_string)
            
            await client.disconnect()
            bot.send_message(chat_id, "✅ **Login Successful!**\nUserbot connected.\nNow go to /start > Userbot Tools.")
            
        except SessionPasswordNeededError:
            msg = bot.send_message(chat_id, "🔐 Two-Step Verification enabled. Please send your **Password**:")
            bot.register_next_step_handler(msg, process_password, bot, client)
        except Exception as e:
            bot.send_message(chat_id, f"❌ Login Failed: {e}")

    def process_password(message, bot, client):
        password = message.text
        chat_id = message.chat.id
        asyncio.run(authorize_with_password(chat_id, password, bot, client))

    async def authorize_with_password(chat_id, password, bot, client):
        data = temp_login_data.get(chat_id)
        try:
            await client.sign_in(password=password)
            
            # ✅ লগইন সফল! সেশন সেভ করা হচ্ছে
            session_string = client.session.save()
            save_session_to_db(chat_id, data["api_id"], data["api_hash"], session_string)
            
            await client.disconnect()
            bot.send_message(chat_id, "✅ **Login Successful!**\nUserbot connected.\nNow go to /start > Userbot Tools.")
        except Exception as e:
            bot.send_message(chat_id, f"❌ Login Failed (Password): {e}")

def save_session_to_db(user_id, api_id, api_hash, session_string):
    """আমাদের db_manager ব্যবহার করে MongoDB তে সেভ করা"""
    all_data = get_full_config()
    
    # নতুন ইউজার ডাটা স্ট্রাকচার
    all_data[str(user_id)] = {
        "api_id": api_id,
        "api_hash": api_hash,
        "session_string": session_string, # স্ট্যান্ডার্ড নাম
        "tasks": {} # ডিফল্ট খালি টাস্ক লিস্ট
    }
    
    save_full_config(all_data)
