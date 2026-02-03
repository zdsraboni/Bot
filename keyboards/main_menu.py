from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.utils import is_admin, get_data

# ✅ প্লাগিন হেল্পার
try:
    from handlers.plugin_manager import get_dynamic_tools
except ImportError:
    def get_dynamic_tools(only_active=True): return []

# =================================================
# 🏠 MAIN MENU (Fixed Layout)
# =================================================
def main_menu(user_id):
    kb = InlineKeyboardMarkup(row_width=2)
    
    # Row 1
    kb.add(
        InlineKeyboardButton("🛠 Tools", callback_data="tools"),
        InlineKeyboardButton("🛒 Marketplace", callback_data="shop")
    )
    # Row 2
    kb.add(InlineKeyboardButton("💼 My Business", callback_data="my_business"))
    
    # Admin Row
    if is_admin(user_id):
        kb.add(InlineKeyboardButton("👮 Admin Panel", callback_data="main_btn_admin"))

    return kb

# =================================================
# 🛠 TOOLS MENU (With Mute Filtering)
# =================================================
def tools_layout():
    kb = InlineKeyboardMarkup(row_width=2)
    
    # ডাটাবেস থেকে স্ট্যাটাস আনা (True = Enabled, False = Muted)
    status_db = get_data("tools_status", {})

    # হেল্পার: চেক করে টুল এনাবল আছে কি না (ডিফল্ট True)
    def is_enabled(code):
        return status_db.get(code, True)

    # --- 1. Built-in Tools (Filtered) ---
    builtin_row = []
    
    if is_enabled("tool_url_shortener"):
        builtin_row.append(InlineKeyboardButton("🔗 URL Shortener", callback_data="tool_url_shortener"))
    
    if is_enabled("tool_img"):
        builtin_row.append(InlineKeyboardButton("🎨 Watermark", callback_data="tool_img"))
        
    if is_enabled("open_management"):
        builtin_row.append(InlineKeyboardButton("🛡️ Group Manage", callback_data="open_management"))
        
    if is_enabled("tool_weather"):
        builtin_row.append(InlineKeyboardButton("🌤 Weather", callback_data="tool_weather"))

    # বাটন সাজানো (২টা করে)
    temp_bi = []
    for btn in builtin_row:
        temp_bi.append(btn)
        if len(temp_bi) == 2:
            kb.row(*temp_bi)
            temp_bi = []
    if temp_bi: kb.row(*temp_bi)

    # --- 2. 🔌 DYNAMIC PLUGINS (Filtered) ---
    # only_active=True পাঠানোর ফলে মিউট করা টুলগুলো আসবে না
    dynamic_buttons = get_dynamic_tools(only_active=True)
    
    temp_dyn = []
    for label, callback in dynamic_buttons:
        temp_dyn.append(InlineKeyboardButton(label, callback_data=callback))
        if len(temp_dyn) == 2:
            kb.row(*temp_dyn)
            temp_dyn = []
    if temp_dyn: kb.row(*temp_dyn)

    # --- 3. Navigation ---
    kb.add(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu_return"))
    
    return "🛠 **Tools Menu:**\nSelect a tool from below:", kb
