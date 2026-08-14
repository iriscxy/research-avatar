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

      <section class="plain-section projected-abstract">
        <p class="artifact-kicker">2.1 · PROJECTED TITLE AND ABSTRACT</p>
        <h4>First-Divergence Repair: Causal Single-Layer Recovery from Style-Induced Jailbreaks</h4>
        <p>We test whether intent-preserving style transformations cause a reproducible first exit from a model's safety trajectory and whether repairing only that layer restores downstream safety. A unified white-box framework compares five rerun representation defenses across AdvBench, HarmBench, XSTest, and Just-Eval. The claim survives only if first-exit repair uniquely beats wrong-layer and repeated-repair controls while improving the safety–utility–cost frontier.</p>
      </section>

      <section class="plain-section setup-section">
        <p class="artifact-kicker">5.1 · SETUP</p><h4>统一模型、数据、基线与评测通路</h4>
        <dl class="setup-grid"><dt>Models</dt><dd>Llama-3.1-8B-Instruct · Mistral-7B-Instruct-v0.3 · Qwen2.5-7B-Instruct</dd><dt>Harmful</dt><dd>AdvBench 50-behavior subset · HarmBench 1.0</dd><dt>Benign / quality</dt><dd>XSTest · Just-Eval · Alpaca benign controls</dd><dt>Safety judge</dt><dd>SORRY-Bench evaluator</dd><dt>Baselines</dt><dd>No Defense · ABD · RTV · JBShield · TrajGuard</dd><dt>Metrics</dt><dd>First-exit stability · Downstream trajectory recovery · DSR · XSTest false refusal · Just-Eval retention · latency overhead</dd></dl>
      </section>

      <section class="plain-section claim-contract">
        <p class="artifact-kicker">2.4 · CLAIM–FALSIFIER–EVIDENCE</p><h4>三个主张都预先写明失败条件</h4>
        <div class="claim-rows"><div><b>C1</b><p>匹配意图的风格变换产生可复现的最早 safety-tube exit。</p><span>若 exit depth 跨 paraphrase、seed 或 model 不稳定，则失败。</span></div><div><b>C2</b><p>只修 first-exit layer 足以恢复下游安全几何并降低 harmful compliance。</p><span>若随机层、ABD 层、后续层或重复修复并列或更优，则失败。</span></div><div><b>C3</b><p>一次修复改善 safety–utility–cost frontier。</p><span>若 DSR 增益必须以更差的 XSTest、Just-Eval 或 latency 换取，则失败。</span></div></div>
      </section>

      <section class="evidence-artifact motivation-artifact">
        <p class="artifact-kicker">F1 · MOTIVATION · NON-DATA-DRIVEN</p><h4>Same harmful intent, different style, first divergent depth highlighted</h4>
        <div class="motivation-figure"><div class="intent-node">Same harmful intent</div><div class="style-path direct"><strong>Direct harmful</strong><span>L0</span><i></i><span>L1</span><i></i><span>L2</span><i></i><span>L3</span></div><div class="style-path transformed"><strong>Style-transformed</strong><span>L0</span><i></i><span>L1</span><i class="exit"></i><span class="exit-label">FIRST EXIT · L2</span><i></i><span>L3</span></div><div class="repair-node">one-shot repair at first exit → downstream recovery?</div></div>
      </section>

      <section class="evidence-artifact">
        <p class="artifact-kicker">F2 · CLAIM C1 · TWO PANELS</p><h4>Where the safety trajectory first leaves its tube</h4>
        ${projectedPanel({title:"F2A · Where safety trajectories leave the tube",dataset:"AdvBench 50 + matched-style counterfactuals",metric:"Safety-tube exit rate; x = normalized transformer depth; y = exit rate",fields:"model_id · intent_id · style_id · layer_id · tube_exit",xLabel:"Normalized transformer depth",xs:["0.0","0.14","0.29","0.43","0.57","0.71","0.86","1.0"],series:["Direct harmful","Style-transformed harmful"],image:"assets/expplan/F2_exit_depth.png"})}
        ${projectedPanel({title:"F2B · First exits concentrate for successful jailbreaks",dataset:"HarmBench 1.0 + matched-style counterfactuals",metric:"First-exit probability; x = normalized transformer depth; y = probability",fields:"model_id · intent_id · style_id · layer_id · first_exit_layer · judge_label",xLabel:"Normalized transformer depth",xs:["0.0","0.14","0.29","0.43","0.57","0.71","0.86","1.0"],series:["Successful jailbreak","Unsuccessful jailbreak"],image:"assets/expplan/F2_first_exit_concentration.png"})}
      </section>

      <section class="evidence-artifact">
        <p class="artifact-kicker">F3 · CLAIM C2 · TWO PANELS</p><h4>Does one repair restore the downstream trajectory?</h4>
        ${projectedPanel({title:"F3A · Only the first-exit layer should recover safety",dataset:"AdvBench 50 + XSTest",metric:"Normalized safety recovery and benign utility retention",fields:"model_id · intent_id · first_exit_layer · repair_layer · judge_label · benign_refusal",xLabel:"Repair-layer offset",xs:["-3","-2","-1","0","1","2","3"],series:["Safety recovery","Benign utility retention"],image:"assets/expplan/F3_repair_offset.png"})}
        ${projectedPanel({title:"F3B · One repair should restore downstream geometry",dataset:"HarmBench 1.0 + matched-style counterfactuals",metric:"Safe-reference trajectory cosine similarity",fields:"model_id · intent_id · layer_id · repair_condition · safe_reference_similarity",xLabel:"Depth after first exit",xs:["0","1","2","3","4","5","6"],series:["No repair","First-exit repair","Wrong-layer repair"],image:"assets/expplan/F3_downstream_recovery.png"})}
      </section>

      ${resultTable({id:"T1",title:"Main safety–utility comparison",headers:["Method / condition","AdvBench DSR ↑ (%, 95% CI)","HarmBench DSR ↑ (%, 95% CI)","XSTest false refusal ↓ (%, 95% CI)","Just-Eval retention ↑ (%, 95% CI)"],rows:methods,note:"每一行都在统一 decoding 与 judge contract 下本地重跑；不复用论文中的已发表数字。"})}
      ${resultTable({id:"T2",title:"Single-site causal ablation matrix",headers:["Method / condition","First-exit stability ↑","Downstream recovery ↑","HarmBench DSR ↑","XSTest false refusal ↓"],rows:["Full first-exit repair","Random layer","ABD-selected layer","Latest-exit layer","Repeated multi-layer repair"],note:"决定性比较是完整 first-exit repair 对随机、ABD-selected、latest-exit 与 repeated-repair controls。"})}

      <section class="evidence-artifact">
        <p class="artifact-kicker">F4 · CLAIM C3 · SENSITIVITY</p><h4>Repair-strength safety–utility sensitivity</h4>
        ${projectedPanel({title:"F4 · Safety–utility sensitivity to repair strength",dataset:"AdvBench 50 + HarmBench 1.0 + XSTest",metric:"DSR, false-refusal complement, and Just-Eval retention",fields:"model_id · repair_strength · judge_label · benign_refusal · just_eval_score",xLabel:"Repair strength",xs:["0.25","0.5","0.75","1.0","1.25"],series:["Defense success","1 − false refusal","Just-Eval retention"],image:"assets/expplan/F4_repair_strength.png"})}
      </section>

      ${resultTable({id:"T3",title:"Efficiency and failure surface",headers:["Method / condition","Latency overhead ↓ (ms/query)","Peak memory overhead ↓ (GiB)","Unrecovered cases ↓ (%, 95% CI)"],rows:methods,note:"Failure cases 在 metric 冻结后分类；不把定性原因转换成虚构分数。"})}

      <section class="plain-section implementation-section">
        <p class="artifact-kicker">2.5 · IMPLEMENTATION PLAN</p><h4>所有方法接入同一个本地框架</h4>
        <div class="table-scroll"><table class="implementation-table"><thead><tr><th>Method</th><th>How it is implemented</th></tr></thead><tbody><tr><th>No Defense</th><td>共享 generation path，关闭全部 defense。</td></tr><tr><th>ABD</th><td>本地实现 safety-boundary estimation、penalty 与 layer selection，复用统一 hooks。</td></tr><tr><th>RTV</th><td>本地实现 refusal-direction fingerprints 与 multi-layer Mahalanobis trajectory scoring。</td></tr><tr><th>JBShield</th><td>通过 local adapter 接入官方 concept extraction、scoring、mitigation 与 mixed-input gating；<a href="https://github.com/NISPLab/JBShield" target="_blank" rel="noreferrer">Official GitHub</a>。</td></tr><tr><th>TrajGuard</th><td>本地实现 sliding-window hidden-state aggregation、persistence thresholding 与 semantic adjudication。</td></tr><tr><th>Our method — First-Divergence Repair</th><td>在同一 model、trace、generation、evaluator 接口上实现 first-exit localization、one-shot repair 与 downstream recovery。</td></tr></tbody></table></div>
      </section>

      <section class="approval-line"><strong>3 · APPROVAL</strong><span>APPROVED · 2026-08-09</span><p>实验开始前冻结 7 个 claim-bearing floats、144 个数字目标、预算与 decision criteria；结果不支持时按 falsifier 收窄或放弃主张。</p></section>
    </article>`;
};

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
    compare: null,
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 04 · EXPPLAN</p><h3>Projected Paper 先于实验任务</h3><p>以下内容与实际 reports/03_EXPERIMENT_PLAN.html 对齐：完整展示 4 图、3 表、相邻图源数据表、基线实现和预注册 falsifier。</p></div><span class="status-pill">APPROVED</span></div>
      ${commandStrip("生成实验设计与待填图表", "$expplan")}
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
    const response = await fetch("report-structures.json?v=20260814-expplan-parity");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    reportStructures = await response.json();
    state.stage = stageIndexFromLocation();
    renderStage();
  } catch (error) {
    content.innerHTML = `<div class="demo-load-error"><strong>Demo structure failed to load.</strong><span>${String(error)}</span></div>`;
  }
}

initializeDemo();
