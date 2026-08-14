const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));

const commandStrip = (title, command, detail = "在终端中的 Coding Agent 执行；网页读取生成后的项目文件。") => `
  <div class="command-card">
    <div><span>CODING AGENT · TERMINAL</span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></div>
    <code>${escapeHtml(command)}</code><button type="button" data-copy="${escapeHtml(command)}">复制命令</button>
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

let runPlanDemoState = null;

const runStatusMark = status => ({completed:"✅",running:"▶",proposed:"→",locked:"○",pending:"○",blocked:"⚠",invalidated:"⚠"}[status] || "○");

const currentGoalPanel = goal => `<div class="demo-current-goal" data-demo-current-goal="${escapeHtml(goal.id)}">
  <p class="artifact-kicker">CURRENT GOAL · ${escapeHtml(goal.id)}</p>
  <h5>${escapeHtml(goal.title)}</h5>
  <pre>${escapeHtml(goal.goal_command)}</pre>
  <button type="button" data-copy="${escapeHtml(goal.goal_command)}">复制 /goal</button>
  <dl><dt>Outputs</dt><dd>${(goal.outputs || []).map(escapeHtml).join(" · ")}</dd><dt>Resources</dt><dd>${escapeHtml(goal.budget)}</dd><dt>Completion</dt><dd>${escapeHtml(goal.completion_check)}</dd></dl>
</div>`;

const goalHierarchy = () => {
  if (!runPlanDemoState) return `<section class="goal-hierarchy"><p>Run Plan snapshot unavailable.</p></section>`;
  const goals = Object.fromEntries(runPlanDemoState.goals.map(goal => [goal.id, goal]));
  const currentId = runPlanDemoState.active_goal || runPlanDemoState.proposed_goal_id;
  const completed = runPlanDemoState.goals.filter(goal => goal.status === "completed").length;
  const representativeGoalIds = [currentId, "G2.1", "G5.1"].filter((id, index, ids) => id && goals[id] && ids.indexOf(id) === index);
  const representativeParts = representativeGoalIds.map(goalId => {
    const goal = goals[goalId];
    const part = runPlanDemoState.parts.find(item => item.id === goal.part_id);
    return {part, goal};
  });
  return `<section class="goal-hierarchy"><p class="artifact-kicker">SYNCED FROM ${escapeHtml(runPlanDemoState.source)} · CURRENT STATE + 3 REPRESENTATIVE GOALS</p><p class="runplan-demo-note">真实报告仍保存 ${runPlanDemoState.parts.length} Parts / ${runPlanDemoState.goals.length} Goals 的完整计划；Demo 只展示当前执行、下一阶段和主结果三种代表状态。G2.1 同时演示 Goal 完成后，图表如何直接出现在原卡片内。</p>${representativeParts.map(({part, goal}) => {
    const destination = goal.artifact_ids?.length ? goal.artifact_ids.join("、") : "无直接图表";
    const completedExample = goal.id === "G2.1";
    return `<div class="part-row"><h4><span>${escapeHtml(part.id)}</span>${escapeHtml(part.title)}</h4><p class="part-decision">${escapeHtml(part.decision)}</p><div class="expanded-goal ${completedExample ? "demo-completed-goal" : ""}"><b>${completedExample ? "✅" : runStatusMark(goal.status)}</b><strong>${escapeHtml(goal.id)} · ${escapeHtml(goal.title)}${completedExample ? '<small>模拟实验已完成 · DEMO DATA</small>' : ""}</strong><span>对应图表：${escapeHtml(destination)}</span><p>${escapeHtml(goal.visible_work)} ${escapeHtml(goal.visible_evidence)} 完成检查：${escapeHtml(goal.completion_check)}</p>${goal.id === currentId ? currentGoalPanel(goal) : ""}${completedExample ? resultProvenanceDemo() : ""}</div></div>`;
  }).join("")}</section>`;
};

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
  <section class="evidence-artifact completed-result future-result-example"><p class="artifact-kicker">已完成 Goal 的图表 · DEMO DATA</p><h4>F2A · Safety-tube exit rate by normalized depth</h4>
    <div class="simulated-run-summary"><strong>✅ 模拟执行完成</strong><span>16 / 16 source cells verified</span><span>raw JSONL reopen PASS</span><span>plot regenerated</span></div>
    <p>这组演示数据直接放在 G2.1 卡片内，展示该 Goal 完成后的“源数据表＋图”；它不是当前项目结果，也不是科学结论。</p>
    <div class="provenance-flow"><span>raw JSONL</span><i>→</i><span>已验证结果记录</span><i>→</i><span>验证公式</span><i>→</i><span>填入源数据表</span><i>→</i><span>生成图</span></div>
    <div class="completed-result-grid"><div class="table-scroll"><table class="result-shell source-table completed-source"><thead><tr><th>Normalized depth</th><th>Direct harmful</th><th>Style-transformed harmful</th></tr></thead><tbody>${completedF2Rows.map(([depth,direct,styled]) => `<tr><th>${depth}</th><td>${provenanceNumber(direct,depth,"direct harmful")}</td><td>${provenanceNumber(styled,depth,"style-transformed harmful")}</td></tr>`).join("")}</tbody></table><p class="hover-instruction">鼠标停在任一数字上，或用键盘聚焦，即可查看 raw path、筛选、公式、命令与验证过程。</p></div>${completedF2Chart()}</div>
  </section>`;

