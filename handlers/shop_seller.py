import telebot
import json
import io
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from utils.utils_shop import (
    get_shop, create_shop, add_product_to_shop, update_shop_desc, 
    set_shop_banner, delete_product, toggle_product_status, 
    update_product_field, toggle_product_thumbnail, get_categories, 
    toggle_shop_privacy, get_shop_backup_data, restore_shop_data,
    set_shop_channel, toggle_auto_post, schedule_post, set_payment_info,
    set_subscription_price
)
from handlers.shop_social import post_product_to_channel

media_cache = {}
pending_data = {}
seller_sessions = {}
ITEMS_PER_PAGE = 6

def get_session(user_id):
    if user_id not in seller_sessions: seller_sessions[user_id] = {'page': 0, 'search': None, 'cat': None}
    return seller_sessions[user_id]

def register_seller_handlers(bot):
    
    # ... (Keep all Global Upload Handlers and Done Command from previous) ...
    # [Paste handle_media_upload, handle_done_command, clean_up]
    @bot.message_handler(content_types=['photo', 'video', 'animation'], func=lambda m: m.from_user.id in media_cache)
    def handle_media_upload(message):
        user_id = message.from_user.id
        file_data = None
        if message.content_type == 'photo': file_data = {"type": "photo", "file_id": message.photo[-1].file_id}
        elif message.content_type == 'video': file_data = {"type": "video", "file_id": message.video.file_id}
        elif message.content_type == 'animation': file_data = {"type": "video", "file_id": message.animation.file_id}
        if file_data: media_cache[user_id].append(file_data)
    
    @bot.message_handler(commands=['done'], func=lambda m: m.from_user.id in media_cache)
    def handle_done_command(message):
        user_id = message.from_user.id
        data = pending_data.get(user_id)
        files = media_cache.get(user_id, [])
        if not data or not files: 
            bot.reply_to(message, "❌ No files sent.")
            clean_up(user_id)
            return

        if data['action'] == 'add':
            if add_product_to_shop(user_id, data['name'], data['price'], data['desc'], files, data.get('category_id')):
                bot.reply_to(message, f"✅ Added: {data['name']}")
                shop = get_shop(user_id)
                if shop and shop.get("auto_post") and shop.get("channel_id"):
                    prod_dummy = {"name": data['name'], "price": data['price'], "description": data['desc'], "media": files}
                    if post_product_to_channel(bot, shop["channel_id"], prod_dummy, shop["name"], user_id, bot.get_me().username):
                        bot.send_message(message.chat.id, "📢 Auto-Posted!")
                show_dashboard(bot, message, shop)
        elif data['action'] == 'edit':
            if update_product_field(user_id, data['prod_id'], "media", files):
                bot.reply_to(message, "✅ Media Updated")
                call_obj = type('obj', (object,), {'from_user': message.from_user, 'data': f"sh_mng_{data['prod_id']}", 'message': message, 'id': '0'})
                manage_single_product(call_obj)
        clean_up(user_id)

    def clean_up(user_id):
        if user_id in media_cache: del media_cache[user_id]
        if user_id in pending_data: del pending_data[user_id]

    # --- DASHBOARD (UPDATED WITH STATS) ---
    @bot.callback_query_handler(func=lambda c: c.data == "my_business")
    def open_business_menu(call):
        clean_up(call.from_user.id)
        shop = get_shop(call.from_user.id)
        if not shop:
            msg = bot.send_message(call.message.chat.id, "💼 <b>Start Shop</b>\nEnter Name:")
            bot.register_next_step_handler(msg, process_create_shop, bot)
        else: show_dashboard(bot, call.message, shop)

    def show_dashboard(bot, message, shop):
        user_id = shop['owner_id']
        shop_link = f"https://t.me/{bot.get_me().username}?start=shop_{user_id}"
        banner_status = "✅" if shop.get("banner") else "❌"
        privacy = shop.get("privacy", "public")
        priv_icon = "🔓 Public" if privacy == "public" else "🔒 Private"
        req_count = len(shop.get("pending_requests", []))
        req_btn = f"👥 Buyers ({req_count})" if req_count > 0 else "👥 Buyers"
        chan_status = "📢 ON" if shop.get("channel_id") else "📢 OFF"
        sub_price = shop.get("subscription_price", 0)
        sub_txt = f"💰 Fee: {sub_price}" if sub_price > 0 else "🆓 Free Entry"

        text = (f"🏪 <b>{shop['name']}</b>\n🔗 <code>{shop_link}</code>\n📦 <b>Prods:</b> {len(shop['products'])}\n👁️ <b>Mode:</b> {priv_icon} ({sub_txt})")
        
        kb = InlineKeyboardMarkup(row_width=2)
        # Row 1
        kb.add(InlineKeyboardButton("📦 Products", callback_data="shop_manage_menu"), InlineKeyboardButton("📂 Categories", callback_data="shop_cat_menu"))
        # Row 2: Stats + Privacy
        kb.add(InlineKeyboardButton("📊 Statistics", callback_data="shop_analytics_menu"), InlineKeyboardButton(f"👁️ {privacy.title()}", callback_data="shop_tog_privacy"))
        
        kb.add(InlineKeyboardButton(f"💵 {sub_txt}", callback_data="shop_set_fee"), InlineKeyboardButton(req_btn, callback_data="shop_req_menu"))
        kb.add(InlineKeyboardButton("📢 Broadcast", callback_data="shop_broadcast"), InlineKeyboardButton(chan_status, callback_data="shop_channel_menu"))
        kb.add(InlineKeyboardButton("🎫 Coupons", callback_data="shop_coupon_menu"), InlineKeyboardButton("💾 Backup", callback_data="shop_backup_menu"))
        kb.add(InlineKeyboardButton("💰 Pay Info", callback_data="shop_set_pay_info"), InlineKeyboardButton("➕ Add Product", callback_data="shop_add_prod"))
        kb.add(InlineKeyboardButton(f"🖼️ Banner: {banner_status}", callback_data="shop_set_banner"), InlineKeyboardButton("✏️ Desc", callback_data="shop_edit_info"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="main_menu_return"))
        
        try: bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=text, reply_markup=kb, disable_web_page_preview=True)
        except: bot.send_message(message.chat.id, text, reply_markup=kb, disable_web_page_preview=True)

    # ... (Keep ALL other handlers: subscription, channel, payment, manage list, etc. unchanged) ...
    # [Paste process_create_shop, start_set_fee, start_pay_info, toggle_privacy, channel_menu, etc.]
    
    # RE-INCLUDING NECESSARY FUNCTIONS FOR COMPLETENESS:
    @bot.callback_query_handler(func=lambda c: c.data == "shop_set_fee")
    def start_set_fee(call):
        msg = bot.send_message(call.message.chat.id, "💵 <b>Set Entry Fee</b>\nEnter price (0 for free):")
        bot.register_next_step_handler(msg, process_set_fee, bot)

    def process_set_fee(message, bot):
        try:
            price = float(message.text.strip())
            set_subscription_price(message.from_user.id, price)
            bot.reply_to(message, "✅ Fee Set!")
            show_dashboard(bot, message, get_shop(message.from_user.id))
        except: bot.reply_to(message, "❌ Invalid.")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_set_pay_info")
    def start_pay_info(call):
        msg = bot.send_message(call.message.chat.id, "💰 <b>Set Payment Instructions</b>")
        bot.register_next_step_handler(msg, process_pay_info, bot)

    def process_pay_info(message, bot):
        if set_payment_info(message.from_user.id, message.text):
            bot.send_message(message.chat.id, "✅ Updated!")
            show_dashboard(bot, message, get_shop(message.from_user.id))

    @bot.callback_query_handler(func=lambda c: c.data == "shop_tog_privacy")
    def toggle_privacy(call):
        toggle_shop_privacy(call.from_user.id)
        show_dashboard(bot, call.message, get_shop(call.from_user.id))

    def process_create_shop(message, bot):
        if create_shop(message.from_user.id, message.text):
            bot.send_message(message.chat.id, "✅ Shop Created!")
            show_dashboard(bot, message, get_shop(message.from_user.id))

    @bot.callback_query_handler(func=lambda c: c.data == "shop_channel_menu")
    def channel_menu(call):
        shop = get_shop(call.from_user.id)
        if not shop: return
        chan_id = shop.get("channel_id")
        auto_post = shop.get("auto_post", False)
        status_txt = f"ID: {chan_id}" if chan_id else "❌ Not Connected"
        auto_txt = "✅ ON" if auto_post else "❌ OFF"
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("✏️ Set Channel ID", callback_data="shop_set_chan"))
        if chan_id: kb.add(InlineKeyboardButton(f"🔄 Auto-Post: {auto_txt}", callback_data="shop_tog_autopost"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="my_business"))
        text = (f"📢 <b>Channel Integration</b>\n\n📡 <b>Connected:</b> {status_txt}\n⚡ <b>Auto-Post:</b> {auto_txt}")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_set_chan")
    def ask_channel_id(call):
        msg = bot.send_message(call.message.chat.id, "📢 <b>Send Channel ID:</b>")
        bot.register_next_step_handler(msg, process_channel_id, bot)

    def process_channel_id(message, bot):
        try:
            cid = int(message.text.strip())
            set_shop_channel(message.from_user.id, cid)
            bot.reply_to(message, "✅ Connected!")
            call_obj = type('obj', (object,), {'from_user': message.from_user, 'data': "shop_channel_menu", 'message': message, 'id': '0'})
            channel_menu(call_obj)
        except: bot.reply_to(message, "❌ Invalid ID.")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_tog_autopost")
    def toggle_auto(call):
        toggle_auto_post(call.from_user.id)
        channel_menu(call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("post_menu_"))
    def post_options(call):
        prod_id = call.data.replace("post_menu_", "")
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🚀 Post Now", callback_data=f"do_post_{prod_id}"))
        kb.add(InlineKeyboardButton("⏰ Schedule", callback_data=f"do_sched_{prod_id}"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"sh_mng_{prod_id}"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="📢 <b>Post Options</b>", reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("do_post_"))
    def execute_post(call):
        prod_id = call.data.replace("do_post_", "")
        shop = get_shop(call.from_user.id)
        if not shop or not shop.get("channel_id"):
            bot.answer_callback_query(call.id, "❌ No Channel!")
            return
        prod = shop["products"].get(prod_id)
        if post_product_to_channel(bot, shop["channel_id"], prod, shop["name"], call.from_user.id, bot.get_me().username):
            bot.answer_callback_query(call.id, "✅ Posted!")
        else: bot.answer_callback_query(call.id, "❌ Failed.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("do_sched_"))
    def ask_schedule_time(call):
        prod_id = call.data.replace("do_sched_", "")
        msg = bot.send_message(call.message.chat.id, "⏰ Enter minutes to wait:")
        bot.register_next_step_handler(msg, process_schedule, bot, prod_id)

    def process_schedule(message, bot, prod_id):
        try:
            mins = int(message.text.strip())
            run_at = int(time.time()) + (mins * 60)
            schedule_post(message.from_user.id, prod_id, run_at)
            bot.reply_to(message, f"✅ Scheduled.")
        except: bot.reply_to(message, "❌ Invalid number.")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_backup_menu")
    def backup_menu(call):
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("📥 Download", callback_data="shop_backup_dl"))
        kb.add(InlineKeyboardButton("📤 Restore", callback_data="shop_backup_ul"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="my_business"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="💾 <b>Backup</b>", reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_backup_dl")
    def download_backup(call):
        data = get_shop_backup_data(call.from_user.id)
        if not data: return
        f = io.BytesIO(json.dumps(data, indent=4).encode('utf-8'))
        f.name = f"Backup_{call.from_user.id}.json"
        bot.send_document(call.message.chat.id, f, caption="✅ Backup")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_backup_ul")
    def ask_restore(call):
        msg = bot.send_message(call.message.chat.id, "📤 Send .json file.")
        bot.register_next_step_handler(msg, process_restore, bot)

    def process_restore(message, bot):
        if not message.document: return
        try:
            f = bot.download_file(bot.get_file(message.document.file_id).file_path)
            res, txt = restore_shop_data(message.from_user.id, json.loads(f.decode()))
            bot.reply_to(message, txt)
            if res: show_dashboard(bot, message, get_shop(message.from_user.id))
        except: bot.reply_to(message, "Error")

    @bot.callback_query_handler(func=lambda c: c.data == "shop_manage_menu")
    def init_manage_menu(call):
        seller_sessions[call.from_user.id] = {'page': 0, 'search': None, 'cat': None}
        render_manage_list(bot, call)

    def render_manage_list(bot, call):
        user_id = call.from_user.id
        shop = get_shop(user_id)
        session = get_session(user_id)
        if not shop.get('products'):
            bot.answer_callback_query(call.id, "❌ No products.")
            return
        products = []
        for pid, data in shop['products'].items():
            if session['search'] and session['search'].lower() not in data['name'].lower(): continue
            products.append({'id': pid, **data})
        products.sort(key=lambda x: x['id'], reverse=True)
        total = len(products)
        start = session['page'] * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = products[start:end]
        kb = InlineKeyboardMarkup(row_width=1)
        for p in page_items:
            status = "🟢" if p.get("status", "active") == "active" else "🔴"
            kb.add(InlineKeyboardButton(f"{status} {p['name']}", callback_data=f"sh_mng_{p['id']}"))
        nav = []
        if session['page'] > 0: nav.append(InlineKeyboardButton("⬅️", callback_data="sell_nav_prev"))
        nav.append(InlineKeyboardButton(f"📄 {session['page']+1}", callback_data="ignore"))
        if end < total: nav.append(InlineKeyboardButton("➡️", callback_data="sell_nav_next"))
        kb.row(*nav)
        kb.row(InlineKeyboardButton(f"🔍 {session['search'] or 'Search'}", callback_data="sell_tool_search"), InlineKeyboardButton("❌ Clear", callback_data="sell_tool_clear"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data="my_business"))
        text = f"🛠 <b>Manage Products</b>\nItems: {len(page_items)}/{total}"
        if session['search']: text += f"\n🔍 Filter: {session['search']}"
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, text, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sell_nav_"))
    def seller_nav(call):
        session = get_session(call.from_user.id)
        if "next" in call.data: session['page'] += 1
        elif "prev" in call.data and session['page'] > 0: session['page'] -= 1
        render_manage_list(bot, call)

    @bot.callback_query_handler(func=lambda c: c.data == "sell_tool_clear")
    def seller_clear(call):
        get_session(call.from_user.id)['search'] = None
        render_manage_list(bot, call)

    @bot.callback_query_handler(func=lambda c: c.data == "sell_tool_search")
    def seller_search(call):
        msg = bot.send_message(call.message.chat.id, "🔍 Enter keyword:")
        bot.register_next_step_handler(msg, process_seller_search, bot, call)

    def process_seller_search(message, bot, original_call):
        get_session(message.from_user.id)['search'] = message.text
        try: bot.delete_message(message.chat.id, message.message_id); bot.delete_message(message.chat.id, message.message_id-1)
        except: pass
        render_manage_list(bot, original_call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_mng_"))
    def manage_single_product(call):
        prod_id = call.data.replace("sh_mng_", "")
        shop = get_shop(call.from_user.id)
        prod = shop['products'].get(prod_id)
        if not prod: return
        cat_name = shop.get("categories", {}).get(prod.get("category"), "None")
        text = (f"📦 <b>{prod['name']}</b>\n💰 {prod['price']}\n📂 Cat: <b>{cat_name}</b>\n🖼️ Thumb: {'ON' if prod.get('use_thumbnail', True) else 'OFF'}\nStatus: {prod.get('status', 'active')}")
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("👁️ Preview", callback_data=f"sh_prev_{prod_id}"), InlineKeyboardButton("📢 Post to Channel", callback_data=f"post_menu_{prod_id}"))
        kb.add(InlineKeyboardButton("✏️ Name", callback_data=f"ed_nm_{prod_id}"), InlineKeyboardButton("✏️ Price", callback_data=f"ed_pr_{prod_id}"))
        kb.add(InlineKeyboardButton("✏️ Cat", callback_data=f"ed_cat_{prod_id}"), InlineKeyboardButton("🖼️ Media", callback_data=f"ed_md_{prod_id}"))
        kb.add(InlineKeyboardButton("Toggle Thumb", callback_data=f"sh_tog_th_{prod_id}"), InlineKeyboardButton("Toggle Status", callback_data=f"sh_tog_{prod_id}"))
        kb.add(InlineKeyboardButton("🗑️ Delete", callback_data=f"sh_del_{prod_id}"), InlineKeyboardButton("🔙 Back", callback_data="shop_manage_menu"))
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, text, reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data == "shop_add_prod")
    def start_add_product(call):
        msg = bot.send_message(call.message.chat.id, "📝 <b>Product Name:</b>")
        bot.register_next_step_handler(msg, process_prod_name, bot)

    def process_prod_name(message, bot):
        name = message.text
        msg = bot.send_message(message.chat.id, "💰 <b>Price:</b>")
        bot.register_next_step_handler(msg, process_prod_price, bot, name)

    def process_prod_price(message, bot, name):
        price = message.text
        msg = bot.send_message(message.chat.id, "📄 <b>Description:</b>")
        bot.register_next_step_handler(msg, process_prod_desc, bot, name, price)

    def process_prod_desc(message, bot, name, price):
        desc = message.text
        cats = get_categories(message.from_user.id)
        if not cats: ask_for_media(message, bot, name, price, desc, None)
        else:
            kb = InlineKeyboardMarkup(row_width=2)
            for cid, cname in cats.items(): kb.add(InlineKeyboardButton(cname, callback_data=f"sel_cat_{cid}"))
            kb.add(InlineKeyboardButton("Skip", callback_data="sel_cat_skip"))
            pending_data[message.from_user.id] = {'name': name, 'price': price, 'desc': desc}
            bot.send_message(message.chat.id, "📂 <b>Select Category:</b>", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sel_cat_"))
    def category_selected(call):
        user_id = call.from_user.id
        data = pending_data.get(user_id)
        if not data: return
        cat_id = call.data.replace("sel_cat_", "")
        if cat_id == "skip": cat_id = None
        ask_for_media(call.message, bot, data['name'], data['price'], data['desc'], cat_id)

    def ask_for_media(message, bot, name, price, desc, cat_id):
        user_id = message.from_user.id
        media_cache[user_id] = [] 
        pending_data[user_id] = {'action': 'add', 'name': name, 'price': price, 'desc': desc, 'category_id': cat_id}
        bot.send_message(message.chat.id, "📸 <b>Upload Gallery:</b>\nSend multiple files.\n⚠️ <b>Type /done to finish.</b>")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_del_"))
    def delete_handler(call):
        if delete_product(call.from_user.id, call.data.replace("sh_del_", "")):
            bot.answer_callback_query(call.id, "✅ Deleted"); render_manage_list(bot, call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_tog_"))
    def toggle_status_handler(call):
        prod_id = call.data.replace("sh_tog_", "")
        if "th_" in call.data: toggle_product_thumbnail(call.from_user.id, prod_id.replace("th_", ""))
        else: toggle_product_status(call.from_user.id, prod_id)
        call.data = f"sh_mng_{prod_id.replace('th_', '')}"
        manage_single_product(call)

    @bot.callback_query_handler(func=lambda c: c.data == "shop_set_banner")
    def start_set_banner(call):
        msg = bot.send_message(call.message.chat.id, "🖼️ Send Banner Photo:")
        bot.register_next_step_handler(msg, process_banner, bot)
    def process_banner(message, bot):
        if message.photo and set_shop_banner(message.from_user.id, message.photo[-1].file_id):
            bot.send_message(message.chat.id, "✅ Banner Set!")
            show_dashboard(bot, message, get_shop(message.from_user.id))

    @bot.callback_query_handler(func=lambda c: c.data == "shop_edit_info")
    def start_edit_info(call):
        msg = bot.send_message(call.message.chat.id, "📝 Send new description:")
        bot.register_next_step_handler(msg, process_edit_desc, bot)
    def process_edit_desc(message, bot):
        if update_shop_desc(message.from_user.id, message.text):
            bot.send_message(message.chat.id, "✅ Updated!")
            show_dashboard(bot, message, get_shop(message.from_user.id))

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ed_cat_"))
    def edit_cat_start(call):
        prod_id = call.data.replace("ed_cat_", "")
        cats = get_categories(call.from_user.id)
        kb = InlineKeyboardMarkup(row_width=2)
        for cid, cname in cats.items(): kb.add(InlineKeyboardButton(cname, callback_data=f"set_cat_{prod_id}_{cid}"))
        kb.add(InlineKeyboardButton("Remove", callback_data=f"set_cat_{prod_id}_none"))
        bot.send_message(call.message.chat.id, "Select Category:", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("set_cat_"))
    def set_new_cat(call):
        parts = call.data.split("_")
        prod_id, cat_id = parts[2], parts[3]
        if cat_id == "none": cat_id = None
        update_product_field(call.from_user.id, prod_id, "category", cat_id)
        bot.send_message(call.message.chat.id, "✅ Updated")
        call.data = f"sh_mng_{prod_id}"
        manage_single_product(call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ed_md_"))
    def edit_media_start(call):
        pid = call.data.replace("ed_md_", "")
        media_cache[call.from_user.id] = []
        pending_data[call.from_user.id] = {'action': 'edit', 'prod_id': pid}
        bot.send_message(call.message.chat.id, "🖼️ Send new files. Type /done.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ed_nm_"))
    def edit_name_start(call):
        pid = call.data.replace("ed_nm_", "")
        msg = bot.send_message(call.message.chat.id, "✏️ New Name:")
        bot.register_next_step_handler(msg, process_edit_field, bot, pid, "name")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ed_pr_"))
    def edit_price_start(call):
        pid = call.data.replace("ed_pr_", "")
        msg = bot.send_message(call.message.chat.id, "✏️ New Price:")
        bot.register_next_step_handler(msg, process_edit_field, bot, pid, "price")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ed_ds_"))
    def edit_desc_start(call):
        pid = call.data.replace("ed_ds_", "")
        msg = bot.send_message(call.message.chat.id, "✏️ New Desc:")
        bot.register_next_step_handler(msg, process_edit_field, bot, pid, "description")

    def process_edit_field(message, bot, pid, field):
        if update_product_field(message.from_user.id, pid, field, message.text):
            bot.send_message(message.chat.id, "✅ Updated")
            call_obj = type('obj', (object,), {'from_user': message.from_user, 'data': f"sh_mng_{pid}", 'message': message, 'id': '0'})
            manage_single_product(call_obj)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("sh_prev_"))
    def preview_product(call):
        prod_id = call.data.replace("sh_prev_", "")
        shop = get_shop(call.from_user.id)
        prod = shop['products'].get(prod_id)
        media_list = prod.get("media", [])
        if "image" in prod: media_list = [{"type": "photo", "file_id": prod["image"]}]
        use_thumbnail = prod.get("use_thumbnail", True)
        cat_tag = ""
        if prod.get("category"):
            cat_name = shop.get("categories", {}).get(prod.get("category"), "")
            if cat_name: cat_tag = f"\n🏷️ <b>#{cat_name}</b>"
        caption = (f"📦 <b>{prod['name']}</b>\n💰 <b>Price:</b> {prod['price']}\n\n📝 {prod.get('description', '')}{cat_tag}\n\n🏪 <b>Seller:</b> {shop['name']}")
        kb = InlineKeyboardMarkup()
        if use_thumbnail and len(media_list) > 1: kb.add(InlineKeyboardButton("📂 Gallery", callback_data="dummy"))
        kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"sh_mng_{prod_id}"))
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
