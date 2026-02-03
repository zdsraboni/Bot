import qrcode
import json
import os
import math
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# -------------------------------
# CONFIGURATION & DATA PATHS
# -------------------------------
DATA_FILE = "data/qr_colors.json"

DEFAULT_DATA = {
    "colors": {
        'black': '#000000', 'blue': '#0000FF', 'red': '#FF0000',
        'purple': '#800080', 'green': '#008000', 'orange': '#FFA500',
        'pink': '#FFC0CB', 'gold': '#FFD700', 'cyan': '#00FFFF'
    },
    "gradients": {
        'sunset': ['#FF512F', '#DD2476'],
        'ocean': ['#2193b0', '#6dd5ed'],
        'forest': ['#134E5E', '#71B280'],
        'purple_love': ['#cc2b5e', '#753a88'],
        'fire': ['#f12711', '#f5af19'],
        'sky': ['#00c6ff', '#0072ff'],
        'royal': ['#141E30', '#243B55']
    }
}

# -------------------------------
# 1. DATA MANAGER (Combined JSON with Migration Logic)
# -------------------------------
def load_all_data():
    """পুরো JSON ফাইল লোড করে এবং পুরনো ফরম্যাট থাকলে অটোমেটিক ঠিক করে দেয়।"""
    if not os.path.exists('data'): os.makedirs('data')
    if not os.path.exists(DATA_FILE):
        save_all_data(DEFAULT_DATA)
        return DEFAULT_DATA
    
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        
        # MIGRATION: পুরনো ফাইল ফরম্যাট চেক
        updated = False
        if "colors" not in data:
            old_colors = data if isinstance(data, dict) else DEFAULT_DATA["colors"]
            data = {"colors": old_colors, "gradients": DEFAULT_DATA["gradients"]}
            updated = True
        if "gradients" not in data:
            data["gradients"] = DEFAULT_DATA["gradients"]
            updated = True
        
        if updated: save_all_data(data)
        return data
    except:
        return DEFAULT_DATA

