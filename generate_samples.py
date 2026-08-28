import os
import math
from PIL import Image, ImageDraw, ImageFilter

os.makedirs("/Users/nico/ai/samples", exist_ok=True)

def create_base_lens(size=512, with_highlight_arc=False):
    """建立基礎光學鏡片背景 (工控深色檢測台 + 透明圓形凸透鏡)"""
    img = Image.new("RGB", (size, size), color=(25, 28, 35))
    draw = ImageDraw.Draw(img)
    
    # 畫同心圓檢測格線
    center = size // 2
    for r in range(40, size // 2, 40):
        draw.ellipse([center - r, center - r, center + r, center + r], outline=(38, 42, 52), width=1)
    draw.line([0, center, size, center], fill=(38, 42, 52), width=1)
    draw.line([center, 0, center, size], fill=(38, 42, 52), width=1)
    
    # 鏡片本體
    lens_r = 180
    lens_box = [center - lens_r, center - lens_r, center + lens_r, center + lens_r]
    
    draw.ellipse([center - lens_r - 4, center - lens_r - 4, center + lens_r + 4, center + lens_r + 4], outline=(70, 85, 110), width=3)
    draw.ellipse(lens_box, fill=(40, 50, 65), outline=(130, 160, 200), width=2)
    
    if with_highlight_arc:
        highlight_box = [center - 130, center - 130, center + 90, center + 90]
        draw.arc(highlight_box, start=180, end=290, fill=(100, 180, 240), width=5)
        
    return img, center, lens_r

def generate_scratch():
    img, center, lens_r = create_base_lens(with_highlight_arc=True)
    draw = ImageDraw.Draw(img)
    draw.line([center - 60, center - 40, center + 40, center + 20], fill=(240, 245, 255), width=3)
    draw.line([center - 40, center - 60, center + 70, center - 10], fill=(220, 235, 255), width=2)
    img.save("/Users/nico/ai/samples/scratch.png")

def generate_bubble():
    img, center, lens_r = create_base_lens()
    draw = ImageDraw.Draw(img)
    bubbles = [(center + 30, center - 40, 8), (center + 45, center - 30, 5), (center + 20, center - 50, 4)]
    for x, y, r in bubbles:
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(20, 25, 35), outline=(220, 240, 255), width=2)
        draw.point((x - 1, y - 1), fill=(255, 255, 255))
    img.save("/Users/nico/ai/samples/bubble.png")

def generate_stain():
    img, center, lens_r = create_base_lens()
    draw = ImageDraw.Draw(img)
    stain_x, stain_y = center - 50, center + 40
    for r in range(35, 5, -5):
        draw.ellipse([stain_x - r, stain_y - r*0.7, stain_x + r, stain_y + r*0.7], fill=(90, 75, 45), outline=(130, 110, 60))
    img = img.filter(ImageFilter.GaussianBlur(radius=1.5))
    img.save("/Users/nico/ai/samples/stain.png")

def generate_chip():
    img, center, lens_r = create_base_lens()
    draw = ImageDraw.Draw(img)
    chip_x = center + int(lens_r * math.cos(math.radians(45)))
    chip_y = center - int(lens_r * math.sin(math.radians(45)))
    draw.polygon([(chip_x - 15, chip_y - 15), (chip_x + 20, chip_y + 10), (chip_x - 5, chip_y + 25), (chip_x - 20, chip_y + 5)], fill=(15, 18, 22), outline=(255, 200, 180))
    img.save("/Users/nico/ai/samples/chip.png")

def generate_clean():
    # 完美純淨透亮鏡片
    img, center, lens_r = create_base_lens(with_highlight_arc=False)
    img.save("/Users/nico/ai/samples/clean.png")

if __name__ == "__main__":
    generate_scratch()
    generate_bubble()
    generate_stain()
    generate_chip()
    generate_clean()
    print("✅ 樣本圖檔已重新生成！")
