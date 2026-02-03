import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from utils.utils_shop import get_shop, add_access_request, get_product_rating, validate_coupon, create_order

buyer_sessions = {}
ITEMS_PER_PAGE = 6

def get_session(user_id):
    if user_id not in buyer_sessions:
        buyer_sessions[user_id] = {'page': 0, 'cat': None, 'sort': 'new', 'search': None}
    return buyer_sessions[user_id]

def register_buyer_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data.startswith("view_prods_"))
    def list_shop_content(call):
        shop_id = call.data.replace("view_prods_", "")
        shop = get_shop(shop_id)
        if not shop: 
            bot.answer_callback_query(call.id, "❌ Shop not found.")
            return
        user_id = call.from_user.id
        privacy = shop.get("privacy", "public")
        approved_users = shop.get("approved_users", [])
        
        # Privacy Check
        if privacy == "private" and str(user_id) != str(shop['owner_id']) and user_id not in approved_users:
            pending = shop.get("pending_requests", [])
            sub_price = shop.get("subscription_price", 0)
            kb = InlineKeyboardMarkup()
            if user_id in pending: kb.add(InlineKeyboardButton("⏳ Pending", callback_data="ignore"))
            else:
                if sub_price > 0: kb.add(InlineKeyboardButton(f"💳 Buy Access ({sub_price})", callback_data=f"buy_sub_start_{shop_id}_{sub_price}"))
                else: kb.add(InlineKeyboardButton("✋ Request Access", callback_data=f"req_access_{shop_id}"))
            kb.add(InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu_return"))
            try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="🔒 <b>Private Shop</b>", reply_markup=kb, parse_mode="HTML")
            except: bot.send_message(call.message.chat.id, "🔒 <b>Private Shop</b>", reply_markup=kb)
            return

        buyer_sessions[user_id] = {'page': 0, 'cat': None, 'sort': 'new', 'search': None}
        render_shop_list(bot, call, shop_id)

    def render_shop_list(bot, call, shop_id):
        user_id = call.from_user.id
        session = get_session(user_id)
        shop = get_shop(shop_id)
        all_products = []
        for pid, data in shop.get("products", {}).items():
            if session['cat'] and data.get("category") != session['cat']: continue
            if session['search'] and session['search'].lower() not in data['name'].lower(): continue
            all_products.append({'id': pid, **data})
        if session['sort'] == 'price_asc':
            all_products.sort(key=lambda x: float(x.get('price', 0)) if str(x.get('price',0)).replace('.','',1).isdigit() else 0)
        elif session['sort'] == 'price_desc':
            all_products.sort(key=lambda x: float(x.get('price', 0)) if str(x.get('price',0)).replace('.','',1).isdigit() else 0, reverse=True)
        elif session['sort'] == 'old':
            all_products.sort(key=lambda x: x['id'])
        else: 
            all_products.sort(key=lambda x: x['id'], reverse=True)
        total = len(all_products)
        start = session['page'] * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = all_products[start:end]
        kb = InlineKeyboardMarkup(row_width=2)
        for p in page_items:
            icon = "🔴" if p.get("status") == "sold" else "🟢"
            kb.add(InlineKeyboardButton(f"{icon} {p['name']} - {p['price']}", callback_data=f"sh_view_{shop_id}_{p['id']}"))
        nav = []
        if session['page'] > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"buy_nav_{shop_id}_prev"))
        nav.append(InlineKeyboardButton(f"📄 {session['page']+1}", callback_data="ignore"))
        if end < total: nav.append(InlineKeyboardButton("➡️", callback_data=f"buy_nav_{shop_id}_next"))
        kb.row(*nav)
        filter_status = f"Cat: {shop.get('categories', {}).get(session['cat'], 'All')}" if session['cat'] else "📂 Cats"
        kb.row(InlineKeyboardButton(f"🔍 {session['search'] or 'Search'}", callback_data=f"buy_tool_{shop_id}_search"), InlineKeyboardButton(filter_status, callback_data=f"buy_tool_{shop_id}_cat"), InlineKeyboardButton("Sort", callback_data=f"buy_tool_{shop_id}_sort"))
        
        # --- VIEW CART BUTTON ---
        kb.add(InlineKeyboardButton("🛒 View Cart", callback_data="view_cart_main"))
        
        if session['cat'] or session['search']: kb.add(InlineKeyboardButton("❌ Clear Filters", callback_data=f"buy_tool_{shop_id}_clear"))
        kb.add(InlineKeyboardButton("❌ Close Shop", callback_data="main_menu_return"))
        text = f"🏪 <b>{shop['name']}</b>\n📦 <b>Products:</b> {total} found"
        try: bot.edit_message_text(text=text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)
        except: 
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
            bot.send_message(call.message.chat.id, text, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_nav_"))
    def handle_nav(call):
        parts = call.data.split("_")
        shop_id, action = parts[2], parts[3]
        session = get_session(call.from_user.id)
        if action == "next": session['page'] += 1
        elif action == "prev" and session['page'] > 0: session['page'] -= 1
        render_shop_list(bot, call, shop_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_tool_"))
    def handle_tools(call):
        parts = call.data.split("_")
        shop_id, tool = parts[2], parts[3]
        session = get_session(call.from_user.id)
        if tool == "sort":
            cycle = {'new': 'price_asc', 'price_asc': 'price_desc', 'price_desc': 'new'}
            session['sort'] = cycle.get(session['sort'], 'new')
            render_shop_list(bot, call, shop_id)
        elif tool == "clear":
            session['cat'] = None; session['search'] = None; session['page'] = 0
            render_shop_list(bot, call, shop_id)
        elif tool == "cat":
            shop = get_shop(shop_id)
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("📦 All", callback_data=f"buy_setcat_{shop_id}_all"))
            for cid, cname in shop.get('categories', {}).items(): kb.add(InlineKeyboardButton(cname, callback_data=f"buy_setcat_{shop_id}_{cid}"))
            kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"view_prods_{shop_id}"))
            bot.edit_message_text("📂 <b>Select Category:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
        elif tool == "search":
            msg = bot.send_message(call.message.chat.id, "🔍 <b>Enter search keyword:</b>")
            bot.register_next_step_handler(msg, process_search, bot, shop_id, call)

    def process_search(message, bot, shop_id, original_call):
        session = get_session(message.from_user.id)
        session['search'] = message.text; session['page'] = 0
        try: bot.delete_message(message.chat.id, message.message_id); bot.delete_message(message.chat.id, message.message_id-1)
        except: pass
        render_shop_list(bot, original_call, shop_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_setcat_"))
    def set_category(call):
        parts = call.data.split("_")
        shop_id, cat_id = parts[2], parts[3]
        session = get_session(call.from_user.id)
        session['cat'] = None if cat_id == "all" else cat_id
        session['page'] = 0
        render_shop_list(bot, call, shop_id)

    # --- VIEW PRODUCT ---
    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_view_"))
    def view_product(call):
        try:
            parts = call.data.split("_")
            shop_id, prod_id = parts[2], "_".join(parts[3:])
            shop = get_shop(shop_id)
            prod = shop["products"].get(prod_id)
            if not prod: return
            
            avg_rating, count_rating = get_product_rating(shop_id, prod_id)
            rating_txt = f"⭐ {avg_rating} ({count_rating} reviews)" if count_rating > 0 else "⭐ New"
            
            media_list = prod.get("media", [])
            if "image" in prod: media_list = [{"type": "photo", "file_id": prod["image"]}]
            use_thumbnail = prod.get("use_thumbnail", True)
            cat_tag = ""
            if prod.get("category"):
                cat_name = shop.get("categories", {}).get(prod["category"], "")
                if cat_name: cat_tag = f"\n🏷️ <b>#{cat_name}</b>"
            caption = (f"📦 <b>{prod['name']}</b>\n💰 <b>Price:</b> {prod['price']}\n{rating_txt}\n\n📝 <b>Description:</b>\n{prod.get('description', 'No desc')}{cat_tag}\n\n🏪 <b>Seller:</b> {shop['name']}")
            kb = InlineKeyboardMarkup()
            if use_thumbnail and len(media_list) > 1: kb.add(InlineKeyboardButton("📂 View Full Gallery", callback_data=f"sh_gallery_{shop_id}_{prod_id}"))
            
            if prod.get("status") == "sold": 
                kb.add(InlineKeyboardButton("❌ SOLD OUT", callback_data="sh_alert_sold"))
            else: 
                # ADD TO CART & BUY NOW
                kb.row(
                    InlineKeyboardButton("⚡ Buy Now", callback_data=f"buy_step1_{shop_id}_{prod_id}"),
                    InlineKeyboardButton("🛒 Add to Cart", callback_data=f"add_cart_{shop_id}_{prod_id}")
                )
                
            kb.add(InlineKeyboardButton(f"⭐ Reviews ({count_rating})", callback_data=f"view_revs_{shop_id}_{prod_id}"), InlineKeyboardButton("✍️ Rate", callback_data=f"rate_prod_{shop_id}_{prod_id}"))
            kb.add(InlineKeyboardButton("🔙 Back to List", callback_data=f"view_prods_{shop_id}"))
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
            if use_thumbnail or len(media_list) == 1:
                m = media_list[0]
                if m["type"] == "photo": bot.send_photo(call.message.chat.id, m["file_id"], caption=caption, reply_markup=kb)
                else: bot.send_video(call.message.chat.id, m["file_id"], caption=caption, reply_markup=kb)
            else:
                album = []
                for m in media_list:
                    if m["type"] == "photo": album.append(InputMediaPhoto(m["file_id"]))
                    elif m["type"] == "video": album.append(InputMediaVideo(m["file_id"]))
                bot.send_media_group(call.message.chat.id, album)
                bot.send_message(call.message.chat.id, caption, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, "❌ Error.")

    # ... (Keep existing Single Buy & Membership Buy Flows) ...
    # [Paste buy_sub_step1, sub_ask_coupon, process_sub_coupon, sub_ask_proof, process_sub_proof, buy_step1, ask_coupon, process_coupon, ask_payment_proof, process_proof, handle_access_request, sh_gallery_, sh_alert_sold]
    # NOTE: Ensure you include all handlers from the previous step.
    
    # RE-INCLUDING FOR COMPLETENESS
    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_sub_start_"))
    def buy_sub_step1(call):
        parts = call.data.split("_")
        shop_id, price = parts[3], parts[4]
        msg = f"🔐 <b>Unlock Shop Access</b>\n\n💰 Price: {price}\n\n👇 Do you have a coupon?"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎟️ Apply Coupon", callback_data=f"sub_ask_coup_{shop_id}_{price}"))
        kb.add(InlineKeyboardButton("✅ Proceed to Pay", callback_data=f"sub_fin_{shop_id}_{price}_NONE"))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="main_menu_return"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=msg, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sub_ask_coup_"))
    def sub_ask_coupon(call):
        parts = call.data.split("_")
        shop_id, price = parts[3], parts[4]
        msg = bot.send_message(call.message.chat.id, "🎟️ <b>Enter Coupon Code:</b>")
        bot.register_next_step_handler(msg, process_sub_coupon, bot, shop_id, price)

    def process_sub_coupon(message, bot, shop_id, price):
        code = message.text.strip()
        coupon = validate_coupon(shop_id, code)
        try:
            original = float(price)
            if coupon:
                if coupon['type'] == 'percent': final = original - ((original * coupon['value']) / 100)
                else: final = original - coupon['value']
                if final < 0: final = 0
                msg = f"✅ <b>Coupon Applied!</b>\nOriginal: {original}\n<b>New Price: {final}</b>"
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("✅ Proceed to Pay", callback_data=f"sub_fin_{shop_id}_{final}_{code}"))
                bot.send_message(message.chat.id, msg, reply_markup=kb, parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "❌ Invalid Coupon.")
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("✅ Pay Original", callback_data=f"sub_fin_{shop_id}_{price}_NONE"))
                bot.send_message(message.chat.id, f"💰 Price: {price}", reply_markup=kb)
        except: bot.send_message(message.chat.id, "Error")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sub_fin_"))
    def sub_ask_proof(call):
        parts = call.data.split("_")
        shop_id, price, code = parts[2], parts[3], parts[4]
        shop = get_shop(shop_id)
        pay_info = shop.get("payment_info", "Contact Seller")
        msg = (f"🧾 <b>Payment Instructions</b>\n{pay_info}\n\n💰 <b>Total: {price}</b>\nFor: Shop Membership\n\n📸 <b>Send Payment Screenshot now.</b>")
        sent = bot.send_message(call.message.chat.id, msg, parse_mode="HTML")
        bot.register_next_step_handler(sent, process_sub_proof, bot, shop_id, price)

    def process_sub_proof(message, bot, shop_id, price):
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            order_id = create_order(shop_id, message.from_user.id, message.from_user.first_name, "Shop Membership", price, file_id, order_type="subscription")
            add_access_request(shop_id, message.from_user.id, {"first_name": message.from_user.first_name})
            bot.reply_to(message, "✅ <b>Proof Submitted!</b>\nWaiting for seller approval.")
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"ord_pay_ok_{shop_id}_{order_id}"),
                   InlineKeyboardButton("❌ Reject", callback_data=f"ord_pay_no_{shop_id}_{order_id}"))
            caption = (f"🔔 <b>New Membership Request #{order_id[-4:]}</b>\n👤 {message.from_user.first_name}\n💰 Paid: {price}\n👇 <b>Proof:</b>")
            bot.send_photo(shop_id, file_id, caption=caption, reply_markup=kb, parse_mode="HTML")
        else: bot.reply_to(message, "❌ Send photo.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("buy_step1_"))
    def buy_step1(call):
        parts = call.data.split("_")
        shop_id, prod_id = parts[2], "_".join(parts[3:])
        shop = get_shop(shop_id)
        prod = shop["products"].get(prod_id)
        try: price = float(prod['price'])
        except: price = 0
        msg = f"🛒 <b>Checkout</b>\n\n📦 <b>{prod['name']}</b>\n💰 Price: {prod['price']}\n\n👇 Do you have a coupon?"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎟️ Apply Coupon", callback_data=f"ask_coup_{shop_id}_{prod_id}_{price}"))
        kb.add(InlineKeyboardButton("✅ Confirm Order", callback_data=f"fin_buy_{shop_id}_{prod_id}_{price}_NONE"))
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"sh_view_{shop_id}_{prod_id}"))
        bot.send_message(call.message.chat.id, msg, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ask_coup_"))
    def ask_coupon(call):
        parts = call.data.split("_")
        shop_id, prod_id, price = parts[2], parts[3], parts[4]
        msg = bot.send_message(call.message.chat.id, "🎟️ <b>Enter Coupon Code:</b>")
        bot.register_next_step_handler(msg, process_coupon, bot, shop_id, prod_id, price)

    def process_coupon(message, bot, shop_id, prod_id, price):
        code = message.text.strip()
        coupon = validate_coupon(shop_id, code)
        try:
            original = float(price)
            if coupon:
                if coupon['type'] == 'percent': final = original - ((original * coupon['value']) / 100)
                else: final = original - coupon['value']
                if final < 0: final = 0
                msg = f"✅ <b>Coupon Applied!</b>\nOriginal: {original}\n<b>New Price: {final}</b>"
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("✅ Confirm Order", callback_data=f"fin_buy_{shop_id}_{prod_id}_{final}_{code}"))
                bot.send_message(message.chat.id, msg, reply_markup=kb, parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "❌ Invalid Coupon.")
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("✅ Confirm Original", callback_data=f"fin_buy_{shop_id}_{prod_id}_{price}_NONE"))
                bot.send_message(message.chat.id, f"💰 Price: {price}", reply_markup=kb)
        except: bot.send_message(message.chat.id, "Error")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("fin_buy_"))
    def ask_payment_proof(call):
        parts = call.data.split("_")
        shop_id, prod_id, price, code = parts[2], parts[3], parts[4], parts[5]
        shop = get_shop(shop_id)
        pay_info = shop.get("payment_info", "Contact Seller")
        msg = (f"🧾 <b>Payment Instructions</b>\n{pay_info}\n\n💰 <b>Total to Pay: {price}</b>\n\n📸 <b>Send Payment Screenshot now.</b>")
        sent = bot.send_message(call.message.chat.id, msg, parse_mode="HTML")
        bot.register_next_step_handler(sent, process_proof, bot, shop_id, prod_id, price)

    def process_proof(message, bot, shop_id, prod_id, price):
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            shop = get_shop(shop_id)
            prod = shop["products"].get(prod_id)
            order_id = create_order(shop_id, message.from_user.id, message.from_user.first_name, prod['name'], price, file_id, order_type="product")
            bot.reply_to(message, "✅ <b>Proof Submitted!</b>\nWaiting for seller approval.")
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"ord_pay_ok_{shop_id}_{order_id}"),
                   InlineKeyboardButton("❌ Reject", callback_data=f"ord_pay_no_{shop_id}_{order_id}"))
            caption = (f"🔔 <b>New Order #{order_id[-4:]}</b>\n👤 Buyer: {message.from_user.first_name}\n📦 Item: {prod['name']}\n💰 Price: {price}\n👇 <b>Payment Proof:</b>")
            bot.send_photo(shop_id, file_id, caption=caption, reply_markup=kb, parse_mode="HTML")
        else: bot.reply_to(message, "❌ Please send a screenshot.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("req_access_"))
    def handle_access_request(call):
        shop_id = call.data.replace("req_access_", "")
        user_info = {"first_name": call.from_user.first_name, "username": call.from_user.username or "None"}
        if add_access_request(shop_id, call.from_user.id, user_info):
            bot.answer_callback_query(call.id, "✅ Sent!", show_alert=True)
            try:
                seller_kb = InlineKeyboardMarkup(row_width=2)
                seller_kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"req_ok_{call.from_user.id}"), InlineKeyboardButton("❌ Deny", callback_data=f"req_no_{call.from_user.id}"))
                bot.send_message(shop_id, f"🔔 <b>Request from {user_info['first_name']}</b>\nID: {call.from_user.id}", reply_markup=seller_kb, parse_mode="HTML")
            except: pass
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⏳ Pending", callback_data="ignore"), InlineKeyboardButton("🏠 Main", callback_data="main_menu_return"))
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="🔒 <b>Request Sent</b>", reply_markup=kb)
        else: bot.answer_callback_query(call.id, "❌ Error.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_gallery_"))
    def view_full_gallery(call):
        try:
            parts = call.data.split("_")
            shop_id, prod_id = parts[2], "_".join(parts[3:])
            prod = get_shop(shop_id)["products"].get(prod_id)
            media_list = prod.get("media", [])
            album = []
            for m in media_list:
                if m["type"] == "photo": album.append(InputMediaPhoto(m["file_id"]))
                elif m["type"] == "video": album.append(InputMediaVideo(m["file_id"]))
            bot.answer_callback_query(call.id, "📂 Opening Gallery...")
            bot.send_media_group(call.message.chat.id, album)
        except: pass

    @bot.callback_query_handler(func=lambda c: c.data == "sh_alert_sold")
    def alert_sold(call):
        bot.answer_callback_query(call.id, "🚫 Sold out!", show_alert=True)
