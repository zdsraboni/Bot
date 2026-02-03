import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageColor
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageColor

# =========================================================
# 🛡️ FFmpeg CRASH PROTECTION
# =========================================================
# এই অংশটি এমনভাবে লেখা হয়েছে যাতে FFmpeg না থাকলেও বট রান করে।
VIDEO_SUPPORT = False

try:
    # ১. প্রথমে imageio-ffmpeg ইমপোর্ট করার চেষ্টা
    import imageio_ffmpeg
    
    # ২. FFmpeg ফাইল খোঁজার চেষ্টা (এটিই মূলত ক্র্যাশ করাচ্ছিল)
    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
        print(f"✅ FFmpeg found at: {ffmpeg_path}")
        
        # ৩. সব ঠিক থাকলে ভিডিও লাইব্রেরি লোড করা
        import numpy as np
        from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
        VIDEO_SUPPORT = True
        
    except RuntimeError:
        print("⚠️ Warning: imageio-ffmpeg could not find a binary for this OS.")
        print("ℹ️ Video watermarking will be DISABLED.")
        
except ImportError:
    print("⚠️ Warning: 'imageio-ffmpeg' or 'moviepy' not installed.")
    print("ℹ️ Video watermarking will be DISABLED.")
except Exception as e:
    print(f"⚠️ Video Engine Error: {e}")
    print("ℹ️ Video watermarking will be DISABLED.")


# ==========================================
# 🛠️ HELPER FUNCTIONS (Shared Logic)
# ==========================================

def get_color_rgb(hex_code):
    try: return ImageColor.getrgb(hex_code)
    except: return (255, 255, 255)

def apply_opacity_pil(image, opacity_val):
    if opacity_val == 255: return image
    img = image.convert("RGBA")
    alpha = img.split()[3]
    factor = opacity_val / 255.0
    alpha = ImageEnhance.Brightness(alpha).enhance(factor)
    img.putalpha(alpha)
    return image

def generate_watermark_layer(target_size, s):
    width, height = target_size
    watermark_layer = Image.new("RGBA", (width, height), (0,0,0,0))
    wm_content = None

    # --- 1. GENERATE CONTENT (Logo/Text) ---
    if s["mode"] == "logo" and s["logo_path"] and os.path.exists(s["logo_path"]):
        try:
            wm_content = Image.open(s["logo_path"]).convert("RGBA")
            scale = s.get("logo_scale", 1.0)
            base_w = int(min(width, height) * 0.2 * scale)
            w_ratio = base_w / float(wm_content.size[0])
            h_size = int(float(wm_content.size[1]) * float(w_ratio))
            wm_content = wm_content.resize((base_w, h_size), Image.Resampling.LANCZOS)
            wm_content = apply_opacity_pil(wm_content, s["opacity"])
        except: pass

    elif s["mode"] == "text":
        text = s.get("text", "Watermark")
        font_size = int(min(width, height) * (s.get("size_pct", 5) / 100))
        
        font = None
        if s.get("font_path") and os.path.exists(s["font_path"]):
            try: font = ImageFont.truetype(s["font_path"], font_size)
            except: pass
        if not font: font = ImageFont.load_default()

        draw_temp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = draw_temp.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

        txt_img = Image.new("RGBA", (text_w + 40, text_h + 40), (0,0,0,0))
        txt_draw = ImageDraw.Draw(txt_img)

        if s["bg_enabled"]:
            bg_col = get_color_rgb(s["bg_color"]) + (s["bg_opacity"],)
            txt_draw.rectangle([0, 0, text_w + 20, text_h + 20], fill=bg_col)

        txt_col = get_color_rgb(s["text_color"]) + (s["opacity"],)
        txt_draw.text((10, 10), text, font=font, fill=txt_col)
        wm_content = txt_img

    if not wm_content: return None

    # --- 2. ROTATION ---
    if s["rotation"] != 0:
        wm_content = wm_content.rotate(s["rotation"], expand=True, resample=Image.BICUBIC)

    # --- 3. POSITIONING/TILING ---
    wm_w, wm_h = wm_content.size

    if s["is_tiled"]:
        gap = s.get("tile_gap", 20); mode = s.get("tile_mode", "grid")
        for y in range(0, height, wm_h + gap):
            for x in range(0, width, wm_w + gap):
                if mode == "vertical" and x > 0: continue
                if mode == "horizontal" and y > 0: continue
                watermark_layer.paste(wm_content, (x, y), wm_content)
    else:
        padding = 20; pos = s["position"]
        if pos == "custom": x, y = s.get("pos_x", 0), s.get("pos_y", 0)
        elif pos == "top_left": x, y = padding, padding
        elif pos == "bottom_left": x, y = padding, height - wm_h - padding
        elif pos == "center": x, y = (width - wm_w) // 2, (height - wm_h) // 2
        else: x, y = width - wm_w - padding, height - wm_h - padding
        watermark_layer.paste(wm_content, (x, y), wm_content)
        
    return watermark_layer

