const commandStrip = (title, command, detail = "在终端中的 Coding Agent 执行；网页读取生成后的项目文件。") => `
  <div class="command-card">
    <div><span>CODING AGENT · TERMINAL</span><strong>${title}</strong><small>${detail}</small></div>
    <code>${command}</code><button type="button" data-copy="${command}">复制命令</button>
  </div>`;

const pendingRows = (xs, series) => xs.map(x => `<tr><th>${x}</th>${series.map(() => `<td class="demo-pending">PENDING</td>`).join("")}</tr>`).join("");

const blankFigureWithSource = ({ id, title, dataset, metric, xLabel, xs, series }) => `
  <section class="evidence-artifact">
    <p class="artifact-kicker">${id} · DATA-DRIVEN FIGURE</p>
    <h4>${title}</h4>
    <p>${dataset} · ${metric}。左侧数字表是唯一绘图来源；任何一格未验证，右图都保持空白。</p>
    <div class="figure-data-pair">
      <div class="numeric-source">
        <div class="table-scroll"><table class="result-shell source-table"><thead><tr><th>${xLabel}</th>${series.map(name => `<th>${name}</th>`).join("")}</tr></thead><tbody>${pendingRows(xs, series)}</tbody></table></div>
        <p class="field-line">Required fields → model_id · intent_id · style_id · layer_id · judge_label</p>
      </div>
      <div class="blank-chart" aria-label="Empty chart waiting for verified data">
        <div class="blank-axis blank-y"></div><div class="blank-axis blank-x"></div>
        <strong>等待验证数据</strong><span>表格全部 FILLED 后，才调用同一 Python 脚本画图</span>
      </div>
    </div>
  </section>`;

const mainPendingTable = () => {
  const methods = ["No Defense", "ABD", "RTV", "JBShield", "TrajGuard", "First-Divergence Repair"];
  return `<section class="evidence-artifact"><p class="artifact-kicker">T1 · MAIN RESULTS</p><h4>安全、过度拒答与通用能力必须同表出现</h4><div class="table-scroll"><table class="result-shell main-result"><thead><tr><th>Method</th><th>AdvBench DSR ↑</th><th>HarmBench DSR ↑</th><th>XSTest false refusal ↓</th><th>Just-Eval retention ↑</th></tr></thead><tbody>${methods.map(name => `<tr><th>${name}</th>${[0,1,2,3].map(() => `<td class="demo-pending">PENDING</td>`).join("")}</tr>`).join("")}</tbody></table></div><p class="field-line">24 个单元格全部 RUN_LOCAL；不复制论文数字。每格绑定 raw JSON/JSONL、实际命令、配置与 bootstrap 区间。</p></section>`;
};

const experimentPlanDemo = () => `
  <section class="plain-section"><p class="artifact-kicker">PROJECTED PAPER</p><h4>First-Divergence Repair: Causal Single-Layer Recovery from Style-Induced Jailbreaks</h4><ul><li><strong>C1</strong>：匹配语义的风格变换产生可复现的首次 safety-tube exit。</li><li><strong>C2</strong>：只修首次偏离层，后续轨迹应自行恢复；错误层或重复修复若并列，主张失败。</li><li><strong>C3</strong>：必须同时改善 DSR、XSTest、Just-Eval 与部署成本，而不是只降低 ASR。</li></ul></section>
  ${mainPendingTable()}
  ${blankFigureWithSource({id:"F3A",title:"修复层偏移：首次偏离层是否有唯一峰值？",dataset:"AdvBench 50 + XSTest",metric:"Safety recovery + benign utility retention",xLabel:"Offset from first exit",xs:[-3,-2,-1,0,1,2,3],series:["Safety recovery","Utility retention"]})}
  ${blankFigureWithSource({id:"F4",title:"修复强度的 safety–utility 曲线",dataset:"AdvBench + HarmBench + XSTest",metric:"DSR / 1−false refusal / Just-Eval retention",xLabel:"Repair strength",xs:[0.25,0.5,0.75,1.0,1.25],series:["Defense success","1−false refusal","Just-Eval"]})}
  <section class="plain-section"><p class="artifact-kicker">CAUSAL ABLATIONS</p><h4>T2 不做装饰性消融，只攻击核心因果主张</h4><ul><li>Full first-exit repair</li><li>Random layer</li><li>ABD-selected layer</li><li>Latest-exit layer</li><li>Repeated multi-layer repair</li></ul></section>`;

