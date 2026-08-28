# 🔬 光學鏡片瑕疵多模態分析與診斷助手 (Optical Defect AI POC)

> **基於 Google Gemini 多模態視覺技術 (Multimodal Vision) 與 Streamlit 打造之智慧光學產線 AOI 瑕疵快速判定與 SOP 處置系統**

---

## 🌟 專案亮點與痛點解決

在光學鏡片製造業（如手機鏡頭、AR/VR 鏡片、車載鏡頭）中，傳統 AOI 往往存在誤判率高、無法直接提供「產線處置建議」與「根因推測」的問題。本 POC 展現了將 **多模態大模型 (Multimodal LLM)** 導入光學檢測的實戰能力：

- 👁️ **視覺多模態分析**：即時識別表面刮痕 (Scratch)、內部氣泡 (Bubble)、表面油污 (Stain)、邊緣崩角 (Chip) 等細部缺陷。
- 📊 **結構化工控輸出**：輸出標準 JSON Schema，包含嚴重度評級 (Level 1~5)、影響面積百分比、置信度。
- 🛠️ **生成式 SOP 指令**：直接依據機台編號與規格，自動生成現場人員可立即執行的標準作業流程 (SOP)。
- ⚡ **雙模式架構**：支援即時 Google Gemini 1.5 API，並內建離線工控模擬展示引擎（未設定 API Key 亦能流暢 Demo）。

---

## 📁 專案檔案結構

```text
ai/
├── app.py                 # Streamlit Web 互動儀表板主程式
├── detector.py            # Gemini 多模態視覺分析核心與結構化 JSON 解析
├── generate_samples.py    # 內建光學鏡片瑕疵圖檔產生腳本
├── requirements.txt       # Python 依賴套件清單
├── samples/               # 內建預設測試圖庫 (刮痕、氣泡、油污、崩角、良品)
│   ├── scratch.png
│   ├── bubble.png
│   ├── stain.png
│   ├── chip.png
│   └── clean.png
└── README.md              # 專案與公開部署說明
```

---

## 🚀 本地快速啟動

### 1. 啟動虛擬環境並安裝套件
```bash
./.venv/bin/pip install -r requirements.txt
```

### 2. 產生預設測試樣本（若尚未產生）
```bash
./.venv/bin/python generate_samples.py
```

### 3. 啟動 Web 儀表板
```bash
./.venv/bin/streamlit run app.py
```
啟動後在瀏覽器打開 `http://localhost:8501` 即可操作！

---

## 🌐 免費放上網路公開展示教學 (3 種方法)

### 方法一：部署到 Streamlit Community Cloud (最推薦，永久免費)
1. 將本專案資料夾上傳至你的 **GitHub Repository**（設為 Public 或 Private 皆可）。
2. 前往 [share.streamlit.io](https://share.streamlit.io/) 並使用 GitHub 登入。
3. 點擊 **"New app"**，選擇你的 Repository，Main file path 填寫 `app.py`。
4. 點擊 **"Deploy!"**，約 1 分鐘後即可獲得專屬公開網址（例如：`https://optical-defect-ai.streamlit.app`）。
5. *(可選)* 在 Streamlit Cloud 後台 Settings -> Secrets 中設定 `GEMINI_API_KEY = "你的金鑰"`。

---

### 方法二：部署到 Hugging Face Spaces (免費)
1. 註冊 [Hugging Face](https://huggingface.co/) 並建立一個新的 **Space**（SDK 選擇 **Streamlit**）。
2. 將 `app.py`、`detector.py`、`requirements.txt` 及 `samples/` 目錄上傳至 Space Repository。
3. 系統將自動建置並提供公開存取連結。

---

### 方法三：本機外網穿透 (即時面試演示)
若不想上傳 GitHub，可以在本機啟動 `cloudflared` 或 `ngrok`：
```bash
# 使用免費 cloudflare tunnel 一秒穿透
npx cloudflared tunnel --url http://localhost:8501
```
終端機會輸出一個臨時的公開 HTTPS 網址，直接傳給面試官即可打開觀看。
