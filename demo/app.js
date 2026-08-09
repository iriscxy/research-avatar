const commandCard = (title, command, detail = "在终端中的 Coding Agent 执行；网页读取生成后的项目文件。") => `
  <div class="command-card">
    <div><span>CODING AGENT · TERMINAL</span><strong>${title}</strong><small>${detail}</small></div>
    <code>${command}</code><button type="button" data-copy="${command}">复制命令</button>
  </div>`;

const stages = [
  {
    id: "profile", short: "研究画像", label: "Researcher Profile", path: "profile",
    title: "先理解研究者，再开始研究",
    summary: ["终端生成", "PROFILE.md", "Writing Style", "Experiment Habits"],
    compare: ["以任务上下文和通用配置为主要起点", "适合快速进入自动探索", "先建立可检查的个性化依据"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 01 · PROFILECONSTRUCT</p><h3>研究画像由终端生成，网页负责阅读</h3><p>先手动下载完整 Scholar 主页；这里没有上传 HTML 或在网页运行 Skill 的假入口。</p></div><span class="status-pill">COMPLETE</span></div>
      ${commandCard("读取本地 Scholar HTML 并建立画像", "$profileconstruct 使用 ~/Downloads/scholar_profile.html")}
      <div class="workspace-grid wide-left">
        <div class="panel"><div class="panel-head"><strong>PROFILE.md</strong><span>canonical artifact</span></div><div class="profile-output"><div class="mini-card"><span>IDENTITY</span><strong>Trustworthy AI</strong><small>LLM safety · representation analysis</small></div><div class="mini-card"><span>LINEAGE</span><strong>Defense → Mechanism</strong><small>从现象防御走向内部机制</small></div><div class="mini-card"><span>EXPERIMENT</span><strong>4× A100</strong><small>缓存中间结果 · 避免重复调用</small></div><div class="mini-card"><span>WORKFLOW</span><strong>Evidence first</strong><small>关键决定由研究者确认</small></div></div></div>
        <div class="panel"><div class="panel-head"><strong>PROFILE.md · Writing Style</strong><span>same profile</span></div><div class="paper-outline"><div class="outline-section"><strong>Abstract</strong><span>problem → gap → method → evidence</span></div><div class="outline-section"><strong>Claims</strong><span>谨慎措辞，结果先于结论</span></div><div class="outline-section"><strong>Structure</strong><span>会议匹配的章节与图表习惯</span></div><div class="outline-section"><strong>Usage</strong><span>画像网页完整展示；后续流程读取同一来源</span></div></div></div>
      </div>`
  },
  {
    id: "literature", short: "文献 Survey", label: "Literature Survey", path: "literature",
    title: "先建立可核验的文献地图",
    summary: ["多角度检索", "逐篇核验", "Taxonomy", "趋势与空白"], compare: null,
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 02 · RESEARCHLIT</p><h3>检索、核验并组织研究版图</h3><p>Survey 与 Idea 分开；每篇工作都能回到实际打开的来源。</p></div><span class="status-pill">54 VERIFIED</span></div>
      ${commandCard("生成独立文献 Survey", "$researchlit stylish jailbreak")}
      <div class="workspace-grid">
        <div class="panel"><div class="panel-head"><strong>Literature landscape</strong><span>01_LIT_SURVEY.html</span></div><div class="landscape"><div class="paper-row"><span>25</span><div><strong>Style & register attacks</strong><small>poetry · persona · vernacular</small></div><b>CROWDED</b></div><div class="paper-row"><span>18</span><div><strong>Mechanism analysis</strong><small>representation · attention</small></div><b>EMERGING</b></div><div class="paper-row"><span>11</span><div><strong>Intent-invariant defense</strong><small>utility-preserving controls</small></div><b>OPEN GAP</b></div></div></div>
        <div class="panel"><div class="panel-head"><strong>Survey synthesis</strong><span>fixed report slots</span></div><div class="paper-outline"><div class="outline-section"><strong>Taxonomy</strong><span>persona / narrative / register / encoding</span></div><div class="outline-section"><strong>Landscape</strong><span>按方法、数据与证据类型比较</span></div><div class="outline-section"><strong>Debate</strong><span>纯 style 还是语义与语用变化</span></div><div class="outline-section"><strong>Trends / gaps</strong><span>缺少跨模型的因果机制证据</span></div><div class="outline-section"><strong>References</strong><span>逐篇核验并链接正式来源</span></div></div></div>
      </div>`
  },
  {
    id: "ideas", short: "Idea 选择", label: "Idea Selection", path: "ideas",
    title: "候选先过门槛，再由研究者选择",
    summary: ["多个 Candidate", "最近工作核对", "资格门槛", "网页确认"],
    compare: ["通常用排序快速呈现候选方向", "研究者再判断价值与新颖性", "把新颖性与可证伪性设为独立硬门槛"],
    render: state => `
      <div class="stage-head"><div><p class="eyebrow">STEP 03 · IDEAGEN</p><h3>终端生成候选，网页完成研究者选择</h3><p>真实界面会把确认写回 02_IDEA_REPORT.html，供 $expplan 读取。</p></div><span class="status-pill">${state.ideaConfirmed ? "HUMAN PICK RECORDED" : "HUMAN PICK"}</span></div>
      ${commandCard("生成并核验多个 Candidate Idea", "$ideagen")}
      <div class="workspace-grid">
        <div class="panel"><div class="panel-head"><strong>Candidate ideas</strong><span>点击选择</span></div><div class="idea-list">
          <button type="button" class="idea ${state.selectedIdea === "I1" ? "selected" : ""}" data-action="select-idea" data-idea="I1" data-id="I1"><strong>Style-preserving canonicalizer</strong><small>保留正常创作能力，同时恢复 intent safety</small></button>
          <button type="button" class="idea ${state.selectedIdea === "I2" ? "selected" : ""}" data-action="select-idea" data-idea="I2" data-id="I2"><strong>Matched causal benchmark</strong><small>严格控制长度、语义、turn 与 style family</small></button>
          <button type="button" class="idea ${state.selectedIdea === "I3" ? "selected" : ""}" data-action="select-idea" data-idea="I3" data-id="I3"><strong>Representation falsification test</strong><small>一个核心机制与明确的失败条件</small></button>
        </div><label class="idea-reason"><span>选择理由（可选）</span><textarea rows="2" placeholder="为什么它最值得进入实验规划？"></textarea></label><button class="confirm-action" type="button" data-action="confirm-idea">${state.ideaConfirmed ? `✓ ${state.selectedIdea} 已写入 Idea Report` : `确认 ${state.selectedIdea} →`}</button></div>
        <div class="panel"><div class="panel-head"><strong>${state.selectedIdea} · Candidate detail</strong><span>fixed card fields</span></div><div class="paper-outline"><div class="outline-section"><strong>Novelty</strong><span>与最近工作存在可验证的机制差异</span></div><div class="outline-section"><strong>Mechanism</strong><span>一个不可拆散的中心机制</span></div><div class="outline-section"><strong>Falsifier</strong><span>跨 style family 不成立则收窄 claim</span></div><div class="outline-section"><strong>Objection</strong><span>提升可能来自语义变化而非 style</span></div></div><div class="approval-state ${state.ideaConfirmed ? "approved" : ""}">${state.ideaConfirmed ? "人工选择已确认；下一步可生成实验设计。" : "Skill 只推荐，不替研究者做最终选择。"}</div></div>
      </div>`
  },
  {
    id: "expplan", short: "实验设计", label: "Projected Paper", path: "experiment-plan",
    title: "先固定证据空位，再反推实验",
    summary: ["预期摘要", "论文骨架", "Claims / falsifiers", "网页批准"],
    compare: ["从任务目标和实验空间开始探索", "论文结构通常在结果后整理", "先固定图表与证据空位，避免漏证据和事后叙事"],
    render: state => `
      <div class="stage-head"><div><p class="eyebrow">STEP 04 · EXPPLAN</p><h3>Projected Paper 先于实验任务</h3><p>逐段骨架、claim、falsifier、baseline、数据集、metric、图表预算与实现来源均在批准前审阅。</p></div><span class="status-pill">${state.expApproved ? "APPROVED" : "APPROVAL REQUIRED"}</span></div>
      ${commandCard("生成实验设计与待填图表", "$expplan")}
      <div class="workspace-grid wide-left">
        <div class="panel"><div class="panel-head"><strong>Projected paper blueprint</strong><span>7 figures/tables</span></div><div class="paper-outline"><div class="outline-section"><strong>Abstract</strong><span>预期问题、机制、方法与证据</span></div><div class="outline-section"><strong>Introduction</strong><span>motivation → gap → claims</span></div><div class="outline-section"><strong>Mechanism</strong><span>representation hypothesis + falsifier</span></div><div class="outline-section"><strong>Experiments</strong><span>setup → main → ablation → limits</span></div></div><div class="evidence-chain"><div class="chain-node">Claim C2</div><i>→</i><div class="chain-node focus">支持 / 证伪</div><i>→</i><div class="chain-node">Goal G4.2</div><i>→</i><div class="chain-node">Table T1</div></div></div>
        <div class="panel"><div class="panel-head"><strong>Table T1 · Main comparison</strong><span>paper-shaped shell</span></div><table class="result-shell"><thead><tr><th>Method</th><th>AdvBench ASR</th><th>StrongREJECT</th></tr></thead><tbody><tr><td>PAIR</td><td class="pending">pending</td><td class="pending">pending</td></tr><tr><td>Vernacular</td><td class="pending">pending</td><td class="pending">pending</td></tr><tr><td>Ours</td><td class="pending">pending</td><td class="pending">pending</td></tr></tbody></table><div class="source-list"><span><b>Dataset</b> AdvBench · cited source</span><span><b>Metric</b> ASR / StrongREJECT · cited source</span><span><b>Baseline</b> official GitHub / unified adapter / own implementation</span></div><button class="confirm-action" type="button" data-action="approve-expplan">${state.expApproved ? "✓ 实验设计已批准" : "批准实验设计 →"}</button></div>
      </div>`
  },
  {
    id: "runplan", short: "实验执行", label: "Run Plan & Results", path: "run-plan",
    title: "一次执行一个 Goal，完成即填表并整理",
    summary: ["04_RUN_PLAN", "Goal ✅", "05_EXP_RESULT", "数字可追溯"],
    compare: ["强调连续自主探索与整体吞吐", "适合可自动判分的大规模搜索", "每个 Goal 落盘、验证、填表、打勾，再解锁下一项"],
    render: state => `
      <div class="stage-head"><div><p class="eyebrow">STEP 05 · RUNPLAN + /GOAL</p><h3>计划、执行状态和结果证据在同一阶段</h3><p>执行在终端；网页只展示 Run Plan 与 Experiment Result，并让每个结果数字回到生成过程。</p></div><span class="status-pill">3 / 10 GOALS</span></div>
      ${commandCard("执行当前 Goal G4.3", "/goal Complete G4.3: run TrustLLM benchmark and fill Table T1")}
      <div class="artifact-switch" role="tablist"><button type="button" class="${state.runView === "plan" ? "active" : ""}" data-action="run-view" data-view="plan">04_RUN_PLAN.html</button><button type="button" class="${state.runView === "results" ? "active" : ""}" data-action="run-view" data-view="results">05_EXP_RESULT.html</button></div>
      ${state.runView === "plan" ? `<div class="workspace-grid wide-left"><div><div class="run-summary"><div><strong>10</strong><span>total goals</span></div><div><strong>4×A100</strong><span>estimated GPUs</span></div><div><strong>26 h</strong><span>estimated time</span></div></div><div class="goal-list"><div class="goal completed"><span class="goal-icon">✓</span><div><strong>G1.1 统一数据接口</strong><small>基础设施 / 无直接图表</small></div><b>DONE</b></div><div class="goal completed"><span class="goal-icon">✓</span><div><strong>G2.1 Representation sanity</strong><small>对应 Figure F2</small></div><b>DONE</b></div><div class="goal completed"><span class="goal-icon">✓</span><div><strong>G4.2 主实验 · AdvBench</strong><small>Table T1 已填；代码和文件已整理</small></div><b>DONE</b></div><div class="goal current"><span class="goal-icon">→</span><div><strong>G4.3 主实验 · TrustLLM</strong><small>填写 Table T1 的剩余 cells</small></div><b>CURRENT</b></div></div></div><div class="goal-detail"><p class="eyebrow">CURRENT GOAL</p><h4>G4.3 · 填写 TrustLLM 主结果</h4><p>保存每个 request / seed 的原始响应、evaluator 输出和实际命令。</p><div class="goal-meta"><span>Table T1</span><span>2× A100</span><span>≈ 4.5 h</span></div><div class="goal-files">results/main/trustllm/responses.jsonl<br>results/main/trustllm/metrics.json</div></div></div>` : ""}
      ${state.runView === "results" ? `<div class="panel result-ledger"><div class="panel-head"><strong>Table T1 · Main results</strong><span>点击数字追溯</span></div><table class="result-shell"><thead><tr><th>Method</th><th>AdvBench ASR ↑</th><th>TrustLLM ASR ↑</th></tr></thead><tbody><tr><td>PAIR</td><td>31.8</td><td class="pending">pending</td></tr><tr><td>Vernacular</td><td>37.6</td><td class="pending">pending</td></tr><tr><td>Ours</td><td><a class="trace-value" href="#demo-provenance-R1" data-provenance-trigger="demo-provenance-R1">42.1</a></td><td class="pending">pending</td></tr></tbody></table><p class="trace-hint">点击 <b>42.1</b>，展开这一格的原始文件、实际命令、代码、配置与计算方式。</p><details class="provenance-card" id="demo-provenance-R1"><summary>42.1 的生成过程</summary><dl><dt>原始文件</dt><dd><code>results/main/advbench/responses.jsonl</code></dd><dt>实际命令</dt><dd><code>python -m experiments.evaluate --dataset advbench --method ours --seed 42</code></dd><dt>代码与配置</dt><dd><code>experiments/evaluate.py</code> · <code>configs/main.yaml</code></dd><dt>计算方式</dt><dd>unsafe_count / valid_count × 100；bootstrap 95% CI</dd><dt>验证</dt><dd><span class="verified-mark">✓ 原始输出、命令与结果已核对</span></dd></dl></details></div>` : ""}
      `
  },
  {
    id: "paper", short: "论文写作", label: "Paper Writing", path: "paper-writing",
    title: "逐段写作、实时编译、图表可编辑",
    summary: ["逐段对话", "Accept → LaTeX", "Figures / Tables", "Live PDF"],
    compare: ["倾向批量生成 Markdown 或 LaTeX 草稿", "适合快速获得整体版本", "逐段确认，接受后才写入 LaTeX 并实时编译"],
    render: state => `
      <div class="stage-head"><div><p class="eyebrow">STEP 06 · PAPERWRITE</p><h3>写作使用独立网页工作台</h3><p>终端先配置论文项目；网页中逐段修改、接受正文，生成并批准可编辑图表，实时预览 PDF。</p></div><span class="status-pill">LIVE PDF</span></div>
      ${commandCard("配置并打开论文写作界面", "$paperwrite")}
      <div class="studio-tabs demo-studio-tabs"><button type="button" class="${state.paperView === "prose" ? "active" : ""}" data-action="paper-view" data-view="prose">正文</button><button type="button" class="${state.paperView === "figures" ? "active" : ""}" data-action="paper-view" data-view="figures">图</button><button type="button" class="${state.paperView === "tables" ? "active" : ""}" data-action="paper-view" data-view="tables">表</button></div>
      ${state.paperView === "prose" ? `<div class="studio-layout"><div class="studio-editor"><div class="paragraph-box"><div class="paragraph-purpose"><strong>I3 · Paragraph purpose</strong><br>提出 representation contraction hypothesis，并明确可证伪预测。</div><p class="generated-copy">We hypothesize that literary stylization weakens the separability of harmful intent. The claim predicts lower local probe accuracy and greater overlap with a benign reference region.</p><div class="comment-box">修改意见：收窄 causal wording，并引用 Figure 2。</div><div class="studio-actions"><button type="button">GPT 修改</button><button type="button" data-action="accept-paragraph">${state.paragraphAccepted ? "✓ 已写入 LaTeX" : "Accept → LaTeX"}</button></div></div></div><div class="pdf-preview"><div class="pdf-top">main.pdf · page 2 / 8</div><div class="pdf-page"><h4>3 Representation Analysis</h4><p></p><p></p><p></p><div class="pdf-mini-figure"><i></i><i></i><i></i></div><small>Figure 2: Representation signatures.</small><p></p><p></p></div></div></div>` : ""}
      ${state.paperView === "figures" ? `<div class="workspace-grid wide-left"><div class="panel"><div class="panel-head"><strong>Figure sequence</strong><span>按论文首次引用顺序</span></div><div class="goal-list"><div class="goal completed"><span class="goal-icon">✓</span><div><strong>F1 · Motivation</strong><small>editable PPT/PDF pair</small></div><b>APPROVED</b></div><div class="goal current"><span class="goal-icon">→</span><div><strong>F2 · Representation mechanism</strong><small>绑定 Section 3 · Paragraph I3</small></div><b>DRAFT</b></div></div></div><div class="panel"><div class="panel-head"><strong>F2 composition</strong><span>two-column figure</span></div><div class="figure-demo"><div><span>Prompt</span><p>保持三个 representation region、箭头和标签均为独立可编辑对象。</p></div><div class="pdf-mini-figure"><i></i><i></i><i></i></div></div><div class="source-list"><span><b>输出</b> paper/figures/F2.pptx + F2.pdf</span><span><b>步骤</b> 构图 → 重绘 → 审阅 → 插入正文</span></div><button type="button" class="confirm-action" data-action="approve-figure">${state.figureApproved ? "✓ Figure F2 已批准并插入" : "批准 Figure F2 →"}</button></div></div>` : ""}
      ${state.paperView === "tables" ? `<div class="workspace-grid wide-left"><div class="panel"><div class="panel-head"><strong>Table sequence</strong><span>只读取已核验结果</span></div><div class="goal-list"><div class="goal current"><span class="goal-icon">→</span><div><strong>T1 · Main results</strong><small>来源：已核验实验结果</small></div><b>READY</b></div><div class="goal"><span class="goal-icon">○</span><div><strong>T2 · Ablation</strong><small>等待全部 cells verified</small></div><b>BLOCKED</b></div></div></div><div class="panel"><div class="panel-head"><strong>T1 LaTeX preview</strong><span>可编辑</span></div><table class="result-shell"><thead><tr><th>Method</th><th>ASR ↑</th></tr></thead><tbody><tr><td>PAIR</td><td>31.8</td></tr><tr><td>Ours</td><td class="verified-mark">42.1</td></tr></tbody></table><div class="source-list"><span><b>Provenance</b> raw output → command → calculation</span><span><b>Placement</b> Section 5 · after E2</span></div><button type="button" class="confirm-action" data-action="approve-table">${state.tableApproved ? "✓ Table T1 已批准并插入" : "批准 Table T1 →"}</button></div></div>` : ""}`
  }
];

const state = { stage: 0, selectedIdea: "I3", ideaConfirmed: false, expApproved: false, runView: "plan", paperView: "prose", paragraphAccepted: false, figureApproved: false, tableApproved: false };
const nav = document.querySelector("#journey-nav");
const content = document.querySelector("#stage-content");
const path = document.querySelector("#browser-path");
const comparePanel = document.querySelector("#compare-panel");
const browserBody = document.querySelector(".browser-body");

function renderNav() {
  nav.innerHTML = stages.map((stage, index) => `<button class="journey-step ${index === state.stage ? "active" : ""}" data-stage="${index}" type="button"><span>0${index + 1}</span><strong>${stage.short}</strong></button>`).join("");
}

function renderCompare() {
  const stage = stages[state.stage];
  comparePanel.hidden = !stage.compare;
  browserBody.classList.toggle("comparing", Boolean(stage.compare));
  comparePanel.innerHTML = stage.compare ? `<p class="eyebrow">工作方式对比</p><h4>${stage.short}的工作重心</h4><div class="compare-card bad"><span>常见 AUTORESEARCH 侧重</span><strong>${stage.compare[0]}</strong><p>${stage.compare[1]}</p></div><div class="compare-card good"><span>RESEARCH BUDDY 侧重</span><strong>${stage.title}</strong><p>${stage.compare[2]}</p></div>` : "";
}

function renderStage() {
  const stage = stages[state.stage];
  renderNav();
  path.textContent = `research-buddy-demo.pages.dev/${stage.path}`;
  content.innerHTML = stage.render(state);
  content.scrollTop = 0;
  renderCompare();
}

nav.addEventListener("click", event => {
  const button = event.target.closest("[data-stage]");
  if (button) { state.stage = Number(button.dataset.stage); renderStage(); }
});

content.addEventListener("click", event => {
  const target = event.target.closest("[data-action]");
  if (target?.dataset.action === "select-idea") { state.selectedIdea = target.dataset.idea; state.ideaConfirmed = false; renderStage(); }
  if (target?.dataset.action === "confirm-idea") { state.ideaConfirmed = true; renderStage(); }
  if (target?.dataset.action === "approve-expplan") { state.expApproved = true; renderStage(); }
  if (target?.dataset.action === "run-view") { state.runView = target.dataset.view; renderStage(); }
  if (target?.dataset.action === "paper-view") { state.paperView = target.dataset.view; renderStage(); }
  if (target?.dataset.action === "accept-paragraph") { state.paragraphAccepted = true; renderStage(); }
  if (target?.dataset.action === "approve-figure") { state.figureApproved = true; renderStage(); }
  if (target?.dataset.action === "approve-table") { state.tableApproved = true; renderStage(); }
  const trace = event.target.closest("[data-provenance-trigger]");
  if (trace) {
    const detail = document.getElementById(trace.dataset.provenanceTrigger);
    if (detail) { detail.open = true; requestAnimationFrame(() => detail.scrollIntoView({behavior:"smooth", block:"center"})); }
  }
});

document.addEventListener("click", async event => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  const original = button.textContent;
  try { await navigator.clipboard.writeText(button.dataset.copy); button.textContent = "已复制 ✓"; }
  catch { button.textContent = "请手动复制"; }
  setTimeout(() => { button.textContent = original; }, 1400);
});

renderStage();
