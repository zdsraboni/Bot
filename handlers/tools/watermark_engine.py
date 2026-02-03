import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageColor

# ==============================================================================
# ⚙️ DEFAULT SETTINGS (Features Preserved)
# ==============================================================================
DEFAULT_WM_SETTINGS = {
    "mode": "text",             # 'text' or 'logo'
    "text": "Watermark",
    "text_color": "#FFFFFF",
    "bg_color": "#000000",
    "position": "bottom_right", # top_left, bottom_right, center, custom
    "opacity": 255,             # 0-255 (Text/Logo opacity)
    "bg_opacity": 150,          # 0-255 (Background box opacity)
    "size_pct": 5,              # Font size percentage relative to image
    "bg_enabled": True,         # Text Box enable/disable
    "font_path": None,          # Custom font path (.ttf)
    
    # Logo Settings
    "logo_path": None,          # Path to logo file
    "logo_scale": 1.0,          # Logo scaling factor
    
    # Advanced Settings
    "rotation": 0,              # Angle 0-360
    "is_tiled": False,          # Pattern Mode
    "tile_gap": 20,             # Gap between tiles
    "tile_mode": "grid",        # grid, vertical, horizontal
    
    # Custom Position
    "pos_x": 0,
    "pos_y": 0
}

# ==============================================================================
# 🛠️ HELPER FUNCTIONS
# ==============================================================================

def get_color_rgb(hex_code):
    try:
        return ImageColor.getrgb(hex_code)
    except:
        return (255, 255, 255)

def apply_opacity(image, opacity_val):
    if opacity_val == 255:
        return image
    alpha = image.split()[3]
    factor = opacity_val / 255.0
    alpha = ImageEnhance.Brightness(alpha).enhance(factor)
    image.putalpha(alpha)
    return image

# ==============================================================================
# 🎨 MAIN PROCESSING ENGINE
# ==============================================================================

def apply_watermark(input_image_path, output_image_path, settings=None):
    """
    Apply watermark with full feature support (Text/Logo, Tiling, Rotation, etc.)
    """
    # 1. Load Settings (Merge with defaults)
    s = DEFAULT_WM_SETTINGS.copy()
    if settings:
        s.update(settings)

    # 2. Open Image
    try:
        img = Image.open(input_image_path).convert("RGBA")
    except Exception as e:
        print(f"Error opening image: {e}")
        return None

    width, height = img.size
    watermark_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    
    wm_content = None

    # ---------------------------------------------------------
    # LAYER 1: CONTENT PREPARATION (TEXT OR LOGO)
    # ---------------------------------------------------------
    
    # --- LOGO MODE ---
    if s["mode"] == "logo" and s["logo_path"] and os.path.exists(s["logo_path"]):
        try:
            wm_content = Image.open(s["logo_path"]).convert("RGBA")
            scale = s.get("logo_scale", 1.0)
            
            # Smart Resize (Approx 20% of base image * scale)
            base_w = int(min(width, height) * 0.2 * scale)
            w_ratio = base_w / float(wm_content.size[0])
            h_size = int(float(wm_content.size[1]) * float(w_ratio))
            
            wm_content = wm_content.resize((base_w, h_size), Image.Resampling.LANCZOS)
            wm_content = apply_opacity(wm_content, s["opacity"])
        except Exception as e:
            print(f"Error loading logo: {e}")
            return None

    # --- TEXT MODE ---
    elif s["mode"] == "text":
        text = s.get("text", "Watermark")
        font_size = int(min(width, height) * (s.get("size_pct", 5) / 100))
        
        # Font Loading
        font = None
        if s.get("font_path") and os.path.exists(s["font_path"]):
            try:
                font = ImageFont.truetype(s["font_path"], font_size)
            except:
                pass
        
        if not font:
            # Fallback to default
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()

        # Measure Text
        draw_temp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = draw_temp.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Create Text Canvas
        txt_img = Image.new("RGBA", (text_w + 40, text_h + 40), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)

        # Background Box
        if s["bg_enabled"]:
            bg_col = get_color_rgb(s["bg_color"]) + (s["bg_opacity"],)
            txt_draw.rectangle([0, 0, text_w + 20, text_h + 20], fill=bg_col)

        # Draw Text
        txt_col = get_color_rgb(s["text_color"]) + (s["opacity"],)
        txt_draw.text((10, 10), text, font=font, fill=txt_col)

        wm_content = txt_img

    # Fallback if content creation failed
    if not wm_content:
        return img.convert("RGB")

    # ---------------------------------------------------------
    # LAYER 2: ROTATION
    # ---------------------------------------------------------
    if s["rotation"] != 0:
        wm_content = wm_content.rotate(s["rotation"], expand=True, resample=Image.BICUBIC)

    # ---------------------------------------------------------
    # LAYER 3: POSITIONING & TILING
    # ---------------------------------------------------------
    wm_w, wm_h = wm_content.size

    if s["is_tiled"]:
        # TILING PATTERN
        gap = s.get("tile_gap", 20)
        mode = s.get("tile_mode", "grid")

        for y in range(0, height, wm_h + gap):
            for x in range(0, width, wm_w + gap):
                # Skip based on pattern mode
                if mode == "vertical" and x > 0: continue
                if mode == "horizontal" and y > 0: continue
                
                watermark_layer.paste(wm_content, (x, y), wm_content)
    else:
        # SINGLE POSITION
        padding = 20
        x, y = 0, 0
        pos = s["position"]

        if pos == "custom":
            x, y = s.get("pos_x", 0), s.get("pos_y", 0)
        elif pos == "top_left":
            x, y = padding, padding
        elif pos == "bottom_left":
            x, y = padding, height - wm_h - padding
        elif pos == "center":
            x, y = (width - wm_w) // 2, (height - wm_h) // 2
        else: # bottom_right (default)
            x, y = width - wm_w - padding, height - wm_h - padding

        watermark_layer.paste(wm_content, (x, y), wm_content)

    # ---------------------------------------------------------
    # LAYER 4: COMPOSITING & SAVING
    # ---------------------------------------------------------
    result = Image.alpha_composite(img, watermark_layer)
    final_img = result.convert("RGB")
    
    final_img.save(output_image_path, "JPEG", quality=95)
    return output_image_path
