import os
from telebot import types
from handlers.tools.group_management.data import get_data, save_wm_settings
from handlers.tools.watermark_engine import apply_watermark

# স্টেট ম্যানেজমেন্ট
user_states = {} 
last_menu_ids = {} # মেনু ক্লিন রাখার জন্য

# ---------------------------------------------------------
# 🛠️ HELPER FUNCTIONS
# ---------------------------------------------------------

def get_wm_settings(chat_id):
    return get_data(chat_id)['wm_settings']

def update_wm(chat_id, key, value):
    save_wm_settings(chat_id, key, value)

def delete_prev_menu(bot, chat_id):
    if chat_id in last_menu_ids:
        try: bot.delete_message(chat_id, last_menu_ids[chat_id])
        except: pass

def register_menu_id(chat_id, msg_id):
    last_menu_ids[chat_id] = msg_id

# ---------------------------------------------------------
# 🖥️ MENU LAYOUTS (Original UI Restored)
# ---------------------------------------------------------

def send_main_menu(bot, chat_id, message_id=None):
    s = get_wm_settings(chat_id)
    mode = s.get('mode', 'text')
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Row 1: Mode & Preview
    markup.add(
        types.InlineKeyboardButton(f"🔤 Mode: {mode.upper()}", callback_data="wm_toggle_mode"),
        types.InlineKeyboardButton("👁️ Preview", callback_data="wm_do_preview")
    )

    if mode == 'text':
        # Text Controls
        markup.add(types.InlineKeyboardButton("✍️ Edit Text", callback_data="wm_set_text"))
        markup.row(
            types.InlineKeyboardButton(f"🔠 Font", callback_data="wm_menu_fonts"),
            types.InlineKeyboardButton("🎨 Colors", callback_data="wm_menu_colors")
        )
        markup.row(
            types.InlineKeyboardButton(f"🔳 Box: {'ON' if s['bg_enabled'] else 'OFF'}", callback_data="wm_tog_bg"),
            types.InlineKeyboardButton("📐 Style", callback_data="wm_menu_style")
        )
        markup.row(
            types.InlineKeyboardButton("📏 Size", callback_data="wm_menu_size"),
            types.InlineKeyboardButton("👻 Opacity", callback_data="wm_menu_op")
        )
    else:
        # Logo Controls
        markup.add(types.InlineKeyboardButton("📤 Change Logo", callback_data="wm_up_logo"))
        markup.row(
            types.InlineKeyboardButton("➖ Smaller", callback_data="wm_logo_dec"),
            types.InlineKeyboardButton(f"🔍 Scale: {int(s.get('logo_scale', 1.0)*100)}%", callback_data="ignore"),
            types.InlineKeyboardButton("➕ Bigger", callback_data="wm_logo_inc")
        )
        markup.row(
            types.InlineKeyboardButton("👻 Opacity", callback_data="wm_menu_op"),
            types.InlineKeyboardButton("📐 Style", callback_data="wm_menu_style")
        )

    # Common Controls
    markup.add(types.InlineKeyboardButton("💠 Pattern / Position", callback_data="wm_menu_tile"))
    markup.add(types.InlineKeyboardButton("🔙 Back to Tools", callback_data="tools"))

    text = (
        f"🎛️ **Watermark Studio**\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📝 **Text:** `{s.get('text', 'Watermark')}`\n"
        f"📍 **Position:** `{s.get('position')}`\n"
        f"🎨 **Ready to Edit**"
    )

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
            register_menu_id(chat_id, message_id)
            return
        except: pass
    
    delete_prev_menu(bot, chat_id)
    sent = bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    register_menu_id(chat_id, sent.message_id)

# ---------------------------------------------------------
# 🎮 HANDLERS REGISTRATION
# ---------------------------------------------------------

