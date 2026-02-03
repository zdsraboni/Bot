import logging
from telethon import events

# মেনু প্যানেলের জন্য তথ্য (এটি ইউজারবট টুলস মেনুতে বাটন হিসেবে দেখাবে)
TOOL_INFO = {
    "label": "🤖 Connection Tester (Hi-Hello)",
    "callback": "none"
}

logger = logging.getLogger(__name__)

def register_userbot_task(client, bot, user_id):
    """
    ইউজারবট ইঞ্জিন এই ফাংশনটি কল করে যখন ইউজার বাটনটি ON করে।
    এটি সরাসরি সেশন ক্লায়েন্টের সাথে ইভেন্ট হ্যান্ডলার রেজিস্টার করে।
    """
    
    @client.on(events.NewMessage(incoming=True))
    async def hello_handler(event):
        # মেসেজটি যদি 'hi' হয় (ছোট বা বড় হাতের অক্ষর যাই হোক)
        if event.raw_text.lower() == "hi":
            logger.info(f"Test match found for user {user_id}. Sending reply...")
            
            # ১. ইউজারবট থেকে সরাসরি রিপ্লাই পাঠানো
            try:
                await event.reply("Hello! Your Userbot is working perfectly. ✅")
            except Exception as e:
                logger.error(f"Error sending reply: {e}")
            
            # ২. মেইন বটের মাধ্যমে আপনাকে একটি নোটিফিকেশন দেওয়া (সতর্কবার্তা)
            try:
                bot.send_message(
                    user_id, 
                    "📢 **Userbot Alert:** আপনার একাউন্ট থেকে একটি অটো-রিপ্লাই ('Hello') পাঠানো হয়েছে।"
                )
            except Exception as e:
                logger.error(f"Notification Error: {e}")

    logger.info(f"✨ Test task (Hi-Hello) successfully registered for user {user_id}")