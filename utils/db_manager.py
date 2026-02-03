import logging
import pymongo
from pymongo import MongoClient
import os
import certifi

# লগিং সেটআপ
logger = logging.getLogger(__name__)

# ✅ কনফিগ থেকে মঙ্গো ইউআরএল নেওয়া (অথবা ডিফল্ট এনভায়রনমেন্ট ভেরিয়েবল)
try:
    from config import MONGO_URL
except ImportError:
    MONGO_URL = os.environ.get("MONGO_URL")

# গ্লোবাল ভেরিয়েবল
db_client = None
db = None
collection = None

def init_db():
    """ডাটাবেস ইনিশিয়ালাইজেশন এবং কানেকশন"""
    global db_client, db, collection
    
    if not MONGO_URL:
        logger.error("❌ MONGO_URL missing in config.py or Environment!")
        return False

    try:
        # SSL সার্টিফিকেটের সমস্যা এড়াতে 'certifi' ব্যবহার করা হয়েছে
        db_client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())
        
        # ডাটাবেস এবং কালেকশন নাম (প্রয়োজনে পরিবর্তন করতে পারেন)
        db = db_client["userbot_database"]
        collection = db["sessions"]
        
        # কানেকশন টেস্ট
        db_client.admin.command('ping')
        logger.info("✅ MongoDB Atlas Connected Successfully!")
        return True
    except Exception as e:
        logger.error(f"❌ MongoDB Connection Failed: {e}")
        return False

# প্রথমবার রান করার সময় কানেক্ট করা
init_db()

def get_full_config():
    """
    ডাটাবেস থেকে সকল ইউজার সেশন কনফিগ রিড করা।
    রিটার্ন ফরম্যাট: { "user_id": { "api_id": "...", "session": "..." } }
    """
    if collection is None:
        if not init_db(): return {}

    try:
        all_data = {}
        # সব ডকুমেন্ট রিড করা
        cursor = collection.find({})
        for doc in cursor:
            user_id = doc.get("user_id")
            if user_id:
                # _id অবজেক্ট রিমুভ করে ক্লিন ডাটা পাঠানো
                doc.pop("_id", None)
                all_data[str(user_id)] = doc
        return all_data
    except Exception as e:
        logger.error(f"❌ Error fetching config: {e}")
        return {}

def save_full_config(all_data):
    """
    সম্পূর্ণ কনফিগ ডাটাবেসে সেভ/আপডেট করা।
    এটি নতুন ডাটা অ্যাড করবে এবং পুরনো ডাটা আপডেট করবে।
    """
    if collection is None:
        if not init_db(): return False

    try:
        # বাল্ক রাইট অপারেশন (দ্রুত এবং কার্যকরী)
        from pymongo import UpdateOne
        operations = []

        # বর্তমান মেমোরিতে থাকা ডাটা লুপ করা
        for user_id, user_data in all_data.items():
            # নিশ্চিত করা যে user_id ডাটার ভেতরেও আছে
            user_data["user_id"] = str(user_id)
            
            # আপডেট অপারেশন তৈরি করা (Upsert: থাকলে আপডেট, না থাকলে ইনসার্ট)
            op = UpdateOne(
                {"user_id": str(user_id)},
                {"$set": user_data},
                upsert=True
            )
            operations.append(op)

        if operations:
            collection.bulk_write(operations)
        
        # নোট: এই ফাংশনটি ডিলিট হ্যান্ডেল করছে না (main.py ম্যানুয়ালি ডিলিট করে)।
        # তবে আপনি চাইলে ডিলিট লজিকও এখানে আনতে পারেন। আপাতত এটি সেফ।
        
        logger.info("✅ Database Saved Successfully.")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving config: {e}")
        return False

# নির্দিষ্ট ইউজার ডাটা ডিলিট করার ফাংশন (অপশনাল কিন্তু কাজের)
def delete_user_data(user_id):
    if collection is None: return False
    try:
        collection.delete_one({"user_id": str(user_id)})
        return True
    except Exception as e:
        logger.error(f"❌ Error deleting user {user_id}: {e}")
        return False
