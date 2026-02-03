import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils_shop import get_shop, validate_coupon, create_order

# Storage: {user_id: {'shop_id': '123', 'items': [ {id, name, price} ]}}
cart_sessions = {}

def register_cart_handlers(bot):

    # --- ADD TO CART ---
    @bot.callback_query_handler(func=lambda c: c.data.startswith("add_cart_"))
    def add_to_cart(call):
        parts = call.data.split("_")
        shop_id = parts[2]
        prod_id = "_".join(parts[3:])
        
        shop = get_shop(shop_id)
        if not shop: return
        prod = shop["products"].get(prod_id)
        
        user_id = call.from_user.id
        if user_id not in cart_sessions:
            cart_sessions[user_id] = {'shop_id': shop_id, 'items': []}
        
        # If user switches shop, reset cart
        if cart_sessions[user_id]['shop_id'] != shop_id:
            cart_sessions[user_id] = {'shop_id': shop_id, 'items': []}
            
        cart_sessions[user_id]['items'].append({
            'id': prod_id,
            'name': prod['name'],
            'price': float(prod['price'])
        })
        
        bot.answer_callback_query(call.id, f"✅ Added: {prod['name']}")

    # --- VIEW CART ---
    @bot.callback_query_handler(func=lambda c: c.data == "view_cart_main")
    def view_cart(call):
        user_id = call.from_user.id
        cart = cart_sessions.get(user_id)
        
        if not cart or not cart['items']:
            bot.answer_callback_query(call.id, "🛒 Your cart is empty.", show_alert=True)
            return
            
        shop_id = cart['shop_id']
        shop = get_shop(shop_id)
        
        total = sum(item['price'] for item in cart['items'])
        
        text = f"🛒 <b>Shopping Cart</b>\n🏪 <b>Shop:</b> {shop['name']}\n\n"
        for i, item in enumerate(cart['items']):
            text += f"{i+1}. {item['name']} - {item['price']}\n"
            
        text += f"\n💰 <b>Total: {total}</b>"
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("✅ Checkout", callback_data="cart_checkout_start"))
        kb.add(InlineKeyboardButton("🗑️ Clear Cart", callback_data="cart_clear"))
        kb.add(InlineKeyboardButton("🔙 Back to Shop", callback_data=f"view_prods_{shop_id}"))
        
        bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")

    # --- CLEAR CART ---
    @bot.callback_query_handler(func=lambda c: c.data == "cart_clear")
    def clear_cart(call):
        if call.from_user.id in cart_sessions:
            del cart_sessions[call.from_user.id]
        bot.answer_callback_query(call.id, "🗑️ Cart Cleared!")
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass

    # --- CHECKOUT FLOW (CART) ---
    @bot.callback_query_handler(func=lambda c: c.data == "cart_checkout_start")
    def cart_checkout_step1(call):
        cart = cart_sessions.get(call.from_user.id)
        if not cart: return
        
        total = sum(item['price'] for item in cart['items'])
        
        msg = f"🛒 <b>Cart Checkout</b>\n\n💰 Total: {total}\n👇 Do you have a coupon?"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🎟️ Apply Coupon", callback_data=f"cart_ask_coup"))
        kb.add(InlineKeyboardButton("✅ Confirm Order", callback_data=f"cart_fin_{total}_NONE"))
        
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=msg, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "cart_ask_coup")
    def cart_ask_coupon(call):
        msg = bot.send_message(call.message.chat.id, "🎟️ <b>Enter Coupon Code:</b>")
        bot.register_next_step_handler(msg, process_cart_coupon, bot)

    def process_cart_coupon(message, bot):
        user_id = message.from_user.id
        cart = cart_sessions.get(user_id)
        if not cart: return
        
        code = message.text.strip()
        coupon = validate_coupon(cart['shop_id'], code)
        original_total = sum(item['price'] for item in cart['items'])
        
        try:
            if coupon:
                if coupon['type'] == 'percent':
                    discount = (original_total * coupon['value']) / 100
                    final = original_total - discount
                else:
                    final = original_total - coupon['value']
                
                if final < 0: final = 0
                
                msg = f"✅ <b>Coupon Applied!</b>\nOriginal: {original_total}\n<b>New Price: {final}</b>"
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("✅ Confirm Order", callback_data=f"cart_fin_{final}_{code}"))
                bot.send_message(message.chat.id, msg, reply_markup=kb, parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "❌ Invalid Coupon.")
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("✅ Confirm Original", callback_data=f"cart_fin_{original_total}_NONE"))
                bot.send_message(message.chat.id, f"💰 Price: {original_total}", reply_markup=kb)
        except: pass

    @bot.callback_query_handler(func=lambda c: c.data.startswith("cart_fin_"))
    def cart_ask_proof(call):
        parts = call.data.split("_")
        price = parts[2]
        
        cart = cart_sessions.get(call.from_user.id)
        if not cart: return
        shop = get_shop(cart['shop_id'])
        pay_info = shop.get("payment_info", "Contact Seller")
        
        msg = (
            f"🧾 <b>Payment Instructions</b>\n{pay_info}\n\n"
            f"💰 <b>Total to Pay: {price}</b>\n\n"
            f"📸 <b>Send Payment Screenshot now.</b>"
        )
        sent = bot.send_message(call.message.chat.id, msg, parse_mode="HTML")
        bot.register_next_step_handler(sent, process_cart_proof, bot, price)

    def process_cart_proof(message, bot, price):
        if message.content_type == 'photo':
            user_id = message.from_user.id
            cart = cart_sessions.get(user_id)
            if not cart: return
            
            shop_id = cart['shop_id']
            file_id = message.photo[-1].file_id
            
            # Generate Item Summary
            item_summary = ", ".join([i['name'] for i in cart['items']])
            # Truncate if too long
            if len(item_summary) > 50: item_summary = f"{len(cart['items'])} items (See list)"
            
            order_id = create_order(shop_id, user_id, message.from_user.first_name, item_summary, price, file_id, order_type="product")
            
            # Clear Cart
            del cart_sessions[user_id]
            
            bot.reply_to(message, "✅ <b>Proof Submitted!</b>\nOrder Sent to Seller.")
            
            # Notify Seller
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("✅ Approve", callback_data=f"ord_pay_ok_{shop_id}_{order_id}"),
                   InlineKeyboardButton("❌ Reject", callback_data=f"ord_pay_no_{shop_id}_{order_id}"))
            
            caption = (
                f"🔔 <b>New Cart Order #{order_id[-4:]}</b>\n"
                f"👤 Buyer: {message.from_user.first_name}\n"
                f"📦 Items: {item_summary}\n"
                f"💰 Total: {price}\n"
                f"👇 <b>Payment Proof:</b>"
            )
            bot.send_photo(shop_id, file_id, caption=caption, reply_markup=kb, parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ Please send a photo.")