const runParts = [
  ["P1", "Instrumentation", [["→", "G1.1", "最小可复现轨迹通路", "F1 · 非实验动机图规格"]]],
  ["P2", "Problem-Existence Validation", [["○", "G2.1", "AdvBench 首次偏离探针", "F2 · exit depth"],["○", "G2.2", "HarmBench 成功/失败退出集中度", "F2 · concentration"]]],
  ["P3", "Method Feasibility", [["○", "G3.1", "单模型单点修复可行性", "无直接图表"]]],
  ["P4", "Development Tuning", [["○", "G4.1", "冻结 safety-tube threshold", "无直接图表"],["○", "G4.2", "冻结最小有效 repair strength", "无直接图表"]]],
  ["P5", "Primary Evidence", [["○", "G5.1", "三模型、五基线统一协议主比较", "T1"]]],
  ["P6", "Causal Controls and Ablation", [["○", "G6.1", "修复层偏移因果曲线", "F3A"],["○", "G6.2", "下游轨迹恢复检验", "F3B"],["○", "G6.3", "唯一性消融矩阵", "T2"]]],
  ["P7", "Robustness and Sensitivity", [["○", "G7.1", "修复强度鲁棒性", "F4"]]],
  ["P8", "Cost and Failure Analysis", [["○", "G8.1", "延迟、显存与未恢复案例", "T3"]]]
];

const goalHierarchy = () => `<section class="goal-hierarchy"><p class="artifact-kicker">8 PARTS · 12 GOALS · ONE UNLOCKED</p>${runParts.map(([pid,title,goals]) => `<div class="part-row"><h4><span>${pid}</span>${title}</h4>${goals.map(([mark,gid,name,dest]) => `<div class="expanded-goal"><b>${mark}</b><strong>${gid} · ${name}</strong><span>对应图表：${dest}</span><p>${gid === "G1.1" ? "先打通一个模型、极小输入切片、层×token trace、judge 与 provenance；重复两次结果结构一致后才解锁下一 Goal。" : "前置 Gate 完成后才解锁；每个原子结果先落盘并写 ledger，再计算聚合值。"}</p></div>`).join("")}</div>`).join("")}</section>`;

const resultProvenanceDemo = () => `
  <section class="evidence-artifact"><p class="artifact-kicker">05_EXP_RESULT · PENDING COUNTERPART</p><h4>图表几何与 03 完全相同，未完成数字不会被插值</h4>
    <div class="provenance-flow"><span>raw JSONL</span><i>→</i><span>已验证结果记录</span><i>→</i><span>验证公式</span><i>→</i><span>填入源数据表</span><i>→</i><span>生成图</span></div>
    <p class="demo-value-line">下面是<strong>界面功能示例，不是本项目实验结果</strong>：<a href="#demo-provenance" class="trace-value">0.81</a> 点击数字跳到同页、已展开的生成过程。</p>
    <div id="demo-provenance" class="open-provenance"><h5>生成过程 · DEMO VALUE 0.81</h5><dl><dt>Goal</dt><dd>G7.1</dd><dt>Metric</dt><dd>Just-Eval retention</dd><dt>Raw artifact</dt><dd>results/first_divergence_repair/g7_1.json</dd><dt>Calculation</dt><dd>三个批准模型的 full-precision macro mean；display rounding only</dd><dt>Command</dt><dd>python -m code.first_divergence.acquire --artifact F4</dd><dt>Status</dt><dd>界面演示数据 · NOT A SCIENTIFIC RESULT</dd></dl></div>
  </section>`;

let reportStructures = {};

const reportDocument = (key, kicker = "FIXED HTML STRUCTURE · FILLED EXAMPLE") => {
  const report = reportStructures[key];
  if (!report) return "";
  return `<article class="report-document" aria-label="${report.artifact} filled example">
    <header><span>${kicker}</span><h4>${report.artifact}</h4><p>${report.note}</p></header>
    ${report.sections.map(section => `<section data-structure-section="${key}:${section.number}">
      <div class="report-section-title"><span>${section.number}</span><h5>${section.title}</h5></div>
      <p>${section.content}</p>
      ${section.details?.length ? `<ul>${section.details.map(detail => `<li>${detail}</li>`).join("")}</ul>` : ""}
    </section>`).join("")}
  </article>`;
};

