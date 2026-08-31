import os
import json
import time
from PIL import Image
import streamlit as st
from detector import analyze_lens_image, draw_defect_boxes

# 頁面配置 (寬螢幕、高階工控標題)
st.set_page_config(
    page_title="光學鏡片瑕疵多模態診斷系統 | Optical Defect AI",
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

# 注入高階工控質感 CSS 樣式
st.markdown("""
<style>
    /* 全域字體與背景優化 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    
    /* 指標卡片美化 */
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 12px;
        text-align: center;
        transition: all 0.2s ease-in-out;
    }
    .metric-card:hover {
        border-color: #3B82F6;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.08);
    }
    .metric-val {
        font-size: 1.35rem;
        font-weight: 800;
        color: #0F172A;
        line-height: 1.3;
    }
    .metric-lbl {
        font-size: 0.82rem;
        color: #64748B;
        font-weight: 500;
        margin-top: 6px;
    }
    
    /* SOP 步驟美化 */
    .sop-box {
        background: #F8FAFC;
        border-left: 4px solid #3B82F6;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
        font-size: 0.95rem;
        color: #1E293B;
        border-top: 1px solid #F1F5F9;
        border-right: 1px solid #F1F5F9;
        border-bottom: 1px solid #F1F5F9;
    }
</style>
""", unsafe_allow_html=True)

# 側邊欄設定 (專案作品集展示與技術規格)
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/microscope.png", width=64)
    st.markdown("### 🔬 Optical Defect AI")
    st.caption("光學鏡片多模態 AOI 智慧診斷與標註系統")
    
    default_key = get_default_api_key()
    
    # 系統連線狀態徽章
    if default_key:
        st.markdown('''
        <div style="background-color: #ECFDF5; border: 1px solid #10B981; color: #047857; padding: 8px 12px; border-radius: 8px; font-size: 0.86rem; font-weight: 600; margin-bottom: 0.8rem;">
            🟢 <b>Gemini 3.6 Flash 引擎已連線</b><br>
            <span style="font-size: 0.75rem; color: #065F46; font-weight: normal;">• 即時多模態視覺推理 & 空間定位</span>
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown('''
        <div style="background-color: #FEF3C7; border: 1px solid #F59E0B; color: #92400E; padding: 8px 12px; border-radius: 8px; font-size: 0.86rem; font-weight: 600; margin-bottom: 0.8rem;">
            🟡 <b>離線智慧模擬引擎 (Demo Mode)</b><br>
            <span style="font-size: 0.75rem; color: #78350F; font-weight: normal;">• 雙模式容錯展示，無須連網</span>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown("---")
    
    st.markdown("---")
    
    # 支援缺陷清單
    st.markdown("#### 🎯 支援檢測瑕疵類型")
    st.markdown("""
    - 🔴 **表面刮痕 (Scratch)**：通光區磨損
    - 🟠 **內部氣泡 (Bubble)**：射出夾氣缺陷
    - 🟡 **表面油污 (Stain)**：有機油脂光暈
    - 🟣 **邊緣崩角 (Chip)**：脫模應力碎裂
    - 🟢 **正常良品 (Pass)**：零瑕疵自動放行
    """)
    
    st.markdown("---")
    
    # 產線與進階設定
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
    
    # 金鑰設定
    with st.expander("🔐 自訂 API 金鑰 (選填)", expanded=False):
        custom_key = st.text_input(
            "手動覆蓋金鑰",
            value="",
            type="password",
            help="留空將自動讀取系統環境變數或 Secrets"
        )
        api_key = custom_key.strip() if custom_key.strip() else default_key

# 頂部精緻 Header 卡片
st.markdown("""
<div style="background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); padding: 22px 28px; border-radius: 16px; margin-bottom: 20px; border: 1px solid #334155; box-shadow: 0 4px 20px rgba(0,0,0,0.06);">
    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
        <div>
            <div style="font-size: 1.75rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.5px; display: flex; align-items: center; gap: 10px;">
                🔬 光學鏡片瑕疵多模態視覺診斷系統
            </div>
            <div style="font-size: 0.92rem; color: #94A3B8; margin-top: 6px;">
                基於 Google Gemini 多模態視覺技術 (Multimodal Vision) • 智慧 AOI 瑕疵快速判定、<b>2D 空間座標鎖定 (Bounding Box)</b> 與產線處置 SOP 生成
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# 影像來源選擇模式 (使用 modern segmented_control)
source_mode = st.segmented_control(
    "選擇影像來源",
    options=["📂 上傳鏡片相片檢測", "🌟 點選內建預設測試樣本庫 (One-Click Demo)"],
    default="📂 上傳鏡片相片檢測",
    label_visibility="collapsed"
)

if source_mode == "📂 上傳鏡片相片檢測":
    col_up, col_cam = st.columns([1.2, 0.8])
    with col_up:
        uploaded_file = st.file_uploader("選擇鏡片檢測相片 (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"], key="lens_uploader")
        if uploaded_file is not None:
            current_upload_id = f"upload_{uploaded_file.name}_{uploaded_file.size}"
            if st.session_state.get("img_id") != current_upload_id:
                st.session_state["active_img"] = Image.open(uploaded_file)
                st.session_state["sample_tag"] = "custom_upload"
                st.session_state["img_id"] = current_upload_id
                st.session_state.pop("last_report", None)
                st.session_state.pop("annotated_img", None)
                st.rerun()
        else:
            if st.session_state.get("img_id", "").startswith("upload_"):
                st.session_state.pop("active_img", None)
                st.session_state.pop("sample_tag", None)
                st.session_state.pop("img_id", None)
                st.session_state.pop("last_report", None)
                st.session_state.pop("annotated_img", None)
                st.rerun()

    with col_cam:
        with st.expander("📷 開啟鏡頭拍照檢測 (Webcam Capture)", expanded=False):
            camera_photo = st.camera_input("拍照以進行檢驗", key="lens_camera")
            if camera_photo is not None:
                current_cam_id = f"cam_{camera_photo.size}_{camera_photo.name}"
                if st.session_state.get("img_id") != current_cam_id:
                    st.session_state["active_img"] = Image.open(camera_photo)
                    st.session_state["sample_tag"] = "camera_capture"
                    st.session_state["img_id"] = current_cam_id
                    st.session_state.pop("last_report", None)
                    st.session_state.pop("annotated_img", None)
                    st.rerun()

else:
    # 預設樣本庫模式
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
            with st.container(border=True):
                if os.path.exists(p_path):
                    thumb = Image.open(p_path)
                    st.image(thumb)
                
                is_current = (st.session_state.get("sample_tag") == p_hint and st.session_state.get("img_id", "").startswith("preset_"))
                btn_label = f"✅ {p_name}" if is_current else f"👉 測試 {p_name}"
                btn_type = "primary" if is_current else "secondary"
                if st.button(btn_label, key=f"btn_{p_hint}", type=btn_type):
                    st.session_state["active_img"] = Image.open(p_path)
                    st.session_state["sample_tag"] = p_hint
                    st.session_state["img_id"] = f"preset_{p_hint}"
                    st.session_state.pop("last_report", None)
                    st.session_state.pop("annotated_img", None)
                    st.rerun()

selected_image = st.session_state.get("active_img")
sample_tag = st.session_state.get("sample_tag", "custom_upload")

st.markdown("---")

# 影像顯示與診斷區
if selected_image is not None:
    col_img, col_diag = st.columns([1.15, 1.25])
    
    with col_img:
        with st.container(border=True):
            st.markdown("#### 📸 光學檢測影像與瑕疵標註")
            run_btn = st.button("⚡ 重新啟動多模態 AI 瑕疵診斷", type="primary")
            
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
                
            img_tab1, img_tab2 = st.tabs(["🎯 AI 瑕疵標註圖 (HUD Overlay)", "📷 原始檢測照片"])
            with img_tab1:
                st.image(annotated_img, caption="AI 自動偵測並框選之瑕疵標註圖")
            with img_tab2:
                st.image(selected_image, caption="原始相片")
    
    with col_diag:
        with st.container(border=True):
            st.markdown("#### 📊 智能診斷分析報告")
            
            has_defect = report.get("has_defect", False)
            severity = report.get("severity_level", 0)
            
            if not has_defect or severity == 0:
                st.success("🟢 **【檢驗合格 (PASS)】** 鏡片品質符合 ISO 10110 標準，無明顯不良，正常放行。")
            elif severity <= 2:
                st.warning(f"🟡 **【輕微瑕疵 (WARNING - Lv.{severity})】** {report.get('defect_type')} - 建議隔離返洗或微調參數。")
            else:
                st.error(f"🔴 **【嚴重不良 (CRITICAL DEFECT - Lv.{severity})】** {report.get('defect_type')} - 破壞光學成像，建議立即停機檢修！")
            
            # 指標卡片 (4 列卡片式排版)
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f'<div class="metric-card"><div class="metric-val">{report.get("defect_type", "未知")}</div><div class="metric-lbl">瑕疵分類</div></div>', unsafe_allow_html=True)
            with m2:
                sev_color = "🔴" if severity >= 4 else ("🟡" if severity >= 2 else "🟢")
                st.markdown(f'<div class="metric-card"><div class="metric-val">{sev_color} Lv.{severity}</div><div class="metric-lbl">嚴重度 ({report.get("severity_label", "良品")})</div></div>', unsafe_allow_html=True)
            with m3:
                conf = report.get("confidence_score", 0.95) * 100
                st.markdown(f'<div class="metric-card"><div class="metric-val">{conf:.1f}%</div><div class="metric-lbl">模型信心指數</div></div>', unsafe_allow_html=True)
            with m4:
                st.markdown(f'<div class="metric-card"><div class="metric-val" style="font-size: 1.05rem; color: #2563EB;">{report.get("machine_action", "正常放行")}</div><div class="metric-lbl">機台即時指令</div></div>', unsafe_allow_html=True)
            
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            
            # 分頁細節
            tab1, tab2, tab3, tab4 = st.tabs(["📝 缺陷特徵與根因", "🎯 瑕疵座標標註清單", "🛠️ 產線標準 SOP", "📄 結構化 JSON 匯出"])
            
            with tab1:
                st.markdown(f"**🔍 瑕疵細部特徵**：`{report.get('defect_subtype', '無')}` ｜ **受影響光學面積**：`{report.get('affected_area_percentage', '0%')}`")
                st.markdown("##### 📌 外觀特徵描述")
                st.info(report.get("defect_description", "無詳細描述"))
                st.markdown("##### 🔬 產線最可能根因分析 (Root Cause)")
                st.write(report.get("root_cause_analysis", "無異常，製程參數穩定。"))
                
            with tab2:
                boxes = report.get("bounding_boxes", [])
                if boxes and has_defect:
                    st.markdown(f"共偵測到 **{len(boxes)} 處** 瑕疵區域：")
                    for idx, b in enumerate(boxes, 1):
                        coords = b.get("box_2d", [])
                        st.markdown(f"- 🔴 **區域 #{idx}**：`{b.get('label', '瑕疵')}` ｜ 嚴重度：`Lv.{b.get('severity', 4)}` ｜ 座標範圍 `[ymin, xmin, ymax, xmax]`: `{coords}`")
                else:
                    st.info("✅ 未偵測到異常標註區域（全光學通光面判定為良品）")
                    
            with tab3:
                st.markdown("##### 📋 現場作業員 / 設備工程師處置步驟：")
                sops = report.get("action_sop", [])
                for item in sops:
                    st.markdown(f'<div class="sop-box">📌 {item}</div>', unsafe_allow_html=True)
                    
            with tab4:
                st.markdown("##### 📦 系統輸出標準 JSON Schema (可用於對接 MES / ERP 系統)")
                st.json(report)
                
                report_str = json.dumps(report, ensure_ascii=False, indent=2)
                st.download_button(
                    label="💾 下載 JSON 品保檢驗報告",
                    data=report_str,
                    file_name=f"AOI_Report_{lot_id}.json",
                    mime="application/json",
                    type="primary"
                )
                
            st.caption(f"✨ 運算引擎：{report.get('_model_used', 'Google Gemini 3.6 Flash')}")
else:
    if source_mode == "📂 上傳鏡片相片檢測":
        st.info("👆 請從上方選擇上傳一張鏡片相片（或開啟鏡頭拍照），開始進行多模態 AI 檢測。")
    else:
        st.info("👆 請點選上方任一瑕疵樣本按鈕（如：👉 測試 表面刮痕）立即啟動 AI 診斷與 HUD 畫框。")
