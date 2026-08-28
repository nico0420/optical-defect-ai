import os
import io
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageStat

# 載入 .env
ENV_FILE = "/Users/nico/ai/.env"
if os.path.exists(ENV_FILE):
    with open(ENV_FILE, "r") as f:
        for line in f:
            if line.strip().startswith("GEMINI_API_KEY="):
                os.environ["GEMINI_API_KEY"] = line.strip().split("=", 1)[1]

SYSTEM_PROMPT = """你是一位專精於光學鏡片製程與 AOI（自動光學檢測）的資深品保工程師。
你的任務是仔細觀察使用者上傳的鏡片照片，進行客觀、真實的多模態視覺瑕疵診斷。

【判定原則】：
1. 若鏡片透亮、無明顯刮痕、氣泡、髒污或崩角，請務必判定為【正常良品 (Pass / Clean)】，severity_level 設為 0，has_defect 設為 false，bounding_boxes 設為空陣列 []。
2. 若觀察到明顯刮痕 (Scratch)、氣泡 (Bubble)、油污 (Stain)、崩角 (Chip) 等缺陷，請判定為瑕疵，並標註缺陷位置座標 bounding_boxes。
3. bounding_boxes 中的 box_2d 座標必須使用 0 到 1000 之間的整數 [ymin, xmin, ymax, xmax]。

請嚴格輸出符合以下 JSON 格式（不要包含任何 markdown 外框）：
{
  "has_defect": true 或 false,
  "defect_type": "正常良品 (Pass / Clean) 或 瑕疵名稱",
  "defect_subtype": "細部分類說明",
  "severity_level": 0 到 5 的整數 (0為良品, 5為致命),
  "severity_label": "正常良品 / 輕微 / 中度 / 嚴重 / 致命",
  "confidence_score": 0.00 到 1.00 之間的浮點數,
  "affected_area_percentage": "0.0% 或 估計受影響面積比例",
  "bounding_boxes": [
    {
      "box_2d": [ymin, xmin, ymax, xmax],
      "label": "瑕疵描述",
      "severity": 1到5的整數
    }
  ],
  "defect_description": "詳述在影像中觀察到的特徵",
  "root_cause_analysis": "產線根因推測或製程穩定說明",
  "machine_action": "正常放行 / 減速觀測 / 停機檢修 / 批次隔離",
  "action_sop": [
    "處置步驟 1",
    "處置步驟 2"
  ]
}
"""

