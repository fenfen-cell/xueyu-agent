# -*- coding: utf-8 -*-
"""雪域智学 · 藏汉双语教材智能助教 —— Streamlit 版

复用项目原有的 core.py / agent.py / ocr_local.py，不重写业务逻辑。
Run:  streamlit run streamlit_app.py
"""
import json
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ---- 把 Streamlit secrets 注入环境变量（大模型密钥）----
for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "OCR_ENDPOINT", "OCR_API_KEY"):
    try:
        if key in st.secrets and st.secrets[key]:
            os.environ[key] = str(st.secrets[key])
    except Exception:
        pass

DATA_DIR = Path(os.getenv("XY_DATA_DIR", str(ROOT / "data_runtime")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ["XY_DATA_DIR"] = str(DATA_DIR)
os.environ.setdefault("XY_NODE_EXECUTABLE", os.getenv("XY_NODE_EXECUTABLE", "node"))

from core import Store, make_quiz, public_quiz, grade_quiz, normalize  # noqa: E402
from agent import Agent  # noqa: E402

st.set_page_config(page_title="雪域智学 · 藏汉双语教材智能助教", page_icon="📚", layout="wide")


@st.cache_resource
def get_store():
    store = Store(DATA_DIR / "xueyu.db")
    # 首次运行播种演示教材
    if not store.list_docs():
        demo = json.loads((ROOT / "data" / "demo.json").read_text(encoding="utf-8"))
        store.import_text(demo["title"], demo["text"], demo["source"])
    return store


@st.cache_resource
def get_agent():
    return Agent(get_store())


STORE = get_store()
AGENT = get_agent()


def llm_ready():
    return bool(os.getenv("LLM_API_KEY") and os.getenv("LLM_MODEL"))


# ============================== 侧边栏 ==============================
st.sidebar.title("📚 雪域智学")
st.sidebar.caption("藏汉双语教材智能助教 · 教育赛道")
st.sidebar.divider()

docs = STORE.list_docs()
if not docs:
    st.sidebar.warning("还没有教材，请先在「教材库」导入")
    doc = None
else:
    labels = {d["id"]: f"{d['title']}（{d['paragraph_count']} 段）" for d in docs}
    doc_id = st.sidebar.selectbox("选择教材", list(labels), format_func=lambda x: labels[x])
    doc = STORE.get("docs", doc_id)

mode = st.sidebar.radio(
    "运行模式",
    ["本地检索（不需要密钥）", "大模型 + 工具调用"],
    index=1 if llm_ready() else 0,
)
mode_key = "llm" if mode.startswith("大模型") else "local"
if mode_key == "llm" and not llm_ready():
    st.sidebar.error("未配置 LLM_API_KEY / LLM_MODEL，请在 Secrets 里填")
elif mode_key == "llm":
    st.sidebar.success(f"已配置：{os.getenv('LLM_MODEL')}")

st.sidebar.divider()
st.sidebar.caption("演示账号（本地版不需要）")
st.sidebar.code("mobile_teacher\nzAGHrE4U4qH1qMxubqFL", language="text")
st.sidebar.caption("本地 OCR 与检索不产生任何接口费用。")

tabs = st.tabs(["💬 助教对话", "📝 出题与批改", "📖 教材库"])

# ============================== 助教对话 ==============================
with tabs[0]:
    if doc is None:
        st.info("请先在「教材库」导入教材或加载演示材料。")
    else:
        st.subheader("助教对话")
        st.caption("回答只依据教材原文，并给出段落编号；检索不到依据时会明确拒答。")

        if "msgs" not in st.session_state:
            st.session_state.msgs = []

        c1, c2, c3 = st.columns([1, 1, 3])
        preset = None
        if c1.button("📖 精讲本课", use_container_width=True):
            preset = "请逐段精讲这篇课文，给出藏汉对照与关键术语"
        if c2.button("🧑‍🏫 生成教案", use_container_width=True):
            preset = "请根据这节课生成一份 40 分钟的备课教案"

        for m in st.session_state.msgs:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

        prompt = st.chat_input("问教材里的任何内容，例如：水循环的过程是什么？")
        question = preset or prompt
        if question:
            st.session_state.msgs.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                with st.spinner("正在检索教材并组织回答…"):
                    try:
                        run = AGENT.run({"goal": question, "doc_id": doc["id"], "mode": mode_key})
                        answer = run.get("answer", "")
                        ok = run.get("citation_check_passed")
                        st.markdown(answer)
                        if not ok:
                            st.warning("引用检查未通过，已回退为原文摘录。")
                        with st.expander(f"原文依据（{len(run.get('citations') or [])} 段）"):
                            for c in run.get("citations") or []:
                                st.markdown(f"**`{c['id']}`**")
                                st.write(c["text"])
                        with st.expander("执行轨迹 Planner → Tools → Critic"):
                            for step in run.get("trace") or []:
                                st.markdown(f"`{step['step']}. {step['stage']} · {step['tool']}` — {step['elapsed_ms']} ms")
                        st.session_state.last_run = run
                        st.session_state.msgs.append({"role": "assistant", "content": answer})
                        if run.get("quiz"):
                            st.session_state.quiz = run["quiz"]
                    except Exception as exc:
                        st.error(f"执行失败：{exc}")

        if st.session_state.get("last_run"):
            run = st.session_state.last_run
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "⬇️ 下载讲稿（Markdown）",
                    data=(f"# 雪域智学教学任务\n\n任务：{run['goal']}\n\n{run['answer']}\n\n## 原文依据\n\n"
                          + "\n\n".join(f"[{c['id']}] {c['title']}\n\n{c['text']}" for c in run.get("citations") or [])),
                    file_name=f"lesson-{run['id']}.md",
                    mime="text/markdown",
                )
            with col2:
                st.download_button(
                    "⬇️ 下载执行轨迹（JSON）",
                    data=json.dumps(run, ensure_ascii=False, indent=2),
                    file_name=f"trace-{run['id']}.json",
                    mime="application/json",
                )

# ============================== 出题与批改 ==============================
with tabs[1]:
    if doc is None:
        st.info("请先在「教材库」导入教材。")
    else:
        st.subheader("出题与批改")
        st.caption("题目由教材原文挖空生成，答案不进题目接口；判分按原文精确匹配。")
        c1, c2, c3 = st.columns([1, 1, 2])
        count = c1.number_input("题数", 1, 8, 3)
        diff = c2.selectbox("难度", ["基础", "进阶"])
        if c3.button("生成练习", type="primary"):
            try:
                st.session_state.quiz = public_quiz(make_quiz(STORE, doc["id"], int(count), diff))
                st.session_state.grade = None
            except Exception as exc:
                st.error(f"生成失败：{exc}")

        quiz = st.session_state.get("quiz")
        if quiz:
            st.markdown(f"**{quiz['title']}**")
            answers = {}
            with st.form("quiz_form"):
                for i, q in enumerate(quiz["questions"]):
                    st.markdown(f"**第 {i+1} 题** · {q['difficulty']} · {q['type']}")
                    st.text(q["prompt"])
                    answers[q["id"]] = st.text_input(f"你的答案 {i+1}", key=f"ans_{q['id']}")
                submitted = st.form_submit_button("提交批改", type="primary")
            if submitted:
                try:
                    st.session_state.grade = grade_quiz(STORE, quiz["id"], answers)
                except Exception as exc:
                    st.error(f"批改失败：{exc}")

            g = st.session_state.get("grade")
            if g:
                st.metric("得分", f"{g['score']} / 100")
                st.caption(g["grading"])
                for i, item in enumerate(g["items"]):
                    if item["correct"]:
                        st.success(f"第 {i+1} 题 正确")
                    else:
                        st.error(f"第 {i+1} 题 需要复习")
                        st.write(f"你的答案：{item['given'] or '（未作答）'}")
                        st.write(f"原文答案：{item['expected']}")
                        st.write(item["feedback"])
                        if item.get("followup"):
                            st.info(f"巩固建议：{item['followup']}")
                    with st.expander(f"依据 {item['source_id']}"):
                        st.write(item["source_quote"])

# ============================== 教材库 ==============================
with tabs[2]:
    st.subheader("教材库")
    st.caption("支持粘贴文本、上传 UTF-8 TXT / Markdown。DOCX 与图片 OCR 请在原 Web 版使用。")

    title = st.text_input("教材名称", "我的教材")
    text = st.text_area("教材正文（每行一段）", height=180,
                        placeholder="水是生命活动不可缺少的物质。\nཆུ་ནི་མི་ཚེའི་གཞི་རྩ་ཡིན།")
    if st.button("导入教材", type="primary") and text.strip():
        try:
            STORE.import_text(title, text)
            st.cache_resource.clear()
            st.success("导入成功，请刷新页面选择该教材")
            st.rerun()
        except Exception as exc:
            st.error(f"导入失败：{exc}")

    st.divider()
    if doc:
        st.markdown(f"### {doc['title']}")
        st.caption(f"{doc['source']} · 共 {doc['paragraph_count']} 段 · 原始文本已保留")
        for p in doc["paragraphs"]:
            flag = "✅ 已确认" if p["reviewed"] else "⏳ 待确认"
            with st.expander(f"{flag} · {p['id']} · 第 {p['page']} 页"):
                new_text = st.text_area("校对文本", p["text"], key=f"ta_{p['id']}", height=90)
                if st.button("保存校对并确认", key=f"ok_{p['id']}"):
                    try:
                        STORE.review(doc["id"], p["id"], new_text)
                        st.success("已确认，可用于教学检索")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"保存失败：{exc}")

st.divider()
st.caption("雪域智学 · 教材入库 → 原文检索 → 精讲/出题/备课 → 引用检查。"
           "模型译文与教案须教师复核；未配置大模型时本地模式可用。")
