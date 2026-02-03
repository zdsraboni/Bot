import json
import os
import time
import shutil
import threading

SHOPS_FILE = 'shops.json'
BACKUP_FILE = 'shops.json.bak'

# শপ ডাটাবেস লক (Data Corruption রোধ করতে)
shop_lock = threading.Lock()

# ==========================================
# 💾 DATABASE CORE (UPDATED & SECURE)
# ==========================================

def load_shops():
    """
    নিরাপদভাবে ডাটা লোড করে লক ব্যবহার করে।
    ফাইল নষ্ট থাকলে .corrupt নামে রিনেম করে, যাতে ডাটা হারিয়ে না যায়।
    """
    if not os.path.exists(SHOPS_FILE):
        return {}

    with shop_lock:
        try:
            with open(SHOPS_FILE, 'r', encoding='utf-8') as f: 
                return json.load(f)
        except json.JSONDecodeError:
            print("❌ Error: shops.json is corrupted. Renaming to .corrupt")
            try:
                os.rename(SHOPS_FILE, SHOPS_FILE + ".corrupt")
            except: pass
            return {}
        except Exception as e:
            print(f"⚠️ Load Error: {e}")
            return {}

def save_shops(data):
    """
    লক ব্যবহার করে ডাটা সেভ করে এবং অটোমেটিক ব্যাকআপ রাখে।
    """
    with shop_lock:
        # সেভ করার আগে আগের ফাইলের ব্যাকআপ নেওয়া
        if os.path.exists(SHOPS_FILE):
            try:
                shutil.copy(SHOPS_FILE, BACKUP_FILE)
            except Exception as e:
                print(f"⚠️ Backup Failed: {e}")

        try:
            with open(SHOPS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Save Error: {e}")
            return False

# ==========================================
# 🏪 SHOP MANAGEMENT
# ==========================================

def get_shop(user_id):
    data = load_shops()
    return data.get(str(user_id))

def create_shop(user_id, name):
    data = load_shops()
    uid = str(user_id)
    if uid in data: return False
    
    data[uid] = {
        "owner_id": user_id,
        "name": name,
        "description": "Welcome to my store!",
        "banner": None,
        "payment_info": "Contact Admin for payment.",
        "privacy": "public",
        "subscription_price": 0, # 0 = Free, >0 = Paid
        "channel_id": None,
        "auto_post": False,
        "approved_users": [],
        "pending_requests": [],
        "scheduled_posts": [],
        "customers": {},
        "categories": {}, 
        "products": {},
        "coupons": {},
        "orders": {} 
    }
    return save_shops(data)

# ==========================================
# 📦 PRODUCTS MANAGEMENT
# ==========================================

def add_product_to_shop(user_id, name, price, description, media_list, category_id=None):
    data = load_shops()
    uid = str(user_id)
    if uid not in data: return False
    if "products" not in data[uid]: data[uid]["products"] = {}
    
    prod_id = f"prod_{int(time.time())}"
    data[uid]["products"][prod_id] = {
        "name": name, "price": price, "description": description,
        "media": media_list, "category": category_id, 
        "status": "active", "use_thumbnail": True, "reviews": []
    }
    return save_shops(data)

def update_product_field(user_id, prod_id, field, value):
    data = load_shops()
    uid = str(user_id)
    if uid in data and "products" in data[uid] and prod_id in data[uid]["products"]:
        data[uid]["products"][prod_id][field] = value
        return save_shops(data)
    return False

def toggle_product_thumbnail(user_id, prod_id):
    data = load_shops()
    uid = str(user_id)
    if uid in data and "products" in data[uid] and prod_id in data[uid]["products"]:
        current = data[uid]["products"][prod_id].get("use_thumbnail", True)
        data[uid]["products"][prod_id]["use_thumbnail"] = not current
        return save_shops(data)
    return False

def delete_product(user_id, prod_id):
    data = load_shops()
    uid = str(user_id)
    if uid in data and "products" in data[uid] and prod_id in data[uid]["products"]:
        del data[uid]["products"][prod_id]
        return save_shops(data)
    return False

def toggle_product_status(user_id, prod_id):
    data = load_shops()
    uid = str(user_id)
    if uid in data and "products" in data[uid] and prod_id in data[uid]["products"]:
        current = data[uid]["products"][prod_id].get("status", "active")
        new_status = "sold" if current == "active" else "active"
        data[uid]["products"][prod_id]["status"] = new_status
        return save_shops(data)
    return False

# ==========================================
# 📂 CATEGORIES
# ==========================================

def create_category(user_id, name):
    data = load_shops()
    uid = str(user_id)
    if uid not in data: return False
    if "categories" not in data[uid]: data[uid]["categories"] = {}
    cat_id = f"cat_{int(time.time())}"
    data[uid]["categories"][cat_id] = name
    return save_shops(data)

def delete_category(user_id, cat_id):
    data = load_shops()
    uid = str(user_id)
    if uid in data and "categories" in data[uid] and cat_id in data[uid]["categories"]:
        del data[uid]["categories"][cat_id]
        if "products" in data[uid]:
            for pid in data[uid]["products"]:
                if data[uid]["products"][pid].get("category") == cat_id:
                    data[uid]["products"][pid]["category"] = None
        return save_shops(data)
    return False

def get_categories(user_id):
    data = load_shops()
    return data.get(str(user_id), {}).get("categories", {})

# ==========================================
# 🛒 ORDERS & PAYMENTS
# ==========================================

def create_order(shop_id, buyer_id, buyer_name, item_summary, price, proof_file_id, order_type="product"):
    data = load_shops()
    sid = str(shop_id)
    if sid in data:
        if "orders" not in data[sid]: data[sid]["orders"] = {}
        
        order_id = f"ord_{int(time.time())}_{buyer_id}"
        data[sid]["orders"][order_id] = {
            "buyer_id": buyer_id,
            "buyer_name": buyer_name,
            "item": item_summary,
            "price": price,
            "proof": proof_file_id,
            "type": order_type, 
            "status": "pending", 
            "date": int(time.time())
        }
        save_shops(data)
        return order_id
    return None

def update_order_status(shop_id, order_id, status):
    data = load_shops()
    sid = str(shop_id)
    if sid in data and "orders" in data[sid] and order_id in data[sid]["orders"]:
        data[sid]["orders"][order_id]["status"] = status
        save_shops(data)
        return data[sid]["orders"][order_id]
    return None

def set_payment_info(user_id, text):
    data = load_shops()
    uid = str(user_id)
    if uid in data:
        data[uid]["payment_info"] = text
        return save_shops(data)
    return False

def set_subscription_price(user_id, price):
    data = load_shops()
    uid = str(user_id)
    if uid in data:
        data[uid]["subscription_price"] = float(price)
        return save_shops(data)
    return False

# ==========================================
# 👥 ACCESS & REQUESTS
# ==========================================

def toggle_shop_privacy(user_id):
    data = load_shops()
    uid = str(user_id)
    if uid in data:
        current = data[uid].get("privacy", "public")
        data[uid]["privacy"] = "private" if current == "public" else "public"
        return save_shops(data)
    return False

def add_access_request(shop_owner_id, buyer_id, buyer_info):
    data = load_shops()
    soid = str(shop_owner_id)
    if soid in data:
        if "pending_requests" not in data[soid]: data[soid]["pending_requests"] = []
        if "customers" not in data[soid]: data[soid]["customers"] = {}
        if buyer_id not in data[soid]["pending_requests"] and buyer_id not in data[soid].get("approved_users", []):
            data[soid]["pending_requests"].append(buyer_id)
            data[soid]["customers"][str(buyer_id)] = buyer_info 
            save_shops(data)
            return True
    return False

def approve_access(shop_owner_id, buyer_id):
    data = load_shops()
    soid = str(shop_owner_id)
    if soid in data:
        if "approved_users" not in data[soid]: data[soid]["approved_users"] = []
        if "pending_requests" not in data[soid]: data[soid]["pending_requests"] = []
        if buyer_id in data[soid]["pending_requests"]: data[soid]["pending_requests"].remove(buyer_id)
        if buyer_id not in data[soid]["approved_users"]: data[soid]["approved_users"].append(buyer_id)
        return save_shops(data)
    return False

def deny_access(shop_owner_id, buyer_id):
    data = load_shops()
    soid = str(shop_owner_id)
    if soid in data and "pending_requests" in data[soid]:
        if buyer_id in data[soid]["pending_requests"]:
            data[soid]["pending_requests"].remove(buyer_id)
            return save_shops(data)
    return False

def manual_add_buyer(shop_owner_id, target_id, name="Manual Add"):
    data = load_shops()
    soid = str(shop_owner_id)
    if soid in data:
        if "approved_users" not in data[soid]: data[soid]["approved_users"] = []
        if target_id not in data[soid]["approved_users"]:
            data[soid]["approved_users"].append(target_id)
            if "customers" not in data[soid]: data[soid]["customers"] = {}
            data[soid]["customers"][str(target_id)] = {'first_name': name, 'username': 'Unknown'}
            return save_shops(data)
    return False

# ==========================================
# 🎫 COUPONS
# ==========================================

def create_coupon(user_id, code, discount_type, value):
    data = load_shops()
    uid = str(user_id)
    if uid not in data: return False
    if "coupons" not in data[uid]: data[uid]["coupons"] = {}
    code = code.upper().strip()
    data[uid]["coupons"][code] = {"type": discount_type, "value": float(value), "created_at": int(time.time())}
    return save_shops(data)

def delete_coupon(user_id, code):
    data = load_shops()
    uid = str(user_id)
    if uid in data and "coupons" in data[uid] and code in data[uid]["coupons"]:
        del data[uid]["coupons"][code]
        return save_shops(data)
    return False

def get_coupons(user_id):
    data = load_shops()
    return data.get(str(user_id), {}).get("coupons", {})

def validate_coupon(shop_id, code):
    data = load_shops()
    shop = data.get(str(shop_id))
    if not shop: return None
    return shop.get("coupons", {}).get(code.upper().strip())

# ==========================================
# ⭐ REVIEWS & RATINGS
# ==========================================

def add_product_review(shop_id, prod_id, user_id, user_name, rating, text):
    data = load_shops()
    sid = str(shop_id)
    if sid in data and prod_id in data[sid]["products"]:
        prod = data[sid]["products"][prod_id]
        if "reviews" not in prod: prod["reviews"] = []
        for r in prod["reviews"]:
            if r["user_id"] == user_id:
                r["rating"] = rating; r["text"] = text; r["date"] = int(time.time())
                return save_shops(data)
        prod["reviews"].append({"user_id": user_id, "name": user_name, "rating": rating, "text": text, "date": int(time.time())})
        return save_shops(data)
    return False

def get_product_reviews(shop_id, prod_id):
    data = load_shops()
    return data.get(str(shop_id), {}).get("products", {}).get(prod_id, {}).get("reviews", [])

def get_product_rating(shop_id, prod_id):
    reviews = get_product_reviews(shop_id, prod_id)
    if not reviews: return 0.0, 0
    total = sum(r["rating"] for r in reviews)
    return round(total / len(reviews), 1), len(reviews)

# ==========================================
# 📢 CHANNEL & SCHEDULING
# ==========================================

def set_shop_channel(user_id, channel_id):
    data = load_shops()
    uid = str(user_id)
    if uid in data:
        data[uid]["channel_id"] = channel_id
        return save_shops(data)
    return False

def toggle_auto_post(user_id):
    data = load_shops()
    uid = str(user_id)
    if uid in data:
        curr = data[uid].get("auto_post", False)
        data[uid]["auto_post"] = not curr
        return save_shops(data)
    return False

def schedule_post(user_id, prod_id, post_time):
    data = load_shops()
    uid = str(user_id)
    if uid in data:
        if "scheduled_posts" not in data[uid]: data[uid]["scheduled_posts"] = []
        data[uid]["scheduled_posts"].append({"prod_id": prod_id, "run_at": post_time})
        return save_shops(data)
    return False

def get_and_clear_due_posts():
    data = load_shops()
    now = int(time.time())
    tasks_to_run = []
    modified = False
    for uid, shop in data.items():
        if "scheduled_posts" not in shop or not shop["scheduled_posts"]: continue
        remaining = []
        for task in shop["scheduled_posts"]:
            if task["run_at"] <= now:
                prod = shop["products"].get(task["prod_id"])
                if prod and shop.get("channel_id"):
                    tasks_to_run.append({"channel_id": shop["channel_id"], "product": prod, "shop_name": shop["name"], "shop_owner_id": uid})
                modified = True
            else: remaining.append(task)
        data[uid]["scheduled_posts"] = remaining
    if modified: save_shops(data)
    return tasks_to_run

# ==========================================
# 📊 ANALYTICS & BACKUP
# ==========================================

def update_shop_desc(user_id, new_desc):
    data = load_shops()
    uid = str(user_id)
    if uid in data:
        data[uid]["description"] = new_desc
        return save_shops(data)
    return False

def set_shop_banner(user_id, photo_id):
    data = load_shops()
    uid = str(user_id)
    if uid in data:
        data[uid]["banner"] = photo_id
        return save_shops(data)
    return False

def get_shop_backup_data(user_id):
    data = load_shops()
    return data.get(str(user_id))

def restore_shop_data(user_id, backup_data):
    data = load_shops()
    uid = str(user_id)
    required_keys = ["owner_id", "name", "products"]
    if not all(key in backup_data for key in required_keys): return False, "Invalid File."
    backup_data["owner_id"] = user_id
    data[uid] = backup_data
    if save_shops(data): return True, "Restored!"
    else: return False, "Save error."

def get_shop_analytics(user_id):
    shop = get_shop(user_id)
    if not shop: return None
    orders = shop.get("orders", {})
    products = shop.get("products", {})
    stats = {
        "revenue": 0.0, "total_orders": len(orders), 
        "pending": 0, "paid": 0, "rejected": 0, 
        "members": len(shop.get("approved_users", [])), 
        "total_products": len(products), 
        "best_seller": "None"
    }
    sales_count = {} 
    for oid, o in orders.items():
        status = o.get("status", "pending")
        if status == "pending": stats["pending"] += 1
        elif status == "rejected": stats["rejected"] += 1
        elif status == "paid":
            stats["paid"] += 1
            try: stats["revenue"] += float(o.get("price", 0))
            except: pass
            p_name = o.get("item", "Unknown")
            sales_count[p_name] = sales_count.get(p_name, 0) + 1
    if sales_count:
        top_item = max(sales_count, key=sales_count.get)
        stats["best_seller"] = f"{top_item} ({sales_count[top_item]} sales)"
    return stats