def draw_defect_boxes(image: Image.Image, boxes: list) -> Image.Image:
    """在影像上繪製工控級瑕疵標註框 (Bounding Box) 與半透明高亮光罩"""
    annotated = image.copy().convert("RGBA")
    overlay = Image.new("RGBA", annotated.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    w, h = annotated.size
    
    for i, item in enumerate(boxes):
        box = item.get("box_2d", [])
        if len(box) != 4:
            continue
        ymin, xmin, ymax, xmax = box
        
        top = int((ymin / 1000.0) * h)
        left = int((xmin / 1000.0) * w)
        bottom = int((ymax / 1000.0) * h)
        right = int((xmax / 1000.0) * w)
        
        top, left = max(0, top), max(0, left)
        bottom, right = min(h, bottom), min(w, right)
        
        label = item.get("label", f"Defect #{i+1}")
        severity = item.get("severity", 4)
        
        if severity >= 4:
            color = (239, 68, 68, 255)
            fill_color = (239, 68, 68, 60)
        elif severity >= 2:
            color = (245, 158, 11, 255)
            fill_color = (245, 158, 11, 60)
        else:
            color = (59, 130, 246, 255)
            fill_color = (59, 130, 246, 60)
            
        draw_overlay.rectangle([left, top, right, bottom], fill=fill_color, outline=color, width=3)
        corner_len = min(20, max(8, (right - left) // 4), max(8, (bottom - top) // 4))
        for (cx, cy, dx, dy) in [(left, top, 1, 1), (right, top, -1, 1), (left, bottom, 1, -1), (right, bottom, -1, -1)]:
            draw_overlay.line([(cx, cy), (cx + dx * corner_len, cy)], fill=color, width=4)
            draw_overlay.line([(cx, cy), (cx, cy + dy * corner_len)], fill=color, width=4)
            
        label_text = f"🚨 {label} [Lv.{severity}]"
        text_w = len(label_text) * 11
        text_h = 22
        label_top = max(0, top - text_h - 4)
        draw_overlay.rectangle([left, label_top, left + text_w, label_top + text_h], fill=(15, 23, 42, 230))
        draw_overlay.text((left + 6, label_top + 3), label_text, fill=(255, 255, 255, 255))
        
    return Image.alpha_composite(annotated, overlay).convert("RGB")

def analyze_lens_image(image: Image.Image, machine_id: str = "AOI-01", lens_model: str = "7P-Plastic-Lens", api_key: str = None, sample_hint: str = None) -> tuple:
    """
    分析鏡片照片：調用 Google Gemini 最新多模態視覺模型進行真實推理
    """
    key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    
    if key:
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=key)
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            
            user_prompt = f"""請分析這張機台 [{machine_id}] 拍攝的鏡片影像，型號 [{lens_model}]。請客觀判定是否有任何刮痕、氣泡、油污或裂損。若為正常無瑕疵鏡片，請務必判定為正常良品 (has_defect: false, severity_level: 0)。"""
            
            # 使用支援的最新視覺模型
            for model_name in ['gemini-3.6-flash', 'gemini-3.7-flash', 'gemini-flash-latest']:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[
                            types.Part.from_bytes(data=img_bytes, mime_type='image/png'),
                            SYSTEM_PROMPT + "\n\n" + user_prompt
                        ],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1
                        )
                    )
                    break
                except Exception:
                    continue
            
            result_text = response.text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
                
            data = json.loads(result_text)
            data["_is_mock"] = False
            data["_model_used"] = f"Google Gemini 3.6 Flash (真實 AI 多模態視覺辨識)"
            
            boxes = data.get("bounding_boxes", [])
            has_defect = data.get("has_defect", False)
            annotated_img = draw_defect_boxes(image, boxes) if (boxes and has_defect) else image
            return data, annotated_img
        except Exception as e:
            print(f"[Gemini API 連線失敗，切換離線模式]: {e}")
            res = mock_analyze_image(image, machine_id, lens_model, sample_hint=sample_hint)
            res["_mock_notice"] = f"（API 呼叫失敗，已切換離線模擬：{str(e)[:50]}）"
            boxes = res.get("bounding_boxes", [])
            annotated_img = draw_defect_boxes(image, boxes) if (boxes and res.get("has_defect", False)) else image
            return res, annotated_img
    else:
        res = mock_analyze_image(image, machine_id, lens_model, sample_hint=sample_hint)
        boxes = res.get("bounding_boxes", [])
        annotated_img = draw_defect_boxes(image, boxes) if (boxes and res.get("has_defect", False)) else image
        return res, annotated_img

