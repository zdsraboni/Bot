from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.main_menu import main_menu
from utils.utils import get_text, track_user, delete_msg # New Import
from utils.utils_shop import get_shop

def register_start(bot):
    @bot.message_handler(commands=["start"])
    def start(message):
        # 🧹 Auto Clean: Delete User's Command
        delete_msg(bot, message)
        
        user_id = message.from_user.id
        track_user(message.from_user)
        
        args = message.text.split()
        
        # --- SHOP DEEP LINK ---
        if len(args) > 1 and args[1].startswith("shop_"):
            shop_owner_id = args[1].replace("shop_", "")
            shop = get_shop(shop_owner_id)
            
            if shop:
                text = (
                    f"🏪 <b>Welcome to {shop['name']}</b>\n"
                    f"<i>{shop['description']}</i>\n\n"
                    f"👇 <b>Browse our products below:</b>"
                )
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("📦 Browse Products", callback_data=f"view_prods_{shop_owner_id}"))
                kb.add(InlineKeyboardButton("🏠 Create My Own Shop", callback_data="main_menu_return"))
                
                # --- CHECK FOR BANNER ---
                if shop.get("banner"):
                    # Send Photo with Caption
                    bot.send_photo(
                        message.chat.id,
                        shop["banner"],
                        caption=text,
                        reply_markup=kb
                    )
                else:
                    # Fallback to Text
                    bot.send_message(message.chat.id, text, reply_markup=kb)
                return
            else:
                bot.send_message(message.chat.id, "❌ <b>Error:</b> Shop not found.")
        
        # --- NORMAL START ---
        welcome_text = get_text("start_message", "👋 Welcome!")
        bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(user_id))
