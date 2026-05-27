import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# LLM settings
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_TIMEOUT: int = int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "120"))

# Paper search
SEMANTIC_SCHOLAR_API_KEY: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
NCBI_EMAIL: str = os.getenv("NCBI_EMAIL", "")

# Directories — resolved from working directory at import time
PROJECT_ROOT = Path.cwd()
WATSON_DIR = PROJECT_ROOT / ".watson"
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"
PAPER_DIR = PROJECT_ROOT / "paper"

# State files
STATE_FILE = WATSON_DIR / "state.json"
PAPERS_FILE = WATSON_DIR / "papers.json"          # legacy flat list
SIMILAR_PAPERS_FILE = WATSON_DIR / "papers_similar.json"
TOP_CONF_PAPERS_FILE = WATSON_DIR / "papers_top_conf.json"
IDEA_FILE = WATSON_DIR / "idea.md"
IDEA_ASSESSMENT_FILE = WATSON_DIR / "idea_assessment.md"
EXPERIMENT_FILE = WATSON_DIR / "experiment.md"
CODE_FILE = EXPERIMENTS_DIR / "experiment.py"
RUN_LOG_FILE = WATSON_DIR / "run_log.txt"
RESULTS_FILE = WATSON_DIR / "results.md"
ANALYSIS_FILE = WATSON_DIR / "analysis.md"
PAPER_FILE = PAPER_DIR / "paper.tex"

# Step metadata
STEPS = ["idea", "experiment", "code", "run", "analysis", "paper"]
STEP_NAMES = {
    "idea":       "Step 1: Idea Validation",
    "experiment": "Step 2: Experiment Design",
    "code":       "Step 3: Code Generation",
    "run":        "Step 4: Run & Record",
    "analysis":   "Step 5: Analysis & Iteration",
    "paper":      "Step 6: Paper Writing",
}
STEP_EMOJIS = {
    "idea":       "💡",
    "experiment": "🔬",
    "code":       "💻",
    "run":        "▶️",
    "analysis":   "📊",
    "paper":      "📝",
}
