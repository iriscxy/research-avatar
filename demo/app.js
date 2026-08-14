const commandStrip = (title, command, detail = "在终端中的 Coding Agent 执行；网页读取生成后的项目文件。") => `
  <div class="command-card">
    <div><span>CODING AGENT · TERMINAL</span><strong>${title}</strong><small>${detail}</small></div>
    <code>${command}</code><button type="button" data-copy="${command}">复制命令</button>
  </div>`;

const pendingRows = (xs, series) => xs.map(x => `<tr><th>${x}</th>${series.map(() => `<td class="demo-pending">PENDING</td>`).join("")}</tr>`).join("");

const pendingTable = ({ headers, rows, className = "" }) => `
  <div class="table-scroll"><table class="result-shell source-table ${className}"><thead><tr>${headers.map(name => `<th>${name}</th>`).join("")}</tr></thead><tbody>${rows.map(name => `<tr><th>${name}</th>${headers.slice(1).map(() => `<td class="demo-pending">PENDING</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;

const projectedPanel = ({ title, dataset, metric, fields, xLabel, xs, series, image }) => `
  <section class="projected-panel">
    <h5>${title}</h5>
    <p><strong>Dataset / benchmark:</strong> ${dataset}</p>
    <p><strong>Metric / axes:</strong> ${metric}</p>
    <div class="figure-data-pair">
      <div class="numeric-source">
        ${pendingTable({headers:[xLabel,...series],rows:xs})}
        <p class="field-line">Required fields → ${fields}</p>
      </div>
      <figure class="projected-chart">
        <img src="${image}" alt="${title} projected preview">
        <figcaption>PROJECTED SHAPE — NOT RESULTS · 左表才是后续实验必须填入的真实数字来源。</figcaption>
      </figure>
    </div>
  </section>`;

const resultTable = ({ id, title, headers, rows, note }) => `
  <section class="evidence-artifact result-table-artifact">
    <p class="artifact-kicker">${id} · RESULT PLACEHOLDER — NO NUMBERS FABRICATED</p>
    <h4>${title}</h4>
    ${pendingTable({headers,rows,className:"main-result"})}
    <p>${note}</p>
  </section>`;

const experimentPlanDemo = () => {
  const methods = ["No Defense", "ABD", "RTV", "JBShield", "TrajGuard", "First-Divergence Repair"];
  return `
    <article class="actual-expplan">
      <header class="expplan-title">
        <p class="artifact-kicker">EXPERIMENT PLAN · I1 · APPROVED 2026-08-09</p>
        <h4>First-Divergence Repair</h4>
        <p>从预计论文反推证据：每一个数字都保持待填，每一个图形都绑定旁侧真实数据表。</p>
        <div class="expplan-facts"><span>ACL 2027</span><span>4 figures</span><span>3 tables</span><span>144 pending cells</span><span>4×A100 · 428 GPU-hours</span></div>
      </header>

      <section class="plain-section">
        <p class="artifact-kicker">1 · TARGET AND REFERENCES</p>
        <h4>Target Conference and Reference Papers</h4>
        <ul><li><strong>Target:</strong> ACL 2027 Main Conference / Long Paper.</li><li><strong>Mechanism reference:</strong> RTV，负责科学问题、轨迹机制和必须击败的比较地板。</li><li><strong>Researcher-owned structure reference:</strong> ABD，只负责段落功能、章节比例和图表节奏。</li></ul>
      </section>

      <section class="plain-section projected-paper-overview">
        <p class="artifact-kicker">2 · PROJECTED PAPER</p>
        <h4>Projected Paper</h4>
        <p>这一整节固定预计论文的标题摘要、段落蓝图、代表性图表证据壳、可证伪主张、实现方式与预算；下面的 2.1–2.6 都属于本节。</p>
      </section>

      <section class="plain-section projected-abstract">
        <p class="artifact-kicker">2.1 · PROJECTED TITLE AND ABSTRACT</p>
        <h4>First-Divergence Repair: Causal Single-Layer Recovery from Style-Induced Jailbreaks</h4>
        <p>We test whether intent-preserving style transformations cause a reproducible first exit from a model's safety trajectory and whether repairing only that layer restores downstream safety. A unified white-box framework compares five rerun representation defenses across AdvBench, HarmBench, XSTest, and Just-Eval. The claim survives only if first-exit repair uniquely beats wrong-layer and repeated-repair controls while improving the safety–utility–cost frontier.</p>
      </section>

      <section class="plain-section">
        <p class="artifact-kicker">2.2 · FIGURE/TABLE COUNT</p>
        <h4>7 个 claim-bearing floats</h4>
        <p>计划冻结为 4 figures 和 3 tables；Demo 只展开两个代表性证据壳：一张数据图 F2A 和一张主结果表 T1。其余图表保留在真实实验计划中，不在首页重复铺开。</p>
      </section>

      <section class="plain-section setup-section">
        <p class="artifact-kicker">2.3 · PARAGRAPH BLUEPRINT AND EVIDENCE SHELLS</p><h4>论文段落与图表证据逐项绑定</h4>
        <h5 class="embedded-heading">Projected Experiments Setup</h5>
        <dl class="setup-grid"><dt>Models</dt><dd>Llama-3.1-8B-Instruct · Mistral-7B-Instruct-v0.3 · Qwen2.5-7B-Instruct</dd><dt>Harmful</dt><dd>AdvBench 50-behavior subset · HarmBench 1.0</dd><dt>Benign / quality</dt><dd>XSTest · Just-Eval · Alpaca benign controls</dd><dt>Safety judge</dt><dd>SORRY-Bench evaluator</dd><dt>Baselines</dt><dd>No Defense · ABD · RTV · JBShield · TrajGuard</dd><dt>Metrics</dt><dd>First-exit stability · Downstream trajectory recovery · DSR · XSTest false refusal · Just-Eval retention · latency overhead</dd></dl>
      </section>

      <section class="evidence-artifact">
        <p class="artifact-kicker">FIGURE EXAMPLE · F2A · CLAIM C1</p><h4>Where the safety trajectory first leaves its tube</h4>
        ${projectedPanel({title:"F2A · Where safety trajectories leave the tube",dataset:"AdvBench 50 + matched-style counterfactuals",metric:"Safety-tube exit rate; x = normalized transformer depth; y = exit rate",fields:"model_id · intent_id · style_id · layer_id · tube_exit",xLabel:"Normalized transformer depth",xs:["0.0","0.14","0.29","0.43","0.57","0.71","0.86","1.0"],series:["Direct harmful","Style-transformed harmful"],image:"assets/expplan/F2_exit_depth.png"})}
      </section>

      ${resultTable({id:"TABLE EXAMPLE · T1",title:"Main safety–utility comparison",headers:["Method / condition","AdvBench DSR ↑ (%, 95% CI)","HarmBench DSR ↑ (%, 95% CI)","XSTest false refusal ↓ (%, 95% CI)","Just-Eval retention ↑ (%, 95% CI)"],rows:methods,note:"每一行都在统一 decoding 与 judge contract 下本地重跑；不复用论文中的已发表数字。"})}

      <section class="plain-section claim-contract">
        <p class="artifact-kicker">2.4 · CLAIM–FALSIFIER–EVIDENCE</p><h4>三个主张都预先写明失败条件</h4>
        <div class="claim-rows"><div><b>C1</b><p>匹配意图的风格变换产生可复现的最早 safety-tube exit。</p><span>若 exit depth 跨 paraphrase、seed 或 model 不稳定，则失败。</span></div><div><b>C2</b><p>只修 first-exit layer 足以恢复下游安全几何并降低 harmful compliance。</p><span>若随机层、ABD 层、后续层或重复修复并列或更优，则失败。</span></div><div><b>C3</b><p>一次修复改善 safety–utility–cost frontier。</p><span>若 DSR 增益必须以更差的 XSTest、Just-Eval 或 latency 换取，则失败。</span></div></div>
      </section>

      <section class="plain-section implementation-section">
        <p class="artifact-kicker">2.5 · IMPLEMENTATION PLAN</p><h4>所有方法接入同一个本地框架</h4>
        <div class="table-scroll"><table class="implementation-table"><thead><tr><th>Method</th><th>How it is implemented</th></tr></thead><tbody><tr><th>No Defense</th><td>共享 generation path，关闭全部 defense。</td></tr><tr><th>ABD</th><td>本地实现 safety-boundary estimation、penalty 与 layer selection，复用统一 hooks。</td></tr><tr><th>RTV</th><td>本地实现 refusal-direction fingerprints 与 multi-layer Mahalanobis trajectory scoring。</td></tr><tr><th>JBShield</th><td>通过 local adapter 接入官方 concept extraction、scoring、mitigation 与 mixed-input gating；<a href="https://github.com/NISPLab/JBShield" target="_blank" rel="noreferrer">Official GitHub</a>。</td></tr><tr><th>TrajGuard</th><td>本地实现 sliding-window hidden-state aggregation、persistence thresholding 与 semantic adjudication。</td></tr><tr><th>Our method — First-Divergence Repair</th><td>在同一 model、trace、generation、evaluator 接口上实现 first-exit localization、one-shot repair 与 downstream recovery。</td></tr></tbody></table></div>
      </section>

      <section class="plain-section">
        <p class="artifact-kicker">2.6 · BUDGET AND DECISION CRITERIA</p><h4>预算与停止条件在实验前冻结</h4>
        <p>预算为 4×A100、约 428 GPU-hours；先验证首次偏离现象，再冻结 threshold 与 repair strength。最终数据禁止继续调参，任一 decisive falsifier 成立时收窄或放弃对应 claim。</p>
      </section>

      <section class="approval-line"><strong>3 · APPROVAL</strong><span>APPROVED · 2026-08-09</span><p>实验开始前冻结 7 个 claim-bearing floats、144 个数字目标、预算与 decision criteria；结果不支持时按 falsifier 收窄或放弃主张。</p></section>
    </article>`;
};

const runParts = [
  ["P1", "Instrumentation", [["✅", "G1.1", "最小可复现轨迹通路", "共享 trace / evaluator 基础设施"]]],
  ["P2", "Problem-Existence Validation", [["✅", "G2.1", "AdvBench 首次偏离探针", "F2A · exit depth"],["→", "G2.2", "HarmBench 成功/失败退出集中度", "F2B · concentration"]]],
  ["P3", "Method Feasibility", [["○", "G3.1", "单模型单点修复可行性", "无直接图表"]]],
  ["P4", "Development Tuning", [["○", "G4.1", "冻结 safety-tube threshold", "无直接图表"],["○", "G4.2", "冻结最小有效 repair strength", "无直接图表"]]],
  ["P5", "Primary Evidence", [["○", "G5.1", "三模型、五基线统一协议主比较", "T1"]]],
  ["P6", "Causal Controls and Ablation", [["○", "G6.1", "修复层偏移因果曲线", "F3A"],["○", "G6.2", "下游轨迹恢复检验", "F3B"],["○", "G6.3", "唯一性消融矩阵", "T2"]]],
  ["P7", "Robustness and Sensitivity", [["○", "G7.1", "修复强度鲁棒性", "F4"]]],
  ["P8", "Cost and Failure Analysis", [["○", "G8.1", "延迟、显存与未恢复案例", "T3"]]]
];

const goalDetail = gid => ({
  "G1.1": "已完成：一个模型与极小输入切片的 layer×token trace、judge、重复运行和 provenance 路径均通过验证。",
  "G2.1": "已完成：F2A 的 16 个 Demo 数字已由同一源表生成下方曲线；数字悬停可检查取得过程。",
  "G2.2": "当前唯一解锁项：完成后命令与箭头继续向下移动，G2.1 的结果仍保留可追溯。"
}[gid] || "前置 Gate 完成后才解锁；每个原子结果先落盘并写 ledger，再计算聚合值。");

const goalHierarchy = () => `<section class="goal-hierarchy"><p class="artifact-kicker">8 PARTS · 12 GOALS · 2 COMPLETE · ONE UNLOCKED</p>${runParts.map(([pid,title,goals]) => `<div class="part-row"><h4><span>${pid}</span>${title}</h4>${goals.map(([mark,gid,name,dest]) => `<div class="expanded-goal"><b>${mark}</b><strong>${gid} · ${name}</strong><span>对应图表：${dest}</span><p>${goalDetail(gid)}</p></div>`).join("")}</div>`).join("")}</section>`;

const completedF2Rows = [
  ["0.00", 0.04, 0.06], ["0.14", 0.05, 0.11], ["0.29", 0.08, 0.26], ["0.43", 0.13, 0.47],
  ["0.57", 0.19, 0.68], ["0.71", 0.25, 0.79], ["0.86", 0.29, 0.84], ["1.00", 0.32, 0.86]
];

const provenanceNumber = (value, depth, series) => `<span class="provenance-number" tabindex="0">${value.toFixed(2)}<span class="provenance-tooltip" role="tooltip"><b>DEMO VALUE · NOT A SCIENTIFIC RESULT</b><span><strong>Goal</strong> G2.1</span><span><strong>Slice</strong> depth=${depth} · ${series}</span><span><strong>Raw</strong> results/demo/g2_1/raw_trace.jsonl</span><span><strong>Filter</strong> approved model + matched intent/style IDs</span><span><strong>Formula</strong> sum(tube_exit) / valid records = ${value.toFixed(4)}</span><span><strong>Command</strong> python -m code.first_divergence.acquire --goal G2.1</span><span><strong>Check</strong> ledger schema, config digest, rerun match, source path reopen</span></span></span>`;

const completedF2Chart = () => {
  const points = column => completedF2Rows.map((row, index) => `${54 + index * 61},${202 - row[column] * 170}`).join(" ");
  return `<figure class="completed-chart"><svg viewBox="0 0 520 245" role="img" aria-label="Demo F2A safety tube exit rate chart"><g class="chart-grid"><line x1="54" y1="32" x2="481" y2="32"/><line x1="54" y1="117" x2="481" y2="117"/><line x1="54" y1="202" x2="481" y2="202"/></g><g class="chart-axis"><line x1="54" y1="25" x2="54" y2="202"/><line x1="54" y1="202" x2="486" y2="202"/></g><g class="chart-labels"><text x="18" y="36">1.0</text><text x="18" y="121">0.5</text><text x="18" y="206">0.0</text><text x="51" y="224">0.0</text><text x="256" y="224">depth</text><text x="466" y="224">1.0</text></g><polyline class="series-direct" points="${points(1)}"/><polyline class="series-style" points="${points(2)}"/>${completedF2Rows.map((row,index) => `<circle class="point-direct" cx="${54 + index * 61}" cy="${202 - row[1] * 170}" r="3.5"/><circle class="point-style" cx="${54 + index * 61}" cy="${202 - row[2] * 170}" r="3.5"/>`).join("")}<g class="chart-legend"><line x1="286" y1="18" x2="309" y2="18" class="series-direct"/><text x="315" y="22">Direct harmful</text><line x1="397" y1="18" x2="420" y2="18" class="series-style"/><text x="426" y="22">Styled</text></g></svg><figcaption>由左侧同一张数字源表生成；没有独立的 plot-only 数据源。</figcaption></figure>`;
};

const resultProvenanceDemo = () => `
  <section class="evidence-artifact completed-result"><p class="artifact-kicker">05_EXP_RESULT · FIRST ARTIFACT COMPLETE · DEMO DATA</p><h4>F2A · Safety-tube exit rate by normalized depth</h4>
    <p>这里演示完成第一个结果 Goal 后的状态。数字是 UI 示例，不是本项目的科学结果；表和图使用同一组值。</p>
    <div class="provenance-flow"><span>raw JSONL</span><i>→</i><span>已验证结果记录</span><i>→</i><span>验证公式</span><i>→</i><span>填入源数据表</span><i>→</i><span>生成图</span></div>
    <div class="completed-result-grid"><div class="table-scroll"><table class="result-shell source-table completed-source"><thead><tr><th>Normalized depth</th><th>Direct harmful</th><th>Style-transformed harmful</th></tr></thead><tbody>${completedF2Rows.map(([depth,direct,styled]) => `<tr><th>${depth}</th><td>${provenanceNumber(direct,depth,"direct harmful")}</td><td>${provenanceNumber(styled,depth,"style-transformed harmful")}</td></tr>`).join("")}</tbody></table><p class="hover-instruction">鼠标停在任一数字上，或用键盘聚焦，即可查看 raw path、筛选、公式、命令与验证过程。</p></div>${completedF2Chart()}</div>
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
    compare: null,
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 04 · EXPPLAN</p><h3>Projected Paper 先于实验任务</h3><p>以下内容与实际 reports/03_EXPERIMENT_PLAN.html 的结构对齐，但首页只举两个代表性例子：F2A 图及其待填源表、T1 主结果表。</p></div><span class="status-pill">APPROVED</span></div>
      ${commandStrip("生成实验设计与待填图表", "$expplan")}
      ${experimentPlanDemo()}`
  },
  {
    id: "runplan", short: "实验执行", path: "run-plan", title: "一次执行一个 Goal，完成即填表并整理",
    compare: ["强调连续自主探索与整体吞吐", "适合可自动判分的大规模搜索", "每个 Goal 落盘、验证、填表、打勾，再解锁下一项"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 05 · RUNPLAN + /GOAL</p><h3>完成一项，状态与命令就向下移动</h3><p>Demo 展示首个结果图 F2A 已完成：G1.1 与 G2.1 保留 ✅，当前唯一解锁项移动到 G2.2；16 个示例数字都能悬停查看 provenance。</p></div><span class="status-pill">G2.2 UNLOCKED</span></div>
      ${commandStrip("执行当前唯一 Goal G2.2", "/goal Complete G2.2: acquire and verify the HarmBench first-exit concentration panel")}
      ${reportDocument("runplan")}
      ${goalHierarchy()}
      ${reportDocument("results", "EXPERIMENT RESULTS · FIRST ARTIFACT COMPLETE · DEMO")}
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
    const response = await fetch("report-structures.json?v=20260814-real-provenance");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    reportStructures = await response.json();
    state.stage = stageIndexFromLocation();
    renderStage();
  } catch (error) {
    content.innerHTML = `<div class="demo-load-error"><strong>Demo structure failed to load.</strong><span>${String(error)}</span></div>`;
  }
}

initializeDemo();