const stages = [
  {
    id: "profile", short: "研究画像", path: "profile", title: "先理解研究者，再开始研究",
    compare: ["以任务上下文和通用配置为主要起点", "适合快速进入自动探索", "先建立可检查的个性化依据"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 01 · PROFILECONSTRUCT</p><h3>研究画像由终端生成，网页负责阅读</h3><p>先手动下载完整 Scholar 主页；这里没有上传 HTML 或在网页运行 Skill 的假入口。</p></div><span class="status-pill">COMPLETE</span></div>
      ${commandStrip("读取本地 Scholar HTML 并建立画像", "$profileconstruct 使用 ~/Downloads/scholar_profile.html")}
      ${reportDocument("profile", "CANONICAL PROFILE HTML")}`
  },
  {
    id: "literature", short: "文献 Survey", path: "literature", title: "先建立可核验的文献地图", compare: null,
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 02 · RESEARCHLIT</p><h3>检索、核验并组织研究版图</h3><p>Survey 与 Idea 分开；每篇工作都能回到实际打开的来源。</p></div><span class="status-pill">54 VERIFIED</span></div>
      ${commandStrip("生成独立文献 Survey", "$researchlit stylish jailbreak")}
      ${reportDocument("literature")}`
  },
  {
    id: "ideas", short: "Idea 选择", path: "ideas", title: "候选先过门槛，再由研究者选择",
    compare: ["通常用排序快速呈现候选方向", "研究者再判断价值与新颖性", "把新颖性与可证伪性设为独立硬门槛"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 03 · IDEAGEN</p><h3>候选 Idea 逐项说明，最终选择由研究者确认</h3><p>报告依次给出文献边界、排序依据、候选正文和人工选择记录。</p></div><span class="status-pill">HUMAN PICK</span></div>
      ${commandStrip("生成并核验多个 Candidate Idea", "$ideagen")}
      ${reportDocument("ideas")}`
  },
  {
    id: "expplan", short: "实验设计", path: "experiment-plan", title: "先固定证据空位，再反推实验",
    compare: ["从任务目标和实验空间开始探索", "论文结构通常在结果后整理", "先固定图表与证据空位，避免漏证据和事后叙事"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 04 · EXPPLAN</p><h3>Projected Paper 先于实验任务</h3><p>下面直接依据真实的 03 HTML：I1、ACL 2027、7 个正文图表、144 个逐格待填数字。</p></div><span class="status-pill">APPROVED</span></div>
      ${commandStrip("生成实验设计与待填图表", "$expplan")}
      ${reportDocument("expplan")}
      ${reportDocument("projected-paper", "PROJECTED PAPER · FIXED SUBSECTIONS")}
      ${experimentPlanDemo()}`
  },
  {
    id: "runplan", short: "实验执行", path: "run-plan", title: "一次执行一个 Goal，完成即填表并整理",
    compare: ["强调连续自主探索与整体吞吐", "适合可自动判分的大规模搜索", "每个 Goal 落盘、验证、填表、打勾，再解锁下一项"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 05 · RUNPLAN + /GOAL</p><h3>计划、执行状态和结果证据连续呈现</h3><p>真实 Run Plan 有 8 Parts、12 Goals；当前只解锁最小基础设施 G1.1，结果页保持 0/144。</p></div><span class="status-pill">G1.1 UNLOCKED</span></div>
      ${commandStrip("执行当前唯一 Goal G1.1", "/goal Complete G1.1: build and verify the minimal reproducible layer×token trace path")}
      ${reportDocument("runplan")}
      ${goalHierarchy()}
      ${reportDocument("results", "EXPERIMENT RESULTS · PENDING COUNTERPART")}
      ${resultProvenanceDemo()}`
  },
  {
    id: "paper", short: "论文写作", path: "paper-writing", title: "逐段写作、实时编译、图表可编辑",
    compare: ["倾向批量生成 Markdown 或 LaTeX 草稿", "适合快速获得整体版本", "逐段确认，接受后才写入 LaTeX 并实时编译"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STOP BOUNDARY · PAPERWRITE NEXT</p><h3>本次真实流水线在写论文前停止</h3><p>03 已批准，04/05 已生成；只有执行完 Goals、144 个数字通过 provenance 校验后，才能进入 paperwrite。</p></div><span class="status-pill">NOT STARTED</span></div>
      ${commandStrip("结果完成后才启动", "$paperwrite", "本 Demo 不伪造论文正文、LaTeX 或已完成 PDF。")}
      ${reportDocument("paper-studio", "PAPER STUDIO · WRITING INTERFACE")}
      <section class="plain-section"><p class="artifact-kicker">ENTRY CONTRACT</p><h4>Paperwrite 将消费什么</h4><ul><li>批准且保持空白的 03 Projected Paper</li><li>04 中全部完成并打勾的 Goal 状态</li><li>05 中由 validated ledger 填入的同构图表</li><li>每个数字可回到 raw artifact、实际命令、代码、配置与计算公式</li></ul></section>`
  }
];

const state = { stage: 0 };
const nav = document.querySelector("#journey-nav");
const content = document.querySelector("#stage-content");
const path = document.querySelector("#browser-path");
const comparePanel = document.querySelector("#compare-panel");
const browserBody = document.querySelector(".browser-body");

function stageIndexFromLocation() {
  const hashPath = window.location.hash.replace(/^#\/?/, "");
  const pagePath = window.location.pathname.split("/").filter(Boolean).at(-1) || "";
  const requestedPath = hashPath || pagePath;
  const index = stages.findIndex(stage => stage.path === requestedPath);
  return index >= 0 ? index : 0;
}

function syncStageFromLocation() {
  const nextStage = stageIndexFromLocation();
  if (nextStage === state.stage || !Object.keys(reportStructures).length) return;
  state.stage = nextStage;
  renderStage();
}

function renderNav() {
  nav.innerHTML = stages.map((stage, index) => `<button class="journey-step ${index === state.stage ? "active" : ""}" data-stage="${index}" type="button"><span>0${index + 1}</span><strong>${stage.short}</strong></button>`).join("");
}

function renderCompare() {
  const stage = stages[state.stage];
  comparePanel.hidden = !stage.compare;
  browserBody.classList.toggle("comparing", Boolean(stage.compare));
  comparePanel.innerHTML = stage.compare ? `<p class="eyebrow">工作方式对比</p><h4>${stage.short}的工作重心</h4><div class="compare-card bad"><span>常见 AUTORESEARCH 侧重</span><strong>${stage.compare[0]}</strong><p>${stage.compare[1]}</p></div><div class="compare-card good"><span>RESEARCH AVATAR 侧重</span><strong>${stage.title}</strong><p>${stage.compare[2]}</p></div>` : "";
}

function renderStage() {
  const stage = stages[state.stage];
  renderNav();
  path.textContent = `research-avatar-demo.pages.dev/${stage.path}`;
  content.innerHTML = stage.render();
  content.scrollTop = 0;
  renderCompare();
}

nav.addEventListener("click", event => {
  const button = event.target.closest("[data-stage]");
  if (button) {
    state.stage = Number(button.dataset.stage);
    window.history.pushState(null, "", `#${stages[state.stage].path}`);
    renderStage();
  }
});

window.addEventListener("popstate", syncStageFromLocation);
window.addEventListener("hashchange", syncStageFromLocation);

document.addEventListener("click", async event => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  const original = button.textContent;
  try { await navigator.clipboard.writeText(button.dataset.copy); button.textContent = "已复制 ✓"; }
  catch { button.textContent = "请手动复制"; }
  setTimeout(() => { button.textContent = original; }, 1400);
});

async function initializeDemo() {
  try {
    const response = await fetch("report-structures.json?v=20260814-persistent-tabs");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    reportStructures = await response.json();
    state.stage = stageIndexFromLocation();
    renderStage();
  } catch (error) {
    content.innerHTML = `<div class="demo-load-error"><strong>Demo structure failed to load.</strong><span>${String(error)}</span></div>`;
  }
}

initializeDemo();
