import os
import io
import json
import numpy as np
from PIL import Image, ImageDraw

# 載入 .env (本機)
ENV_FILE = "/Users/nico/ai/.env"
if os.path.exists(ENV_FILE):
    try:
        with open(ENV_FILE, "r") as f:
            for line in f:
                if line.strip().startswith("GEMINI_API_KEY="):
                    os.environ["GEMINI_API_KEY"] = line.strip().split("=", 1)[1]
    except Exception:
        pass

def get_api_key(passed_key=None):
    """優先順序：傳入參數 -> Streamlit Secrets -> 系統環境變數"""
    if passed_key and str(passed_key).strip():
        return str(passed_key).strip()
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()

SYSTEM_PROMPT = """你是一位專精於光學鏡片製程與 AOI（自動光學檢測）的資深品保工程師。
你的任務是精準、客觀地檢驗使用者上傳的照片中的【光學鏡片 (Lens)】。

【重要檢驗邊界】：
1. 鏡框 (Frame)、鼻墊 (Nose pads)、眼鏡腳架、背景環境、正常透光反光【不是瑕疵】！
2. 只有在【鏡片透明本體】上觀察到真正的物理刮傷 (Scratch)、內部微氣泡 (Bubble)、油垢污漬 (Stain) 或破裂 (Crack) 時，才判定為瑕疵。
3. 若鏡片透亮、無嚴重刮痕或裂損，必須判定為【正常良品 (Pass / Clean)】，severity_level 必須設為 0，has_defect 必須為 false，bounding_boxes 為空陣列 []。

【嚴重度評級標準】：
- 0: 正常良品 (無明顯缺陷，正常放行)
- 1~2: 極微輕微疵病 (微小微塵/可擦拭油污，可返洗)
- 3~4: 明顯刮痕/氣泡 (破壞鍍膜或光學成像，需停機或隔離)
- 5: 致命碎裂/破角 (立即報廢)

請嚴格輸出符合以下 JSON 格式（不要包含任何 markdown 外框）：
{
  "has_defect": true 或 false,
  "defect_type": "正常良品 (Pass / Clean) 或 瑕疵名稱（如：表面刮痕）",
  "defect_subtype": "細部特徵描述",
  "severity_level": 0 到 5 的整數,
  "severity_label": "正常良品 / 輕微 / 中度 / 嚴重 / 致命",
  "confidence_score": 0.00 到 1.00 之間的浮點數,
  "affected_area_percentage": "0.0% 或 受影響比例",
  "bounding_boxes": [
    {
      "box_2d": [ymin, xmin, ymax, xmax],
      "label": "Defect Area (刮痕區域)",
      "severity": 1到5的整數
    }
  ],
  "defect_description": "詳述在影像中觀察到的特徵",
  "root_cause_analysis": "產線根因推測或鏡面品質狀態說明",
  "machine_action": "正常放行 / 減速觀測 / 停機檢修 / 批次隔離",
  "action_sop": [
    "處置步驟 1",
    "處置步驟 2"
  ]
}
"""

