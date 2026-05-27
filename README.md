# Watson — AI Research Assistant

Watson 是一个本地运行的 AI 科研助手，覆盖从 **Idea 验证** 到 **论文撰写** 的完整研究流程。支持 Streamlit 网页界面和命令行两种使用方式。

---

## 功能概览

Watson 将科研流程拆解为六个步骤，每步由独立 Agent 驱动：

| 步骤 | 功能 | 说明 |
|------|------|------|
| 💡 Step 1 | Idea Validation | 从顶会 acceptance list 检索相关论文，按相关性评分，生成深度评审报告（新颖性 / 可行性 / Go-NoGo 建议） |
| 🔬 Step 2 | Experiment Design | 基于 Idea 设计实验方案，明确 baseline、指标与实验设置 |
| 💻 Step 3 | Code Generation | 自动生成可运行的实验代码（默认 PyTorch） |
| ▶️ Step 4 | Run & Record | 本地执行实验，记录运行日志与结果 |
| 📊 Step 5 | Analysis & Iteration | 分析实验结果，给出迭代建议 |
| 📝 Step 6 | Paper Writing | 生成 LaTeX 论文草稿 |

### Step 1 支持三种审稿风格

| 风格 | 会议 |
|------|------|
| ML | NeurIPS / ICML / ICLR |
| NLP | ACL / EMNLP / NAACL |
| CV | CVPR / ICCV / ECCV |

论文来源为各会议官方网站的 acceptance list（CVF Open Access、ACL Anthology、OpenReview、papers.nips.cc、PMLR），本地缓存 30 天，避免重复爬取。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
```

`.env` 示例：

```
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_MODEL=deepseek-chat
```

### 3. 启动网页界面（推荐）

```bash
streamlit run app.py
```

浏览器访问 `http://localhost:8501`

### 4. 或使用命令行

```bash
python watson.py                    # 交互式 REPL
python watson.py idea "你的研究方向"  # 一键运行 Step 1
```

---

## 命令行命令

```
idea [描述]        💡 输入研究方向，搜索论文并验证
design [约束]      🔬 设计实验方案
code [框架]        💻 生成实验代码（默认 PyTorch）
run                ▶️  执行实验（需加 --yes 确认）
analyze [备注]     📊 分析结果并给出迭代建议
paper [风格提示]   📝 生成 LaTeX 论文草稿
status             查看当前进度
papers             列出已找到的论文
show <文件名>      显示已生成的文件
help               帮助
```

---

## 项目结构

```
Watson/
├── app.py                  # Streamlit 网页界面
├── watson.py               # 命令行入口
├── requirements.txt
├── watson/
│   ├── agents/
│   │   ├── idea.py         # Step 1: Idea 验证
│   │   ├── experiment.py   # Step 2: 实验设计
│   │   ├── code.py         # Step 3: 代码生成
│   │   ├── run.py          # Step 4: 运行实验
│   │   ├── analysis.py     # Step 5: 结果分析
│   │   └── paper.py        # Step 6: 论文撰写
│   ├── tools/
│   │   ├── conf_search.py  # 会议论文爬取与相关性评分
│   │   └── paper_search.py # Semantic Scholar 备用搜索
│   ├── config.py
│   ├── llm.py
│   └── state.py
└── .watson/                # 运行时状态与缓存（自动生成，不入库）
```

---

## 依赖

- [DeepSeek API](https://platform.deepseek.com/)（LLM 后端）
- Python 3.10+
- 主要库：`streamlit`, `openai`, `beautifulsoup4`, `lxml`, `rich`, `requests`
