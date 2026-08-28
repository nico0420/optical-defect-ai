import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel, AutoModelForCausalLM

# ==========================================================
# 準備階段：建立企業內部知識庫
# ==========================================
knowledge_base = [
    "玉晶光電的員工報帳流程：每月 25 號前需在 ERP 系統填寫單據，並附上發票正本。",
    "廠區伺服器機房門禁規定：非 IT 部門人員進入，需由 IT 主管簽核並於訪客名簿登記。",
    "產線 AOI 檢測機台異常處理原則：若誤判率超過 3%，應立即通報設備工程師進行校正。",
    "員工出差差旅費補助：國內差旅每日膳雜費上限為 800 元，住宿費憑發票實報實銷，上限 2500 元。",
    "機房重大警報應變措施：若發生火災或溫濕度異常，系統會自動發送簡訊給 IT 輪值人員，並於 15 分鐘內到場處置。"
]

# ==========================================================
# 1. 載入開源中文 Embedding 向量模型 (BAAI/bge-small-zh-v1.5)
# ==========================================================
print("=== [1/3] 載入開源中文 Embedding 模型 (BGE-Small-ZH) ===")
embed_model_name = "BAAI/bge-small-zh-v1.5"
embed_tokenizer = AutoTokenizer.from_pretrained(embed_model_name, local_files_only=True)
embed_model = AutoModel.from_pretrained(embed_model_name, local_files_only=True)

def encode_texts(texts):
    """BGE 模型向量編碼 (取 [CLS] Token 並做 L2 正規化)"""
    encoded_input = embed_tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
    with torch.no_grad():
        model_output = embed_model(**encoded_input)
        sentence_embeddings = model_output[0][:, 0]
        sentence_embeddings = torch.nn.functional.normalize(sentence_embeddings, p=2, dim=1)
    return sentence_embeddings.numpy()

# 建立知識庫向量索引
doc_vectors = encode_texts(knowledge_base)
print(f"✅ 知識庫向量索引建立完成，共 {len(knowledge_base)} 筆資料。\n")

# ==========================================================
# 2. 檢索模組 (Retrieval - Top-K 語意相似度檢索)
# ==========================================================
def retrieve_docs(query: str, top_k: int = 2):
    query_vector = encode_texts([query])[0]
    similarities = np.dot(doc_vectors, query_vector)
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    results = []
    for idx in top_indices:
        results.append({
            "doc": knowledge_base[idx],
            "score": float(similarities[idx])
        })
    return results

# ==========================================================
# 3. 載入開源本地 LLM (Qwen2.5-0.5B-Instruct)
# ==========================================================
print("=== [2/3] 載入開源 LLM 生成模型 (Qwen2.5-0.5B-Instruct) ===")
llm_model_name = "Qwen/Qwen2.5-0.5B-Instruct"
device = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"使用硬體加速運算裝置: {device.upper()}")

llm_tokenizer = AutoTokenizer.from_pretrained(llm_model_name, local_files_only=True)
llm_model = AutoModelForCausalLM.from_pretrained(
    llm_model_name,
    local_files_only=True
).to(device)

print("✅ 開源 LLM 模型載入成功！(100% 本地運算、完全免費、無須 API 金鑰)\n")

# ==========================================================
# 4. 運行 RAG 完整流程 (檢索 -> 提示詞增強 -> 生成)
# ==========================================================
def ask_rag(user_query: str):
    print("=" * 70)
    print(f"👤 使用者提問: {user_query}")
    print("=" * 70)
    
    # 步驟 1：檢索 (Retrieval)
    retrieved = retrieve_docs(user_query, top_k=2)
    print("\n🔍 【步驟 1：檢索到的最相關參考資料 (Top-2)】")
    for i, item in enumerate(retrieved, 1):
        print(f"  {i}. [相關度 {item['score']:.4f}] {item['doc']}")
    
    # 步驟 2：提示詞增強 (Augmentation)
    context_text = "\n".join([f"{i+1}. {item['doc']}" for i, item in enumerate(retrieved)])
    messages = [
        {
            "role": "system", 
            "content": "你是企業 AI 助手。請嚴格根據【參考資料】回答【問題】，用繁體中文簡明扼要回答。"
        },
        {
            "role": "user", 
            "content": f"【參考資料】\n{context_text}\n\n【問題】\n{user_query}"
        }
    ]
    
    # 步驟 3：本地生成 (Generation)
    print("\n🤖 【步驟 3：本地開源 LLM 生成回覆中...】")
    prompt = llm_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = llm_tokenizer(prompt, return_tensors="pt").to(device)
    
    with torch.no_grad():
        generated_ids = llm_model.generate(
            **inputs,
            max_new_tokens=180,
            repetition_penalty=1.15,
            temperature=0.2,
            do_sample=True,
            pad_token_id=llm_tokenizer.eos_token_id
        )
    
    input_len = inputs.input_ids.shape[1]
    response_ids = generated_ids[0][input_len:]
    generated_reply = llm_tokenizer.decode(response_ids, skip_special_tokens=True)
    
    print(f"\n💡 【AI 生成回答】:\n{generated_reply.strip()}\n")

if __name__ == "__main__":
    # 測試問題 1
    ask_rag("非 IT 人員要進入機房有什麼規定？")
    
    # 測試問題 2
    ask_rag("員工出差住宿費上限是多少？")
    
    # 測試問題 3
    ask_rag("員工每個月報帳有什麼期限與規定？")