# ==========================================
# 🖼️ IMAGE PROCESSOR (Always Active)
# ==========================================
def apply_watermark_image(input_path, output_path, s):
    try:
        img = Image.open(input_path).convert("RGBA")
        wm_layer = generate_watermark_layer(img.size, s)
        if wm_layer:
            final_img = Image.alpha_composite(img, wm_layer).convert("RGB")
            final_img.save(output_path, "JPEG", quality=95)
        else:
            img.convert("RGB").save(output_path, "JPEG")
        return True
    except Exception as e:
        print(f"Image Engine Error: {e}")
        return False

# ==========================================
# 🎬 VIDEO/GIF PROCESSOR (Conditional)
# ==========================================
def apply_watermark_video(input_path, output_path, s, is_gif=False):
    # যদি VIDEO_SUPPORT ফলস হয়, তবে সরাসরি বের হয়ে যাবে (ক্র্যাশ করবে না)
    if not VIDEO_SUPPORT:
        print("❌ Video watermarking is disabled due to missing FFmpeg.")
        return False

    try:
        video_clip = VideoFileClip(input_path)
        wm_pil = generate_watermark_layer(video_clip.size, s)
        
        if wm_pil:
            wm_clip = ImageClip(np.array(wm_pil)).set_duration(video_clip.duration)
            final_clip = CompositeVideoClip([video_clip, wm_clip])
        else:
            final_clip = video_clip

        if is_gif:
            final_clip.write_gif(output_path, fps=10, verbose=False, logger=None)
        else:
            final_clip.write_videofile(
                output_path, 
                codec='libx264', 
                audio_codec='aac', 
                temp_audiofile='temp-audio.m4a', 
                remove_temp=True,
                preset='ultrafast',
                verbose=False, logger=None
            )
            
        video_clip.close()
        return True
    except Exception as e:
        print(f"Video Engine Error: {e}")
        try: video_clip.close()
        except: pass
        return False

# engine.py এর generate_font_preview_image ফাংশনটি এভাবে আপডেট করুন

def generate_font_preview_image(font_dir="data/fonts", font_list=None):
    if not os.path.exists(font_dir): return None
    
    if font_list is None:
        fonts = [f for f in os.listdir(font_dir) if f.endswith(('.ttf', '.otf'))]
    else:
        fonts = [f for f in font_list if f.endswith(('.ttf', '.otf'))]
        
    if not fonts: return None

    width, line_height, padding = 800, 80, 40
    img_height = (len(fonts) * line_height) + (padding * 2)
    img = Image.new("RGB", (width, img_height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = padding

    for font_name in fonts:
        try:
            f_path = os.path.join(font_dir, font_name)
            font = ImageFont.truetype(f_path, 40)
            
            # ফন্টের নাম থেকে এক্সটেনশন বাদ দিয়ে ডিসপ্লে নাম তৈরি
            display_name = font_name.replace('.ttf', '').replace('.otf', '')
            
            # টাইটেল হিসেবে ফন্টের নাম (হালকা রঙে)
            draw.text((20, y), f"{display_name}:", fill=(150, 150, 150))
            
            # 🔥 পরিবর্তন: প্রিভিউ টেক্সট হিসেবে সরাসরি ফন্টের নাম ব্যবহার করা হয়েছে
            draw.text((20, y + 30), display_name, font=font, fill=(0, 0, 0))
            
            y += line_height
        except:
            continue

    bio = BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

