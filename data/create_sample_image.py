from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import os

# 读取 CSV
photos = pd.read_csv("asset_photos.csv")
out_dir = "sample_images_placeholder"
os.makedirs(out_dir, exist_ok=True)

# 使用默认字体
font = ImageFont.load_default()

for _, row in photos.iterrows():
    asset_id = row["asset_id"]
    asset_type = row.get("asset_type", "unknown")
    
    # 创建灰色背景
    img = Image.new("L", (640, 360), color=200)
    draw = ImageDraw.Draw(img)
    text = f"{asset_id}\n{asset_type}"
    
    # 计算文字边界框
    bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    
    # 居中绘制文字
    x = (640 - w) / 2
    y = (360 - h) / 2
    draw.multiline_text((x, y), text, font=font, fill=0, align="center")
    
    # 保存
    path = os.path.join(out_dir, f"{asset_id}.png")
    img.save(path)

print("占位图生成完毕，保存在 sample_images_placeholder/")