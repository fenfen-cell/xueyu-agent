# 雪域智学 · 藏汉双语教材智能助教（Streamlit 版）

复用项目原有 `core.py` / `agent.py` 的教材入库、原文检索、出题、批改与大模型工具调用，
用 Streamlit 重写交互层，便于在 Streamlit Community Cloud 一键部署。

## 本地运行
    pip install -r requirements.txt
    streamlit run streamlit_app.py

## 部署到 Streamlit Cloud
1. 推到 GitHub
2. https://share.streamlit.io  New app  选仓库  主文件填 streamlit_app.py
3. Settings - Secrets 里填 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
4. 不填密钥也能用：本地模式下的检索、出题、批改、备课模板都可用

## 与 Web 版的差异
- 不含 DOCX 解析、图片 OCR、逐段框选校对、多用户登录
- 保留：教材导入与校对、原文检索、精讲/教案、出题、判分、导出
