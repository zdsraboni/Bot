import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from utils.utils_shop import get_shop, add_product_review, get_product_reviews

review_sessions = {}

def register_social_handlers(bot):

    @bot.callback_query_handler(func=lambda c: c.data == "shop_broadcast")
    def start_broadcast(call):
        msg = bot.send_message(call.message.chat.id, "📢 <b>Broadcast</b>\nSend message (Text/Photo).")
        bot.register_next_step_handler(msg, process_broadcast, bot)

    def process_broadcast(message, bot):
        shop = get_shop(message.from_user.id)
        if not shop: return
        buyers = shop.get("approved_users", [])
        if not buyers:
            bot.send_message(message.chat.id, "❌ No buyers.")
            return
        bot.send_message(message.chat.id, f"⏳ Sending to {len(buyers)} users...")
        count = 0
        for uid in buyers:
            try:
                if message.content_type == 'text':
                    bot.send_message(uid, f"📢 <b>From {shop['name']}</b>\n\n{message.text}", parse_mode="HTML")
                elif message.content_type == 'photo':
                    bot.send_photo(uid, message.photo[-1].file_id, caption=f"📢 <b>From {shop['name']}</b>\n\n{message.caption or ''}", parse_mode="HTML")
                count += 1
            except: pass
        bot.send_message(message.chat.id, f"✅ Sent: {count}")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("rate_prod_"))
    def start_rating(call):
        parts = call.data.split("_")
        shop_id, prod_id = parts[2], "_".join(parts[3:])
        kb = InlineKeyboardMarkup(row_width=5)
        btns = [InlineKeyboardButton(f"{i}⭐", callback_data=f"set_star_{shop_id}_{prod_id}_{i}") for i in range(1, 6)]
        kb.add(*btns)
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"sh_view_{shop_id}_{prod_id}"))
        try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="✍️ <b>Rate Product:</b>", reply_markup=kb)
        except: bot.send_message(call.message.chat.id, "✍️ <b>Rate Product:</b>", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("set_star_"))
    def set_star_rating(call):
        parts = call.data.split("_")
        shop_id, prod_id, rating = parts[2], parts[3], int(parts[4])
        review_sessions[call.from_user.id] = {'shop_id': shop_id, 'prod_id': prod_id, 'rating': rating}
        msg = bot.send_message(call.message.chat.id, f"⭐ <b>{rating} Stars!</b>\nSend review text:")
        bot.register_next_step_handler(msg, process_review_text, bot)

    def process_review_text(message, bot):
        user_id = message.from_user.id
        data = review_sessions.get(user_id)
        if not data: return
        add_product_review(data['shop_id'], data['prod_id'], user_id, message.from_user.first_name, data['rating'], message.text)
        bot.send_message(message.chat.id, "✅ Review Posted!")
        del review_sessions[user_id]
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back to Product", callback_data=f"sh_view_{data['shop_id']}_{data['prod_id']}"))
        bot.send_message(message.chat.id, "Thanks!", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("view_revs_"))
    def view_reviews(call):
        parts = call.data.split("_")
        shop_id, prod_id = parts[2], "_".join(parts[3:])
        reviews = get_product_reviews(shop_id, prod_id)
        if not reviews:
            bot.answer_callback_query(call.id, "No reviews yet.", show_alert=True)
            return
        text = f"⭐ <b>Reviews</b>\n\n"
        for r in reviews[-5:]: text += f"👤 <b>{r['name']}</b> ({r['rating']}⭐)\n💬 <i>{r['text']}</i>\n\n"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Back", callback_data=f"sh_view_{shop_id}_{prod_id}"))
        bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")

# --- HELPER: POST TO CHANNEL ---
def post_product_to_channel(bot, channel_id, prod, shop_name, shop_owner_id, bot_username):
    try:
        media_list = prod.get("media", [])
        shop_link = f"https://t.me/{bot_username}?start=shop_{shop_owner_id}" if shop_owner_id else f"https://t.me/{bot_username}"
        caption = (f"🛍️ <b>NEW ARRIVAL</b>\n\n📦 <b>{prod['name']}</b>\n💰 <b>Price:</b> {prod['price']}\n\n📝 {prod.get('description', '')}\n\n🏪 <b>Shop:</b> {shop_name}\n👇 <b>Buy Here:</b>\n{shop_link}")
        
        if not media_list: bot.send_message(channel_id, caption, parse_mode="HTML")
        elif len(media_list) == 1:
            m = media_list[0]
            if m["type"] == "photo": bot.send_photo(channel_id, m["file_id"], caption=caption, parse_mode="HTML")
            else: bot.send_video(channel_id, m["file_id"], caption=caption, parse_mode="HTML")
        else:
            album = []
            for i, m in enumerate(media_list):
                cap = caption if i == 0 else ""
                if m["type"] == "photo": album.append(InputMediaPhoto(m["file_id"], caption=cap, parse_mode="HTML"))
                elif m["type"] == "video": album.append(InputMediaVideo(m["file_id"], caption=cap, parse_mode="HTML"))
            bot.send_media_group(channel_id, album)
        return True
    except Exception as e:
        print(f"Post Error: {e}")
        return False