def mock_analyze_image(image: Image.Image, machine_id: str, lens_model: str, sample_hint: str = None) -> dict:
    """離線展示模擬引擎"""
    hint = (sample_hint or "").lower()
    if "clean" in hint or "良品" in hint:
        return {
            "has_defect": False,
            "defect_type": "正常良品 (Pass / Clean)",
            "defect_subtype": "無明顯瑕疵 (符合 MIL-PRF-13830B 規範)",
            "severity_level": 0,
            "severity_label": "正常良品 (Pass)",
            "confidence_score": 0.99,
            "affected_area_percentage": "0.0%",
            "bounding_boxes": [],
            "defect_description": "鏡片表面與透鏡內部均質透亮，無刮痕、麻點、氣泡、髒污或崩角，光學鍍膜均勻且符合規格。",
            "root_cause_analysis": f"機台 {machine_id} 製程參數穩定，各工序環境符合無塵標準。",
            "machine_action": "正常放行 (Pass & Continue)",
            "action_sop": ["1. 自動放行至包裝站並貼附 PASS 合格標籤。", "2. 品保檢測數據自動上傳 MES 製造執行系統記錄。"],
            "_is_mock": True,
            "_model_used": "離線模擬引擎"
        }
    elif "bubble" in hint or "氣泡" in hint:
        return {
            "has_defect": True,
            "defect_type": "內部氣泡 (Internal Bubble)",
            "defect_subtype": "聚集型微氣泡 / 光學包裹物",
            "severity_level": 3,
            "severity_label": "中度 (光學性能異常)",
            "confidence_score": 0.91,
            "affected_area_percentage": "4.2%",
            "bounding_boxes": [{"box_2d": [380, 520, 520, 640], "label": "內部微氣泡聚集區", "severity": 3}],
            "defect_description": "在鏡片中心軸偏右上方光學有效區（CA）內部檢測到 4 顆微氣泡聚集，造成局部光線折射率發散。",
            "root_cause_analysis": f"機台 {machine_id} 之原料乾燥溫度不足，導致 COP 膠粒在熔融過程殘留微量水氣夾氣。",
            "machine_action": "減速觀測 & 調整成型參數",
            "action_sop": ["1. 檢查射出烘料溫度是否達 110°C。", "2. 微調射出保壓壓力（提升 5%）。", "3. 執行後續 10 模件切片複檢。"],
            "_is_mock": True,
            "_model_used": "離線模擬引擎"
        }
    elif "stain" in hint or "髒污" in hint or "油" in hint:
        return {
            "has_defect": True,
            "defect_type": "表面髒污 / 油漬 (Surface Stain)",
            "defect_subtype": "有機油劑光暈殘留",
            "severity_level": 2,
            "severity_label": "輕微 (可清洗返修)",
            "confidence_score": 0.89,
            "affected_area_percentage": "6.8%",
            "bounding_boxes": [{"box_2d": [480, 320, 680, 550], "label": "有機油漬殘留光暈", "severity": 2}],
            "defect_description": "鏡片左下方觀察到擴散狀半透明黃褐色有機油脂殘留光暈。",
            "root_cause_analysis": f"超音波清洗工位之脫脂清洗劑濃度不足，或機械手臂夾爪潤滑油脂微量滲漏。",
            "machine_action": "批次隔離返洗 (Rework / Re-wash)",
            "action_sop": ["1. 將該料盤鏡片送回超音波多槽清洗線二次精洗。", "2. 檢查傳送機構夾爪排除油脂外漏。"],
            "_is_mock": True,
            "_model_used": "離線模擬引擎"
        }
    elif "chip" in hint or "崩" in hint:
        return {
            "has_defect": True,
            "defect_type": "邊緣崩角 (Edge Chip)",
            "defect_subtype": "外緣應力破裂破損",
            "severity_level": 5,
            "severity_label": "致命 (重大缺陷立即報廢)",
            "confidence_score": 0.98,
            "affected_area_percentage": "14.5%",
            "bounding_boxes": [{"box_2d": [180, 650, 360, 830], "label": "外緣崩角破裂", "severity": 5}],
            "defect_description": "鏡片外緣 45 度定位面發生嚴重缺角碎裂，伴隨微裂紋延伸。",
            "root_cause_analysis": f"頂出銷受力不均導致脫模應力集中，或治具下壓時公差干涉硬碰。",
            "machine_action": "停機檢修 (Emergency Stop & Hold)",
            "action_sop": ["1. 立即暫停組裝工位，啟動紅燈警報。", "2. 本片鏡片直接判定 Scrap 報廢。"],
            "_is_mock": True,
            "_model_used": "離線模擬引擎"
        }
    else:
        # 自傳照片 (根據邊緣做判斷)
        gray = image.convert("L").resize((256, 256))
        stat = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES))
        if stat.mean[0] < 18.0:
            return {
                "has_defect": False,
                "defect_type": "正常良品 (Pass / Clean)",
                "defect_subtype": "表面均勻無明顯瑕疵",
                "severity_level": 0,
                "severity_label": "正常良品 (Pass)",
                "confidence_score": 0.96,
                "affected_area_percentage": "0.0%",
                "bounding_boxes": [],
                "defect_description": "鏡片表面未見顯著刮痕或異物，反射光線均勻。",
                "root_cause_analysis": "製程環境穩定，鏡面品質良好。",
                "machine_action": "正常放行 (Pass & Continue)",
                "action_sop": ["1. 正常放行至下一工站。"],
                "_is_mock": True,
                "_model_used": "離線模擬引擎"
            }
        else:
            return {
                "has_defect": True,
                "defect_type": "表面刮痕 (Surface Scratch)",
                "defect_subtype": "表面磨損刮痕",
                "severity_level": 4,
                "severity_label": "嚴重 (需停機檢修)",
                "confidence_score": 0.92,
                "affected_area_percentage": "8.5%",
                "bounding_boxes": [{"box_2d": [350, 200, 650, 800], "label": "表面刮痕區域", "severity": 4}],
                "defect_description": "鏡片光學通光區域發現連續性刮傷痕跡。",
                "root_cause_analysis": f"機台 {machine_id} 拋光治具夾帶磨料硬粒或吸嘴刮磨。",
                "machine_action": "停機檢修 (Hold & Inspect)",
                "action_sop": ["1. 暫停自動線並隔離當前批次鏡片。", "2. 清理治具並檢驗吸盤。"],
                "_is_mock": True,
                "_model_used": "離線模擬引擎"
            }