def save_all_data(data):
    """ডাটা JSON ফাইলে সেভ করে।"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# core.py থেকে এই ফাংশনগুলো কল করা হয়
def load_colors():
    return load_all_data().get("colors", {})

def load_gradients():
    return load_all_data().get("gradients", {})

def add_new_color(name, hex_code):
    data = load_all_data()
    data["colors"][name.lower()] = hex_code.upper()
    save_all_data(data)

def add_new_gradient(name, hex1, hex2):
    data = load_all_data()
    data["gradients"][name.lower()] = [hex1.upper(), hex2.upper()]
    save_all_data(data)

# -------------------------------
# 2. HELPER FUNCTIONS
# -------------------------------
def create_linear_gradient(width, height, start_color, end_color):
    """ইমেজের জন্য ডায়াগনাল গ্রেডিয়েন্ট তৈরি করে।"""
    try:
        base = Image.new('RGB', (width, height), start_color)
        top = Image.new('RGB', (width, height), end_color)
        mask = Image.new('L', (width, height))
        mask_data = []
        for y in range(height):
            for x in range(width):
                mask_data.append(int(255 * (y / height + x / width) / 2))
        mask.putdata(mask_data)
        base.paste(top, (0, 0), mask)
        return base
    except:
        return Image.new('RGB', (width, height), "black")

def draw_star_shape(draw, cx, cy, size, fill):
    points = []
    outer_radius, inner_radius = size / 2, size / 4
    angle, step = -math.pi / 2, math.pi / 5
    for _ in range(5):
        points.append((cx + math.cos(angle) * outer_radius, cy + math.sin(angle) * outer_radius))
        angle += step
        points.append((cx + math.cos(angle) * inner_radius, cy + math.sin(angle) * inner_radius))
        angle += step
    draw.polygon(points, fill=fill)

# -------------------------------
# 3. PALETTE GENERATORS
# -------------------------------
def _draw_palette_common(chunk, is_gradient, page_index):
    img_w, row_h, box_s, card_gap = 1200, 250, 160, 20
    img_h = (len(chunk) * row_h) + (card_gap * 2)
    img = Image.new("RGB", (img_w, img_h), "#F0F2F5")
    draw = ImageDraw.Draw(img)
    
    try:
        font_name = ImageFont.truetype("data/fonts/Pacifico-Regular.ttf", 70)
        font_hex = ImageFont.truetype("data/fonts/Pacifico-Regular.ttf", 40)
    except:
        font_name = ImageFont.load_default(); font_hex = ImageFont.load_default()

    for idx, (name, val) in enumerate(chunk):
        y_start = (idx * row_h) + card_gap
        draw.rectangle([30, y_start, img_w-30, y_start+row_h-card_gap], fill="white", outline="#D1D1D1", width=2)
        box_x, box_y = 70, y_start + ((row_h - card_gap - box_s) // 2)
        
        if is_gradient:
            grad_box = create_linear_gradient(box_s, box_s, val[0], val[1])
            img.paste(grad_box, (box_x, box_y))
            hex_text = f"{val[0]} ➔ {val[1]}"
        else:
            try: draw.rectangle([box_x, box_y, box_x+box_s, box_y+box_s], fill=val, outline="black", width=3)
            except: draw.rectangle([box_x, box_y, box_x+box_s, box_y+box_s], fill="black", outline="black", width=3)
            hex_text = val

        draw.text((box_x+box_s+50, y_start+50), name.title(), fill="black", font=font_name)
        draw.text((box_x+box_s+50, y_start+150), hex_text, fill="gray", font=font_hex)

    bio = BytesIO(); img.save(bio, "PNG"); bio.seek(0)
    return bio

def generate_palette_page(page_index):
    colors = load_colors()
    chunk = list(colors.items())[page_index*10 : (page_index+1)*10]
    return _draw_palette_common(chunk, False, page_index) if chunk else None

def generate_gradient_palette_page(page_index):
    grads = load_gradients()
    chunk = list(grads.items())[page_index*10 : (page_index+1)*10]
    return _draw_palette_common(chunk, True, page_index) if chunk else None

# -------------------------------
# 4. QR GENERATOR
def make_qr(url, style='square', color_name='black', logo_data=None, gradient_name=None, bg_color_name='white', bg_image_data=None):
    try:
        colors = load_colors()
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(url); qr.make(fit=True)
        
        matrix = qr.get_matrix(); box_size, border = 20, 4
        img_size = (len(matrix) + (border * 2)) * box_size
        
        # ১. ব্যাকগ্রাউন্ড নির্ধারণ (Image vs Color)
        bg_hex = colors.get(bg_color_name, '#FFFFFF')
        
        if bg_image_data:
            try:
                bg_img = Image.open(BytesIO(bg_image_data)).convert("RGBA")
                # স্কয়ার ক্রপ করা
                w, h = bg_img.size
                min_dim = min(w, h)
                left, top = (w - min_dim)/2, (h - min_dim)/2
                bg_img = bg_img.crop((left, top, left + min_dim, top + min_dim))
                # কিউআর সাইজে রিসাইজ করা
                bg_img = bg_img.resize((img_size, img_size), Image.Resampling.LANCZOS)
                final_img = bg_img
            except:
                final_img = Image.new("RGBA", (img_size, img_size), bg_hex)
        else:
            final_img = Image.new("RGBA", (img_size, img_size), bg_hex)

        # ২. MASK & COLOR Layer (Foreground)
        mask = Image.new("L", (img_size, img_size), 0)
        draw = ImageDraw.Draw(mask); fill_val = 255
        for y in range(len(matrix)):
            for x in range(len(matrix[y])):
                if matrix[y][x]:
                    l, t = (x + border) * box_size, (y + border) * box_size
                    r, b = l + box_size, t + box_size
                    cx, cy = l + (box_size/2), t + (box_size/2)
                    if style == 'round': draw.ellipse((l, t, r, b), fill=fill_val)
                    elif style == 'diamond': draw.polygon([(cx, t), (r, cy), (cx, b), (l, cy)], fill=fill_val)
                    elif style == 'rounded': draw.rounded_rectangle((l, t, r, b), radius=box_size*0.3, fill=fill_val)
                    elif style == 'star': draw_star_shape(draw, cx, cy, box_size, fill_val)
                    else: draw.rectangle((l, t, r, b), fill=fill_val)

        if gradient_name:
            grads = load_gradients()
            c_pair = grads.get(gradient_name, ["#000000", "#000000"])
            color_layer = create_linear_gradient(img_size, img_size, c_pair[0], c_pair[1])
        else:
            color_layer = Image.new("RGB", (img_size, img_size), colors.get(color_name, '#000000'))

        # ৩. মার্জ করা
        final_img.paste(color_layer, (0, 0), mask)
        
        # ৪. লোগো ইন্টিগ্রেশন
        if logo_data:
            try:
                logo = Image.open(BytesIO(logo_data)).convert("RGBA")
                l_s = int(img_size * 0.22)
                logo = logo.resize((l_s, l_s), Image.Resampling.LANCZOS)
                # লোগোর পেছনে একটু প্যাডিং (সাদা বা সলিড কালার দিলে ভালো দেখায়)
                bg_l = Image.new("RGBA", (l_s+10, l_s+10), bg_hex if not bg_image_data else "white")
                bg_l.paste(logo, (5, 5), logo)
                pos = ((img_size - bg_l.width)//2, (img_size - bg_l.height)//2)
                final_img.paste(bg_l, pos, bg_l)
            except: pass

        bio = BytesIO(); final_img.save(bio, "PNG"); bio.seek(0)
        return bio
    except Exception as e:
        print(f"QR Error: {e}"); return None