def draw_defect_boxes(image: Image.Image, boxes: list) -> Image.Image:
    """在影像上繪製工控 HUD 瑕疵標註框 (跨平台字型相容)"""
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
            
        # 半透明框
        draw_overlay.rectangle([left, top, right, bottom], fill=fill_color, outline=color, width=3)
        corner_len = min(20, max(8, (right - left) // 4), max(8, (bottom - top) // 4))
        for (cx, cy, dx, dy) in [(left, top, 1, 1), (right, top, -1, 1), (left, bottom, 1, -1), (right, bottom, -1, -1)]:
            draw_overlay.line([(cx, cy), (cx + dx * corner_len, cy)], fill=color, width=4)
            draw_overlay.line([(cx, cy), (cx, cy + dy * corner_len)], fill=color, width=4)
            
        # 標籤 (使用英文通用字元防止 Linux 缺字)
        label_text = f"DEFECT #{i+1} [Lv.{severity}]"
        text_w = len(label_text) * 9
        text_h = 18
        label_top = max(0, top - text_h - 4)
        draw_overlay.rectangle([left, label_top, left + text_w, label_top + text_h], fill=(15, 23, 42, 230))
        draw_overlay.text((left + 4, label_top + 2), label_text, fill=(255, 255, 255, 255))
        
    return Image.alpha_composite(annotated, overlay).convert("RGB")

def analyze_lens_image(image: Image.Image, machine_id: str = "AOI-01", lens_model: str = "7P-Plastic-Lens", api_key: str = None, sample_hint: str = None) -> tuple:
    """
    分析鏡片照片：調用 Google Gemini 最新多模態視覺模型進行真實推理
    """
    key = get_api_key(api_key)
    
    if key:
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=key)
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            
            user_prompt = f"""請詳細檢驗這張鏡片/眼鏡照片。請特別注意：鏡框與背景不是瑕疵，只有鏡片本體上的刮痕、氣泡或破損才算瑕疵。若鏡片透亮無損，請務必判定為正常良品 (has_defect: false, severity_level: 0)。"""
            
            response = None
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
                    if response and response.text:
                        break
                except Exception:
                    continue
            
            if not response or not response.text:
                raise RuntimeError("All Gemini models failed to return response.")
                
            result_text = response.text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
                
            data = json.loads(result_text)
            
            # 防呆後處理：良品強制校正
            if not data.get("has_defect", False) or "良品" in data.get("defect_type", "") or "Pass" in data.get("defect_type", ""):
                data["has_defect"] = False
                data["defect_type"] = "正常良品 (Pass / Clean)"
                data["severity_level"] = 0
                data["severity_label"] = "正常良品 (Pass)"
                data["bounding_boxes"] = []
                data["machine_action"] = "正常放行 (Pass & Continue)"
                
            data["_is_mock"] = False
            data["_model_used"] = "Google Gemini 3.6 Flash (真實 AI 多模態視覺辨識)"
            
            boxes = data.get("bounding_boxes", [])
            has_defect = data.get("has_defect", False)
            annotated_img = draw_defect_boxes(image, boxes) if (boxes and has_defect) else image
            return data, annotated_img
        except Exception as e:
            print(f"[Gemini API 連線失敗，切換離線模式]: {e}")
            res = mock_analyze_image(image, machine_id, lens_model, sample_hint=sample_hint)
            res["_mock_notice"] = f"（API 呼叫失敗：{str(e)[:50]}）"
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
    if "bubble" in hint or "氣泡" in hint:
        return {
            "has_defect": True,
            "defect_type": "內部氣泡 (Internal Bubble)",
            "defect_subtype": "聚集型微氣泡 / 光學包裹物",
            "severity_level": 3,
            "severity_label": "中度 (光學性能異常)",
            "confidence_score": 0.91,
            "affected_area_percentage": "4.2%",
            "bounding_boxes": [{"box_2d": [380, 520, 520, 640], "label": "Micro-bubble cluster", "severity": 3}],
            "defect_description": "在鏡片光學有效區內部檢測到微氣泡聚集。",
            "root_cause_analysis": f"射出成型機台 {machine_id} 原料乾燥不足夾氣。",
            "machine_action": "減速觀測 & 調整成型參數",
            "action_sop": ["1. 檢查烘料溫度。", "2. 微調射出保壓壓力。"],
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
            "bounding_boxes": [{"box_2d": [480, 320, 680, 550], "label": "Oil stain smudge", "severity": 2}],
            "defect_description": "鏡片表面觀察到有機油脂殘留光暈。",
            "root_cause_analysis": "清洗槽脫脂劑老化或機械夾爪潤滑油外漏。",
            "machine_action": "批次隔離返洗 (Rework / Re-wash)",
            "action_sop": ["1. 送回超音波清洗線二次精洗。", "2. 檢查夾爪防護套。"],
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
            "bounding_boxes": [{"box_2d": [180, 650, 360, 830], "label": "Edge crack chip", "severity": 5}],
            "defect_description": "鏡片外緣發生缺角碎裂，伴隨裂紋延伸。",
            "root_cause_analysis": "頂出銷受力不均或治具下壓公差干涉。",
            "machine_action": "停機檢修 (Emergency Stop & Hold)",
            "action_sop": ["1. 暫停組裝線並啟動紅燈警報。", "2. 本片直接判定報廢。"],
            "_is_mock": True,
            "_model_used": "離線模擬引擎"
        }
    elif "scratch" in hint:
        return {
            "has_defect": True,
            "defect_type": "表面刮痕 (Surface Scratch)",
            "defect_subtype": "通光區域磨損刮傷",
            "severity_level": 4,
            "severity_label": "嚴重 (需停機檢修)",
            "confidence_score": 0.94,
            "affected_area_percentage": "8.5%",
            "bounding_boxes": [{"box_2d": [380, 320, 600, 680], "label": "Surface scratch", "severity": 4}],
            "defect_description": "鏡片光學通光區域發現連續性刮傷痕跡。",
            "root_cause_analysis": f"機台 {machine_id} 拋光治具夾帶磨料硬粒。",
            "machine_action": "停機檢修 (Hold & Inspect)",
            "action_sop": ["1. 暫停生產並隔離批次。", "2. 清理治具更換拋光皮。"],
            "_is_mock": True,
            "_model_used": "離線模擬引擎"
        }
    else:
        # 預設正常良品
        return {
            "has_defect": False,
            "defect_type": "正常良品 (Pass / Clean)",
            "defect_subtype": "無明顯瑕疵 (符合標準)",
            "severity_level": 0,
            "severity_label": "正常良品 (Pass)",
            "confidence_score": 0.99,
            "affected_area_percentage": "0.0%",
            "bounding_boxes": [],
            "defect_description": "鏡片表面與透鏡內部均質透亮，無刮痕、氣泡、髒污或崩角，光學鍍膜均勻。",
            "root_cause_analysis": f"機台 {machine_id} 製程穩定，環境符合無塵標準。",
            "machine_action": "正常放行 (Pass & Continue)",
            "action_sop": ["1. 自動放行至包裝站貼附 PASS 標籤。"],
            "_is_mock": True,
            "_model_used": "離線模擬引擎 (良品)"
        }
