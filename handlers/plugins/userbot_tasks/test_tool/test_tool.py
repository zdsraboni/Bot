import logging
import time
from telethon import events

# =========================================================
# ✅ MENU CONFIGURATION
# =========================================================
# এই ইনফো ব্যবহার করে userbot_menu.py বাটন জেনারেট করে
TOOL_INFO = {
    "label": "🤖 Connection Tester (Ping)",
    "callback": "none"  # কলব্যাক হ্যান্ডলিং মেনু ফাইল নিজেই করবে
}

logger = logging.getLogger(__name__)

# =========================================================
# 🔌 MAIN REGISTRATION FUNCTION
# =========================================================
def register_userbot_task(client, bot, user_id):
    """
    এই ফাংশনটি main.py থেকে কল করা হয় যখন ইউজারবট ইঞ্জিন স্টার্ট হয়।
    :param client: Telethon Client (Userbot Session)
    :param bot: Main Bot Instance (Telebot)
    :param user_id: Owner User ID
    """
    
    # -----------------------------------------------------
    # 1. OUTGOING PING TEST (.test)
    # -----------------------------------------------------
    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.test$"))
    async def ping_handler(event):
        """
        নিজের চ্যাটে .test লিখলে পিং এবং সিস্টেম স্ট্যাটাস দেখাবে।
        """
        try:
            start_time = time.time()
            # এডিট করে রেসপন্স চেক করা
            msg = await event.edit("📡 **Ping...**")
            end_time = time.time()
            
            latency = round((end_time - start_time) * 1000, 2)
            me = await client.get_me()
            
            response_text = (
                f"🚀 **Userbot Status: ONLINE**\n\n"
                f"👤 **User:** {me.first_name}\n"
                f"⚡ **Ping:** `{latency}ms`\n"
                f"📂 **Database:** Connected\n"
                f"✅ **System:** All Systems Operational!"
            )
            await msg.edit(response_text)
            logger.info(f"✅ Ping test successful for user {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ping Test Failed for {user_id}: {e}")

    # -----------------------------------------------------
    # 2. INCOMING REPLY TEST (Hi -> Hello)
    # -----------------------------------------------------
    @client.on(events.NewMessage(incoming=True))
    async def auto_reply_handler(event):
        """
        কেউ 'hi' দিলে অটোমেটিক রিপ্লাই দিবে এবং মেইন বটে নোটিফাই করবে।
        """
        try:
            # শুধুমাত্র প্রাইভেট চ্যাটে এবং টেক্সট ম্যাচ হলে
            if event.is_private and event.raw_text and event.raw_text.lower() == "hi":
                
                # ১. ইউজারবট থেকে রিপ্লাই পাঠানো
                await event.reply("Hello! 👋\nThis is an automated reply from my **Userbot**.\nI am currently verifying my connection. ✅")
                logger.info(f"✅ Auto-reply sent for user {user_id}")

                # ২. মেইন বটের মাধ্যমে মালিককে নোটিফিকেশন দেওয়া
                try:
                    sender = await event.get_sender()
                    sender_name = sender.first_name if sender else "Unknown"
                    
                    bot.send_message(
                        user_id,
                        f"🔔 **Userbot Activity Alert!**\n\n"
                        f"👤 **Sender:** {sender_name}\n"
                        f"📨 **Message:** {event.raw_text}\n"
                        f"✅ **Action:** Auto-reply sent."
                    )
                except Exception as notify_error:
                    # নোটিফিকেশন ফেইল করলেও যাতে টাস্ক বন্ধ না হয়
                    logger.warning(f"⚠️ Failed to send notification to owner: {notify_error}")
                    
        except Exception as e:
            logger.error(f"❌ Auto Reply Error for {user_id}: {e}")

    logger.info(f"✨ Task 'Connection Tester' registered successfully for User: {user_id}")