def register_watermark_ui(bot):

    # --- 1. ENTRY POINT ---
    @bot.callback_query_handler(func=lambda c: c.data == "tool_img")
    def open_studio(c):
        user_states[c.message.chat.id] = "waiting_for_photo_main"
        send_main_menu(bot, c.message.chat.id, c.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "wm_menu_main")
    def back_to_main(c):
        send_main_menu(bot, c.message.chat.id, c.message.message_id)

    # --- 2. PREVIEW SYSTEM ---
    @bot.callback_query_handler(func=lambda c: c.data == "wm_do_preview")
    def do_preview(c):
        chat_id = c.message.chat.id
        bot.answer_callback_query(c.id, "⏳ Generating Preview...")
        
        try:
            # Create a blank dummy image for preview
            from PIL import Image
            preview_img = Image.new('RGB', (1280, 720), (200, 200, 200))
            temp_in = f"prev_in_{chat_id}.jpg"
            temp_out = f"prev_out_{chat_id}.jpg"
            preview_img.save(temp_in)
            
            # Apply Watermark
            s = get_wm_settings(chat_id)
            apply_watermark(temp_in, temp_out, s)
            
            # Send Photo
            with open(temp_out, 'rb') as f:
                bot.send_photo(chat_id, f, caption="👁️ **Live Preview**")
            
            # Cleanup
            os.remove(temp_in)
            os.remove(temp_out)
            
            # Show menu again
            send_main_menu(bot, chat_id)
            
        except Exception as e:
            bot.answer_callback_query(c.id, f"Error: {e}", show_alert=True)

    # --- 3. MODE & TEXT ---
    @bot.callback_query_handler(func=lambda c: c.data == "wm_toggle_mode")
    def toggle_mode(c):
        s = get_wm_settings(c.message.chat.id)
        new_mode = 'logo' if s.get('mode') == 'text' else 'text'
        update_wm(c.message.chat.id, "mode", new_mode)
        send_main_menu(bot, c.message.chat.id, c.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "wm_set_text")
    def set_text_prompt(c):
        user_states[c.message.chat.id] = "waiting_wm_text"
        delete_prev_menu(bot, c.message.chat.id)
        msg = bot.send_message(c.message.chat.id, "✍️ **আপনার ওয়াটারমার্ক টেক্সট লিখুন:**")
        register_menu_id(c.message.chat.id, msg.message_id)

    # --- 4. POSITION & TILING ---
    @bot.callback_query_handler(func=lambda c: c.data == "wm_menu_tile")
    def menu_tile(c):
        s = get_wm_settings(c.message.chat.id)
        is_tiled = s.get('is_tiled', False)
        
        mk = types.InlineKeyboardMarkup(row_width=2)
        mk.add(types.InlineKeyboardButton(f"{'✅' if is_tiled else '❌'} Pattern Mode", callback_data="wm_tog_tile_act"))
        
        if is_tiled:
            mk.add(
                types.InlineKeyboardButton("Grid", callback_data="wm_tm_grid"),
                types.InlineKeyboardButton("Horizontal", callback_data="wm_tm_horizontal"),
                types.InlineKeyboardButton("Vertical", callback_data="wm_tm_vertical")
            )
            mk.add(
                types.InlineKeyboardButton("➖ Gap", callback_data="wm_gap_dec"),
                types.InlineKeyboardButton("➕ Gap", callback_data="wm_gap_inc")
            )
        else:
            mk.add(
                types.InlineKeyboardButton("↖️ Top Left", callback_data="wm_pos_top_left"),
                types.InlineKeyboardButton("↗️ Top Right", callback_data="wm_pos_top_right"),
                types.InlineKeyboardButton("↙️ Bot Left", callback_data="wm_pos_bottom_left"),
                types.InlineKeyboardButton("↘️ Bot Right", callback_data="wm_pos_bottom_right"),
                types.InlineKeyboardButton("⏺️ Center", callback_data="wm_pos_center")
            )
        
        mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="wm_menu_main"))
        bot.edit_message_text("💠 **Position & Pattern**", c.message.chat.id, c.message.message_id, reply_markup=mk, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data == "wm_tog_tile_act")
    def toggle_tile_action(c):
        curr = get_wm_settings(c.message.chat.id).get('is_tiled', False)
        update_wm(c.message.chat.id, "is_tiled", not curr)
        c.data = "wm_menu_tile" # Redirect
        menu_tile(c)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("wm_pos_"))
    def set_pos_action(c):
        pos = c.data.replace("wm_pos_", "")
        update_wm(c.message.chat.id, "position", pos)
        update_wm(c.message.chat.id, "pos_x", 0) # Reset custom
        update_wm(c.message.chat.id, "pos_y", 0)
        bot.answer_callback_query(c.id, "✅ Position Set!")
        send_main_menu(bot, c.message.chat.id, c.message.message_id)

    # --- 5. STYLE & OPACITY ---
    @bot.callback_query_handler(func=lambda c: c.data == "wm_menu_style")
    def menu_style(c):
        mk = types.InlineKeyboardMarkup(row_width=2)
        mk.add(
            types.InlineKeyboardButton("📐 Rotate: 0°", callback_data="wm_rot_0"),
            types.InlineKeyboardButton("📐 Rotate: 45°", callback_data="wm_rot_45"),
            types.InlineKeyboardButton("📐 Rotate: 90°", callback_data="wm_rot_90"),
            types.InlineKeyboardButton("✏️ Custom Angle", callback_data="wm_rot_cust")
        )
        mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="wm_menu_main"))
        bot.edit_message_text("✨ **Style & Rotation**", c.message.chat.id, c.message.message_id, reply_markup=mk, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("wm_rot_"))
    def set_rotation(c):
        val = c.data.split("_")[2]
        if val == "cust":
            user_states[c.message.chat.id] = "waiting_angle"
            delete_prev_menu(bot, c.message.chat.id)
            msg = bot.send_message(c.message.chat.id, "📐 **এঙ্গেল লিখুন (0-360):**")
            register_menu_id(c.message.chat.id, msg.message_id)
        else:
            update_wm(c.message.chat.id, "rotation", int(val))
            send_main_menu(bot, c.message.chat.id, c.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "wm_menu_op")
    def menu_opacity(c):
        mk = types.InlineKeyboardMarkup(row_width=2)
        mk.add(
            types.InlineKeyboardButton("Deep (100%)", callback_data="wm_op_255"),
            types.InlineKeyboardButton("Medium (70%)", callback_data="wm_op_180"),
            types.InlineKeyboardButton("Light (40%)", callback_data="wm_op_100"),
            types.InlineKeyboardButton("Ghost (15%)", callback_data="wm_op_40")
        )
        mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="wm_menu_main"))
        bot.edit_message_text("👻 **Opacity (স্বচ্ছতা)**", c.message.chat.id, c.message.message_id, reply_markup=mk, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("wm_op_"))
    def set_opacity(c):
        val = int(c.data.split("_")[2])
        update_wm(c.message.chat.id, "opacity", val)
        send_main_menu(bot, c.message.chat.id, c.message.message_id)

    # --- 6. COLORS & FONTS ---
    @bot.callback_query_handler(func=lambda c: c.data == "wm_menu_colors")
    def menu_colors(c):
        mk = types.InlineKeyboardMarkup(row_width=3)
        colors = {"⚪": "#FFFFFF", "⚫": "#000000", "🔴": "#FF0000", "🟢": "#00FF00", "🔵": "#0000FF", "🟡": "#FFFF00"}
        btns = []
        for icon, hex_c in colors.items():
            btns.append(types.InlineKeyboardButton(icon, callback_data=f"wm_col_{hex_c}"))
        mk.add(*btns)
        mk.add(types.InlineKeyboardButton("✏️ Custom Hex", callback_data="wm_col_cust"))
        mk.add(types.InlineKeyboardButton("🔙 Back", callback_data="wm_menu_main"))
        bot.edit_message_text("🎨 **Text Color**", c.message.chat.id, c.message.message_id, reply_markup=mk, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("wm_col_"))
    def set_color(c):
        val = c.data.replace("wm_col_", "")
        if val == "cust":
            user_states[c.message.chat.id] = "waiting_color"
            delete_prev_menu(bot, c.message.chat.id)
            msg = bot.send_message(c.message.chat.id, "🎨 **Hex Code পাঠান (e.g. #FF5733):**")
            register_menu_id(c.message.chat.id, msg.message_id)
        else:
            update_wm(c.message.chat.id, "text_color", val)
            send_main_menu(bot, c.message.chat.id, c.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "wm_tog_bg")
    def toggle_bg(c):
        curr = get_wm_settings(c.message.chat.id).get('bg_enabled', True)
        update_wm(c.message.chat.id, "bg_enabled", not curr)
        send_main_menu(bot, c.message.chat.id, c.message.message_id)

    # --- 7. LOGO HANDLING ---
    @bot.callback_query_handler(func=lambda c: c.data == "wm_up_logo")
    def ask_logo(c):
        user_states[c.message.chat.id] = "waiting_logo"
        delete_prev_menu(bot, c.message.chat.id)
        msg = bot.send_message(c.message.chat.id, "📤 **আপনার লোগো (PNG/JPG) পাঠান:**")
        register_menu_id(c.message.chat.id, msg.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("wm_logo_"))
    def adjust_logo(c):
        s = get_wm_settings(c.message.chat.id)
        curr = s.get('logo_scale', 1.0)
        new_val = curr + 0.1 if "inc" in c.data else curr - 0.1
        if new_val < 0.1: new_val = 0.1
        update_wm(c.message.chat.id, "logo_scale", new_val)
        send_main_menu(bot, c.message.chat.id, c.message.message_id)

    # --- 8. INPUT LISTENER (TEXT/PHOTO/LOGO) ---
    @bot.message_handler(content_types=['text', 'photo', 'document'], func=lambda m: m.chat.type == 'private')
    def handle_watermark_inputs(m):
        state = user_states.get(m.chat.id)
        
        # Text Input
        if state == "waiting_wm_text" and m.text:
            update_wm(m.chat.id, "text", m.text)
            user_states[m.chat.id] = "waiting_for_photo_main" # Reset state
            bot.reply_to(m, f"✅ টেক্সট সেট হয়েছে: {m.text}")
            send_main_menu(bot, m.chat.id)
            return

        # Color Input
        if state == "waiting_color" and m.text:
            update_wm(m.chat.id, "text_color", m.text.strip())
            user_states[m.chat.id] = "waiting_for_photo_main"
            send_main_menu(bot, m.chat.id)
            return

        # Logo Upload
        if state == "waiting_logo" and (m.photo or m.document):
            try:
                fid = m.photo[-1].file_id if m.photo else m.document.file_id
                file_info = bot.get_file(fid)
                downloaded = bot.download_file(file_info.file_path)
                
                # Save Logo
                logo_path = f"logo_{m.chat.id}.png"
                with open(logo_path, 'wb') as f: f.write(downloaded)
                
                update_wm(m.chat.id, "logo_path", logo_path)
                update_wm(m.chat.id, "mode", "logo")
                
                user_states[m.chat.id] = "waiting_for_photo_main"
                bot.reply_to(m, "✅ লোগো সেভ হয়েছে!")
                send_main_menu(bot, m.chat.id)
            except Exception as e:
                bot.reply_to(m, f"❌ লোগো এরর: {e}")
            return

        # Photo Processing (Main Action)
        if (state == "waiting_for_photo_main" or state is None) and m.photo:
            # If user sends photo while in watermark menu, process it
            # Check if this user has opened the tool recently (optional check)
            
            msg = bot.reply_to(m, "🎨 ওয়াটারমার্ক যুক্ত করা হচ্ছে...")
            try:
                file_info = bot.get_file(m.photo[-1].file_id)
                downloaded = bot.download_file(file_info.file_path)
                in_path = f"temp_ui_in_{m.chat.id}.jpg"
                out_path = f"temp_ui_out_{m.chat.id}.jpg"
                
                with open(in_path, 'wb') as f: f.write(downloaded)
                
                # Apply Settings
                s = get_wm_settings(m.chat.id)
                apply_watermark(in_path, out_path, s)
                
                with open(out_path, 'rb') as f:
                    bot.send_photo(m.chat.id, f, caption="✅ Watermark Applied!")
                
                bot.delete_message(m.chat.id, msg.message_id)
                os.remove(in_path)
                os.remove(out_path)
                
                # Show menu again for next edit
                send_main_menu(bot, m.chat.id)
                
            except Exception as e:
                bot.reply_to(m, f"❌ এরর: {e}")
