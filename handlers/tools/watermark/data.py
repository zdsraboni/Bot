# handlers/tools/watermark/data.py

wm_storage = {}

DEFAULT_WM_SETTINGS = {
    "mode": "text",             # 'text' or 'logo'
    "text": "Watermark",
    "text_color": "#FFFFFF",
    "bg_color": "#000000",
    "position": "bottom_right", 
    "opacity": 255,             
    "bg_opacity": 150,          
    "size_pct": 5,              
    "bg_enabled": True,         
    
    # Font Settings
    "font_path": None,          
    "font_name": "Default",
    "font_custom": False,
    "favorites": [], 
    
    # Logo Settings
    "logo_path": None,          
    "logo_scale": 1.0,          
    
    # Advanced
    "rotation": 0,              
    "is_tiled": False,          
    "tile_gap": 20,             
    "tile_mode": "grid",        
    
    # Custom Position
    "pos_x": 0,
    "pos_y": 0
}

def get_wm_settings(chat_id):
    if chat_id not in wm_storage:
        wm_storage[chat_id] = DEFAULT_WM_SETTINGS.copy()
        if "favorites" not in wm_storage[chat_id]:
            wm_storage[chat_id]["favorites"] = []
    return wm_storage[chat_id]

def save_wm_settings(chat_id, key, value):
    if chat_id not in wm_storage:
        wm_storage[chat_id] = DEFAULT_WM_SETTINGS.copy()
    wm_storage[chat_id][key] = value
