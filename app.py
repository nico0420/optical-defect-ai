import os
import json
import time
from PIL import Image
import streamlit as st
from detector import analyze_lens_image, draw_defect_boxes

# 頁面配置
st.set_page_config(
    page_title="光學鏡片瑕疵多模態診斷助手 | Optical Defect AI",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 取得預設金鑰 (支援 Streamlit Cloud Secrets 與本機環境變數)
def get_default_api_key():
    try:
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()

# 自訂 CSS 樣式
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-box {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 14px;
        text-align: center;
    }
    .metric-value {
        font-size: 1.4rem;
        font-weight: bold;
        color: #0F172A;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
        margin-top: 4px;
    }
    .sop-item {
        background: #F1F5F9;
        border-left: 4px solid #3B82F6;
        padding: 10px 14px;
        border-radius: 4px;
        margin-bottom: 8px;
        font-size: 0.95rem;
    }
    .api-badge {
        background-color: #ECFDF5;
        border: 1px solid #10B981;
        color: #047857;
        padding: 6px 12px;
        border-radius: 8px;
        font-size: 0.88rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# 側邊欄設定 (專案作品集展示與技術規格)
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/microscope.png", width=64)
    st.markdown("## 🔬 Optical Defect AI")
    st.caption("光學鏡片多模態 AOI 智慧診斷與標註系統")
    
    # 金鑰自動靜默載入 (不直接曝露在畫面上)
    default_key = get_default_api_key()
    
    # 系統連線狀態徽章
    if default_key:
        st.markdown('''
        <div style="background-color: #ECFDF5; border: 1px solid #10B981; color: #047857; padding: 8px 12px; border-radius: 8px; font-size: 0.88rem; font-weight: 600; margin-bottom: 0.8rem;">
            🟢 <b>Gemini 3.6 Flash 多模態引擎連線中</b><br>
            <span style="font-size: 0.76rem; color: #065F46; font-weight: normal;">• 即時雲端視覺推理 & 空間定位</span>
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown('''
        <div style="background-color: #FEF3C7; border: 1px solid #F59E0B; color: #92400E; padding: 8px 12px; border-radius: 8px; font-size: 0.88rem; font-weight: 600; margin-bottom: 0.8rem;">
            🟡 <b>離線智慧模擬引擎 (Demo Mode)</b><br>
            <span style="font-size: 0.76rem; color: #78350F; font-weight: normal;">• 雙模式容錯展示，無須連網</span>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown("---")
    
    # 作品技術亮點 (面試展示超加分)
    st.markdown("### 🌟 核心技術亮點")
    st.markdown("""
    - 🧠 **Multimodal Vision**：大模型光學特徵與根因推理
    - 📐 **Spatial Grounding**：2D Bounding Box 座標輸出
    - 🎨 **HUD Overlay**：Pillow RGBA 標註與警示框渲染
    - 📊 **Structured JSON**：工業級輸出，無縫對接 MES/ERP
    - 🛡️ **Fail-Safe 架構**：API 斷網自動切換離線模擬
    """)
    
    st.markdown("---")
    
    # 支援缺陷清單
    st.markdown("### 🎯 支援檢測瑕疵類型")
    st.markdown("""
    - 🔴 **表面刮痕 (Scratch)**：通光區磨損
    - 🟠 **內部氣泡 (Bubble)**：射出夾氣缺陷
    - 🟡 **表面油污 (Stain)**：有機油脂光暈
    - 🟣 **邊緣崩角 (Chip)**：脫模應力碎裂
    - 🟢 **正常良品 (Pass)**：零瑕疵自動放行
    """)
    
    st.markdown("---")
    
    # 產線與進階設定 (收合面板，不干擾主畫面)
    with st.expander("🏭 產線規格與參數 (選填)", expanded=False):
        machine_id = st.selectbox(
            "AOI 機台編號",
            ["AOI-LENS-01 (研磨線)", "AOI-LENS-02 (射出成型)", "AOI-LENS-03 (鍍膜線)", "AOI-ASSY-05 (組裝線)"],
            index=0
        )
        lens_model = st.selectbox(
            "鏡片規格",
            ["7P Mobile 主鏡頭鏡片 (COP 塑膠)", "8P 潛望式長焦光學鏡片", "AR/VR Pancake 摺疊光路鏡片", "車載 LiDAR 高透鏡片"],
            index=0
        )
        lot_id = st.text_input("批次代碼 (LOT ID)", "LOT-2026-A883")
    
    # 金鑰設定 (收合面板，隱密保護)
    with st.expander("🔐 自訂 API 金鑰 (選填)", expanded=False):
        custom_key = st.text_input(
            "手動覆蓋金鑰",
            value="",
            type="password",
            help="留空將自動讀取系統環境變數或 Secrets"
        )
        api_key = custom_key.strip() if custom_key.strip() else default_key

# 主頁面標題
st.markdown('<div class="main-title">🔬 光學鏡片瑕疵多模態分析與診斷助手</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">基於 Google Gemini 多模態視覺技術 (Multimodal Vision) 打造之智慧光學產線 AOI 瑕疵快速判定、<b>視覺位置標註 (Bounding Box)</b> 與 SOP 處置系統</div>', unsafe_allow_html=True)

# 初始化 Session State
if "active_img" not in st.session_state:
    default_sample = "samples/clean.png"
    if os.path.exists(default_sample):
        st.session_state["active_img"] = Image.open(default_sample)
        st.session_state["sample_tag"] = "clean"
        st.session_state["img_id"] = "preset_clean"

# 影像來源選擇
tab_upload, tab_presets = st.tabs(["📂 上傳鏡片照片 / 拍照檢測", "🌟 點選內建預設測試樣本庫 (One-Click Demo)"])

with tab_upload:
    col_up1, col_up2 = st.columns([1, 1])
    with col_up1:
        uploaded_file = st.file_uploader("選擇鏡片檢測相片 (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"], key="lens_uploader")
        if uploaded_file is not None:
            current_upload_id = f"upload_{uploaded_file.name}_{uploaded_file.size}"
            if st.session_state.get("last_upload_id") != current_upload_id:
                st.session_state["last_upload_id"] = current_upload_id
                st.session_state["active_img"] = Image.open(uploaded_file)
                st.session_state["sample_tag"] = "custom_upload"
                st.session_state["img_id"] = current_upload_id
                st.session_state.pop("last_report", None)
                st.session_state.pop("annotated_img", None)
                st.rerun()

    with col_up2:
        camera_photo = st.camera_input("或使用鏡頭拍照", key="lens_camera")
        if camera_photo is not None:
            current_cam_id = f"cam_{camera_photo.size}_{camera_photo.name}"
            if st.session_state.get("last_cam_id") != current_cam_id:
                st.session_state["last_cam_id"] = current_cam_id
                st.session_state["active_img"] = Image.open(camera_photo)
                st.session_state["sample_tag"] = "camera_capture"
                st.session_state["img_id"] = current_cam_id
                st.session_state.pop("last_report", None)
                st.session_state.pop("annotated_img", None)
                st.rerun()

with tab_presets:
    st.markdown("##### 點選以下光學鏡片常見瑕疵樣本進行即時測試：")
    p_cols = st.columns(5)
    
    presets = [
        ("正常良品", "samples/clean.png", "clean", "無明顯缺陷標準件"),
        ("表面刮痕", "samples/scratch.png", "scratch", "表面研磨磨損刮痕"),
        ("內部氣泡", "samples/bubble.png", "bubble", "COP膠粒夾氣微氣泡"),
        ("表面油污", "samples/stain.png", "stain", "治具油脂光暈殘留"),
        ("邊緣崩角", "samples/chip.png", "chip", "脫模應力外緣破裂")
    ]
    
    for idx, (p_name, p_path, p_hint, p_desc) in enumerate(presets):
        with p_cols[idx]:
            if os.path.exists(p_path):
                thumb = Image.open(p_path)
                st.image(thumb, use_container_width=True)
            
            is_current = (st.session_state.get("sample_tag") == p_hint)
            btn_label = f"✅ {p_name}" if is_current else f"👉 {p_name}"
            if st.button(btn_label, key=f"btn_{p_hint}", use_container_width=True):
                st.session_state["active_img"] = Image.open(p_path)
                st.session_state["sample_tag"] = p_hint
                st.session_state["img_id"] = f"preset_{p_hint}"
                # 清除舊報告，讓切換樣本時即時自動觸發全新分析
                st.session_state.pop("last_report", None)
                st.session_state.pop("annotated_img", None)
                st.rerun()

selected_image = st.session_state.get("active_img")
sample_tag = st.session_state.get("sample_tag", "clean")

st.markdown("---")

# 影像顯示與診斷區
if selected_image is not None:
    col_img, col_diag = st.columns([1.1, 1.2])
    
    with col_img:
        st.markdown("#### 📸 光學檢測影像與瑕疵標註")
        run_btn = st.button("⚡ 重新啟動多模態 AI 瑕疵診斷", type="primary", use_container_width=True)
        
        need_analysis = run_btn or ("last_report" not in st.session_state)
        
        if need_analysis:
            with st.spinner("🤖 正在進行多模態視覺特徵辨識與座標標註..."):
                time.sleep(0.3)
                raw_res = analyze_lens_image(
                    selected_image,
                    machine_id=machine_id,
                    lens_model=lens_model,
                    api_key=api_key,
                    sample_hint=sample_tag
                )
                
                if isinstance(raw_res, tuple) or isinstance(raw_res, list):
                    report = raw_res[0]
                    annotated_img = raw_res[1]
                else:
                    report = raw_res
                    boxes = report.get("bounding_boxes", [])
                    annotated_img = draw_defect_boxes(selected_image, boxes) if (boxes and report.get("has_defect", False)) else selected_image
                    
                st.session_state["last_report"] = report
                st.session_state["annotated_img"] = annotated_img
        else:
            report = st.session_state["last_report"]
            annotated_img = st.session_state.get("annotated_img", selected_image)
            
        img_tab1, img_tab2 = st.tabs(["🎯 AI 瑕疵位置標註圖 (HUD Overlay)", "📷 原始檢測照片"])
        with img_tab1:
            st.image(annotated_img, caption="AI 自動偵測並框選之瑕疵標註圖", use_container_width=True)
        with img_tab2:
            st.image(selected_image, caption="原始相片", use_container_width=True)
    
    with col_diag:
        st.markdown("#### 📊 智能診斷分析報告")
        
        has_defect = report.get("has_defect", False)
        severity = report.get("severity_level", 0)
        
        if not has_defect or severity == 0:
            st.success(f"🟢 **【檢驗合格 (PASS)】** 鏡片品質符合標準，無明顯不良。")
        elif severity <= 2:
            st.warning(f"🟡 **【輕微瑕疵 (WARNING)】** {report.get('defect_type')} - 可隔離返修或微調參數。")
        else:
            st.error(f"🔴 **【嚴重不良 (CRITICAL DEFECT)】** {report.get('defect_type')} - 建議立即停機處置！")
        
        # 指標卡片
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f'<div class="metric-box"><div class="metric-value">{report.get("defect_type", "未知")}</div><div class="metric-label">瑕疵分類</div></div>', unsafe_allow_html=True)
        with m2:
            sev_color = "🔴" if severity >= 4 else ("🟡" if severity >= 2 else "🟢")
            st.markdown(f'<div class="metric-box"><div class="metric-value">{sev_color} Lv.{severity}</div><div class="metric-label">嚴重度 ({report.get("severity_label", "")})</div></div>', unsafe_allow_html=True)
        with m3:
            conf = report.get("confidence_score", 0.95) * 100
            st.markdown(f'<div class="metric-box"><div class="metric-value">{conf:.1f}%</div><div class="metric-label">模型信心指數</div></div>', unsafe_allow_html=True)
        with m4:
            st.markdown(f'<div class="metric-box"><div class="metric-value">{report.get("machine_action", "待定")}</div><div class="metric-label">機台即時指令</div></div>', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 分頁細節
        tab1, tab2, tab3, tab4 = st.tabs(["📝 缺陷特徵與根因", "🎯 瑕疵座標標註清單", "🛠️ 產線標準 SOP", "📄 結構化 JSON 匯出"])
        
        with tab1:
            st.markdown(f"**🔍 瑕疵細部子分類**：`{report.get('defect_subtype', '無')}` （受影響光學面積：`{report.get('affected_area_percentage', '0%')}`）")
            st.markdown("##### 📌 外觀特徵描述")
            st.write(report.get("defect_description", "無詳細描述"))
            st.markdown("##### 🔬 產線最可能根因 (Root Cause)")
            st.write(report.get("root_cause_analysis", "無異常"))
            
        with tab2:
            boxes = report.get("bounding_boxes", [])
            if boxes and has_defect:
                st.markdown(f"共偵測到 **{len(boxes)} 處** 瑕疵區域：")
                for idx, b in enumerate(boxes, 1):
                    coords = b.get("box_2d", [])
                    st.markdown(f"- 🔴 **區域 #{idx}**：`{b.get('label', '瑕疵')}` ｜ 嚴重度：`Lv.{b.get('severity', 4)}` ｜ 座標範圍 [ymin, xmin, ymax, xmax]: `{coords}`")
            else:
                st.info("✅ 未偵測到異常標註區域（判定為良品）")
                
        with tab3:
            st.markdown("##### 📋 現場作業員 / 設備工程師處置步驟：")
            sops = report.get("action_sop", [])
            for item in sops:
                st.markdown(f'<div class="sop-item">📌 {item}</div>', unsafe_allow_html=True)
                
        with tab4:
            st.markdown("##### 📦 系統輸出標準 JSON Schema (可用於對接 MES / ERP 系統)")
            st.json(report)
            
            report_str = json.dumps(report, ensure_ascii=False, indent=2)
            st.download_button(
                label="💾 下載 JSON 品保檢驗報告",
                data=report_str,
                file_name=f"AOI_Report_{lot_id}.json",
                mime="application/json"
            )
            
        st.caption(f"✨ 運算引擎：{report.get('_model_used', 'Google Gemini 3.6 Flash')}")
else:
    st.info("👆 請從上方選擇上傳一張鏡片照片，或直接點選「預設測試樣本庫」中任一瑕疵樣本開始體驗！")