const paperStudioScreenshots = () => `<section class="paper-studio-screenshots">
  <p class="artifact-kicker">REAL PAPER STUDIO SCREENSHOTS · CAPTURED FROM THE LOCAL APP</p>
  <h4>真实界面，不在 Demo 中重画</h4>
  <p>以下三张图直接截取自仓库中的 Paper Studio：同一个固定应用根据当前视图显示正文、图片和表格工作台；正文截图右侧展示真实编译后的 Live PDF。</p>
  ${[
    ["writing.png", "正文写作", "逐段 candidate、修改意见、Accept → LaTeX 与右侧真实 Live PDF。", true],
    ["figures.png", "图片工作台", "真实 GPT Image 已生成并显示；后续继续重建为可编辑 PPT/PDF。", false],
    ["tables.png", "表格工作台", "真实 DEMO DATA 已通过 LaTeX 编译成表格预览，并保留可编辑源码与正文位置。", false],
  ].map(([file, title, caption, isWriting]) => `<figure><img src="assets/paper-studio/${file}?v=20260814-real-artifacts-v2" alt="Paper Studio ${title}真实截图" loading="lazy"><figcaption><div><strong>${title}</strong><span>${caption}</span></div>${isWriting ? `<aside class="writing-api-note"><b>正文由 LLM API 写作</b><span>不是 Code Agent 生成正文</span></aside>` : ""}</figcaption></figure>`).join("")}
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
    render: () => {
      const currentId = runPlanDemoState?.active_goal || runPlanDemoState?.proposed_goal_id || "NONE";
      return `
      <div class="stage-head"><div><p class="eyebrow">STEP 05 · RUNPLAN + /GOAL</p><h3>执行进度和已完成图表都在 04 Run Plan</h3><p>层级、Current Goal 和真实完成状态来自 reports/04_RUN_PLAN.html；Demo 另外在 G2.1 卡片内明确标注一组完成后的交互示例。05 只保留完整 provenance，不再单独展示。</p></div><span class="status-pill">${escapeHtml(currentId)} ${runPlanDemoState?.active_goal ? "RUNNING" : "UNLOCKED"}</span></div>
      ${reportDocument("runplan")}
      ${goalHierarchy()}`;
    }
  },
  {
    id: "paper", short: "论文写作", path: "paper-writing", title: "逐段写作、实时编译、图表可编辑",
    compare: ["倾向批量生成 Markdown 或 LaTeX 草稿", "适合快速获得整体版本", "正文调用 LLM API（不是 Code Agent）逐段生成；确认接受后才写入 LaTeX 并实时编译"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">PAPERWRITE → PAPER STUDIO</p><h3>直接展示真实 Paper Studio 截图</h3><p>不在 Demo 中自创写作界面或 Tab。下面的正文、图片和表格三张截图全部来自仓库中实际运行的 Paper Studio。</p></div><span class="status-pill">REAL SCREENSHOTS</span></div>
      ${commandStrip("结果完成后启动论文写作", "$paperwrite", "Paperwrite 准备项目数据并打开固定 Paper Studio；LLM API 负责流畅正文，本地 Agent 负责可复现图表与排版。")}
      ${paperStudioScreenshots()}
      <section class="plain-section"><p class="artifact-kicker">真实工作方式</p><h4>候选不会自动写入论文</h4><ul><li>正文：GPT 生成可编辑 candidate，研究者点击 Accept → LaTeX 后才编译。</li><li>图片：实验结果驱动矢量图；机制图同时保留 GPT 构图参考和可编辑 PPT/PDF。</li><li>表格：只允许 verified ledger 数字进入可编辑 LaTeX，确认后刷新右侧 PDF。</li></ul></section>`
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
  const value = button.dataset.copy || "";
  try {
    if (!navigator.clipboard || !window.isSecureContext) throw new Error("clipboard API unavailable");
    await navigator.clipboard.writeText(value);
    button.textContent = "已复制 ✓";
  } catch {
    const area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    area.style.top = "0";
    document.body.appendChild(area);
    area.focus();
    area.select();
    area.setSelectionRange(0, value.length);
    let copied = false;
    try { copied = document.execCommand("copy"); } catch {}
    area.remove();
    button.textContent = copied ? "已复制 ✓" : "请选中命令复制";
  }
  setTimeout(() => { button.textContent = original; }, 1400);
});

async function initializeDemo() {
  try {
    const [structureResponse, runPlanResponse] = await Promise.all([
      fetch("report-structures.json?v=20260814-runplan-paperstudio"),
      fetch("runplan-state.json?v=20260814-runplan-paperstudio")
    ]);
    if (!structureResponse.ok) throw new Error(`report structures HTTP ${structureResponse.status}`);
    if (!runPlanResponse.ok) throw new Error(`run plan snapshot HTTP ${runPlanResponse.status}`);
    reportStructures = await structureResponse.json();
    runPlanDemoState = await runPlanResponse.json();
    state.stage = stageIndexFromLocation();
    renderStage();
  } catch (error) {
    content.innerHTML = `<div class="demo-load-error"><strong>Demo structure failed to load.</strong><span>${String(error)}</span></div>`;
  }
}

initializeDemo();
