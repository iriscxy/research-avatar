const stages = [
  {
    id: "profile", short: "研究画像", label: "Researcher Profile", path: "profile",
    title: "先理解研究者，再开始研究",
    description: "完整 Scholar 论文列表与本地工作习惯共同形成唯一研究画像。",
    summary: ["完整 Scholar HTML", "Research Lineage", "Writing Style", "Experiment Habits"],
    compare: ["以任务上下文和通用配置为主要起点", "适合快速进入自动探索", "Research Buddy 先建立可检查的个性化依据"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 01 · PROFILECONSTRUCT</p><h3>把 133 篇论文变成研究画像</h3><p>列表由 Google Scholar 决定；历史记录只补充实验环境和工作习惯。</p></div><span class="status-pill">HUMAN-SUPPLIED SOURCE</span></div>
      <div class="workspace-grid wide-left">
        <div class="panel"><div class="panel-head"><strong>输入完整 Scholar 页面</strong><span>本地文件 · 不上传</span></div><div class="upload-zone"><div><div class="file-icon"></div><strong>scholar_profile.html</strong><small>133 papers · complete page detected</small><button class="inline-action" data-action="profile">解析研究画像</button></div></div></div>
        <div class="panel"><div class="panel-head"><strong>PROFILE.md</strong><span>single source of truth</span></div><div class="profile-output"><div class="mini-card"><span>IDENTITY</span><strong>Trustworthy AI</strong><small>LLM safety · representation analysis</small></div><div class="mini-card"><span>LINEAGE</span><strong>Defense → Mechanism</strong><small>从现象防御走向内部机制</small></div><div class="mini-card"><span>WRITING</span><strong>Evidence first</strong><small>先提出可证伪问题，再给方法</small></div><div class="mini-card"><span>EXPERIMENT</span><strong>4× A100</strong><small>缓存中间结果 · 避免重复调用</small></div></div><div class="publication-line"><span>论文脉络</span><i></i><i></i><i></i></div></div>
      </div>`
  },
  {
    id: "literature", short: "文献 Survey", label: "Literature Survey", path: "literature",
    title: "先建立文献地图，再进入 Idea 生成",
    description: "从多个检索角度覆盖领域，只保留实际核验过的来源。",
    summary: ["多角度检索", "来源逐篇核验", "研究版图", "趋势与空白"],
    compare: ["围绕当前任务快速收集相关工作", "重点是为后续自动探索提供上下文", "Research Buddy 先产出可独立阅读、可核验的领域地图"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 02 · RESEARCHLIT</p><h3>把检索结果组织成研究版图</h3><p>每篇工作都来自实际打开并核验的来源；taxonomy、趋势与结构性空白共同约束后续选题。</p></div><span class="status-pill">VERIFIED SOURCES</span></div>
      <div class="workspace-grid">
        <div class="panel"><div class="panel-head"><strong>Literature landscape</strong><span>54 verified works</span></div><div class="landscape"><div class="paper-row"><span>25</span><div><strong>Adaptive stability</strong><small>confidence routing · early exit</small></div><b>CROWDED</b></div><div class="paper-row"><span>18</span><div><strong>Falsification probes</strong><small>counterarguments · controls</small></div><b>EMERGING</b></div><div class="paper-row"><span>11</span><div><strong>Traceable debate</strong><small>evidence accounting</small></div><b>OPEN GAP</b></div></div></div>
        <div class="panel"><div class="panel-head"><strong>Survey synthesis</strong><span>taxonomy → gaps</span></div><div class="paper-outline"><div class="outline-section"><strong>Taxonomy</strong><span>三条方法谱系及其边界</span></div><div class="outline-section"><strong>Trend</strong><span>从单一得分转向可证伪诊断</span></div><div class="outline-section"><strong>Debate</strong><span>自主探索效率 vs. 科学判断责任</span></div><div class="outline-section"><strong>Gap</strong><span>缺少与 claim 一一对应的证据合同</span></div></div></div>
      </div>`
  },
  {
    id: "ideas", short: "Idea 选择", label: "Idea Selection", path: "ideas",
    title: "检索不是装饰，拥挤方向不会硬推",
    description: "每个 idea 都必须面对最近工作与最强 reviewer objection。",
    summary: ["多个 Candidate", "最近工作核对", "新颖性硬门槛", "研究者选择"],
    compare: ["通常用排序快速呈现候选方向", "研究者再从候选中判断新颖性与价值", "Research Buddy 把新颖性设为推荐前的独立硬门槛"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 03 · IDEAGEN</p><h3>先让 idea 经得住最近工作</h3><p>Survey 的证据直接决定候选能否进入推荐榜，而不是只生成一段“看起来新颖”的描述。</p></div><span class="status-pill">HUMAN PICK</span></div>
      <div class="workspace-grid">
        <div class="panel"><div class="panel-head"><strong>Candidate ideas</strong><span>devil's-advocate reviewed</span></div><div class="idea-list"><div class="idea rejected" data-id="I1"><strong>Confidence Stop Gate</strong><small>可被 adaptive stability 工作直接吸收</small></div><div class="idea rejected" data-id="I2"><strong>Domain-specific Debate Router</strong><small>差异存在，但仍需重新构思</small></div><div class="idea selected" data-id="I3"><strong>Matched Falsification Certificate</strong><small>一个核心机制，具备明确反证实验</small></div></div></div>
        <div class="panel"><div class="panel-head"><strong>Qualification gates</strong><span>why I3 survives</span></div><div class="paper-outline"><div class="outline-section"><strong>Novel</strong><span>最近工作不能直接吸收核心贡献</span></div><div class="outline-section"><strong>Focused</strong><span>一个可独立验证的中心机制</span></div><div class="outline-section"><strong>Falsifiable</strong><span>关键结果失败时明确收窄或停止</span></div><div class="outline-section"><strong>Human pick</strong><span>由研究者确认进入实验规划</span></div></div></div>
      </div>`
  },
  {
    id: "expplan", short: "实验设计", label: "Projected Paper", path: "experiment-plan",
    title: "证据先行：多层 Goals，逐项填表作图",
    description: "每个 claim、表格 cell 和 figure panel 先冻结，再拆成可逐个击破的实验 Goals。",
    summary: ["逐段论文骨架", "Claim 与 falsifier", "多层 Goals", "逐项填表作图"],
    compare: ["从任务目标与实验空间开始自动探索", "论文结构与结果组织可在后续逐步完善", "Research Buddy 先固定证据空位：进度可见、证据不漏、失败可停"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 04 · EXPPLAN</p><h3>从证据空位拆出多层 Goals</h3><p>每个 Goal 都去填写明确的表格 cell 或 figure panel：进度可见、证据不漏、失败可停。</p></div><span class="status-pill">APPROVAL REQUIRED</span></div>
      <div class="workspace-grid wide-left">
        <div class="panel"><div class="panel-head"><strong>Projected paper blueprint</strong><span>one sentence / paragraph</span></div><div class="paper-outline"><div class="outline-section"><strong>1 Introduction</strong><span>P1 motivation · P2 gap · P3 claims</span></div><div class="outline-section"><strong>3 Mechanism</strong><span>P1 representation hypothesis · P2 falsifier</span></div><div class="outline-section"><strong>4 Method</strong><span>P1 style graph · P2 two-turn execution</span></div><div class="outline-section"><strong>5 Experiments</strong><span>P1 setup · P2 main result · P3 ablation</span></div></div><div class="evidence-chain"><div class="chain-node">Claim C2</div><i>→</i><div class="chain-node focus">支持 / 证伪</div><i>→</i><div class="chain-node">Goal G4.2</div><i>→</i><div class="chain-node">Table 1</div></div></div>
        <div class="panel"><div class="panel-head"><strong>Table 1 · Main comparison</strong><span>paper-shaped shell</span></div><table class="result-shell"><thead><tr><th>Method</th><th>AdvBench ASR</th><th>StrongREJECT</th></tr></thead><tbody><tr><td>PAIR</td><td class="pending">pending</td><td class="pending">pending</td></tr><tr><td>Vernacular</td><td class="pending">pending</td><td class="pending">pending</td></tr><tr><td>Ours</td><td class="pending">pending</td><td class="pending">pending</td></tr></tbody></table><p class="citation-row">Dataset: <a>AdvBench</a> · Metrics: <a>ASR</a>, <a>StrongREJECT</a> · split 由 runplan 决定</p></div>
      </div>`
  },
  {
    id: "runplan", short: "实验执行", label: "Run Plan", path: "run-plan",
    title: "一次只解锁一个有边界的 goal",
    description: "每个 goal 都知道要填哪个图表、需要什么资源、如何验证完成。",
    summary: ["GPU / 时间预算", "P / G 层级", "一个当前 goal", "完成即整理文件"],
    compare: ["强调连续自主探索与整体吞吐", "适合可自动判分、可大规模搜索的任务", "Research Buddy 每个 Goal 落盘、验证、打勾，再解锁下一项"],
    render: state => `
      <div class="stage-head"><div><p class="eyebrow">STEP 05 · RUNPLAN + /GOAL</p><h3>清楚知道下一项要做什么</h3><p>计划是人能读懂的网页；详细 acquisition contract 留在机器可读状态中。</p></div><span class="status-pill">${state.goalDone ? "GOAL COMPLETE" : "1 GOAL UNLOCKED"}</span></div>
      <div class="workspace-grid wide-left">
        <div><div class="run-summary"><div><strong>10</strong><span>total goals</span></div><div><strong>4×A100</strong><span>estimated GPUs</span></div><div><strong>26 h</strong><span>estimated time</span></div></div><div class="goal-list"><div class="goal completed"><span class="goal-icon">✓</span><div><strong>G1.1 统一数据接口</strong><small>无直接图表 · shared infrastructure</small></div><b>DONE</b></div><div class="goal completed"><span class="goal-icon">✓</span><div><strong>G2.1 Representation sanity</strong><small>对应 Figure 2 · four panels</small></div><b>DONE</b></div><div class="goal ${state.goalDone ? "completed" : "current"}"><span class="goal-icon">${state.goalDone ? "✓" : "→"}</span><div><strong>G4.2 主实验 · AdvBench</strong><small>填写 Table 1 的 AdvBench cells</small></div><b>${state.goalDone ? "DONE" : "CURRENT"}</b></div><div class="goal"><span class="goal-icon">○</span><div><strong>G4.3 主实验 · TrustLLM</strong><small>等待 G4.2 通过验证</small></div><b>LOCKED</b></div></div></div>
        <div class="goal-detail"><p class="eyebrow">CURRENT GOAL</p><h4>G4.2 · 填写 AdvBench 主结果</h4><p>运行 7 个方法 × 8 个目标模型；保存每个 request/seed 的原始响应和 evaluator 输出。</p><div class="goal-meta"><span>Table T1</span><span>2× A100</span><span>≈ 4.5 h</span><span>95% bootstrap CI</span></div><div class="goal-files">results/main/advbench/responses.jsonl<br>results/main/advbench/metrics.json<br>code/RESULTS_LEDGER.csv</div><button class="goal-complete" data-action="complete-goal" ${state.goalDone ? "disabled" : ""}>${state.goalDone ? "✓ 已保存、验证并整理文件" : "模拟完成 Goal G4.2"}</button></div>
      </div>`
  },
  {
    id: "paper", short: "论文写作", label: "Paper Studio", path: "paper-studio",
    title: "逐段写作、实时编译、图表可编辑",
    description: "论文结构来自批准的计划；Paper Studio 负责让编辑与审阅真正可交互。",
    summary: ["Paragraph purpose", "Reference excerpt", "Accept → LaTeX", "Editable figures"],
    compare: ["倾向批量生成 Markdown 或 LaTeX 草稿", "适合快速获得可阅读的整体版本", "Research Buddy 逐段确认，接受后才写入并编译"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">STEP 06 · PAPERWRITE + PAPER STUDIO</p><h3>论文不是一次性生成物</h3><p>每个段落都有目的、参考结构和证据绑定；接受之后才进入 LaTeX。</p></div><span class="status-pill">LIVE PDF PREVIEW</span></div>
      <div class="studio-layout"><div class="studio-editor"><div class="studio-tabs"><span class="active">正文</span><span>图</span><span>表</span></div><div class="paragraph-box"><div class="paragraph-purpose"><strong>I3 · Paragraph purpose</strong><br>提出 representation contraction hypothesis，并明确它的可证伪预测。</div><p class="generated-copy">We hypothesize that literary stylization weakens the separability of harmful intent in aligned language models. This claim predicts both lower local probe accuracy and greater overlap with a benign reference region; failure of either signature would narrow the proposed mechanism.</p><div class="comment-box">修改意见：把 causal wording 收窄，并在最后一句引用 Figure 2。</div><div class="studio-actions"><button>GPT 修改</button><button>✓ Accept → LaTeX</button></div></div></div><div class="pdf-preview"><div class="pdf-top">main.pdf · page 2 / 8</div><div class="pdf-page"><h4>3 Representation Analysis</h4><p></p><p></p><p></p><p></p><div class="pdf-mini-figure"><i></i><i></i><i></i></div><small>Figure 2: Representation signatures under stylized inputs.</small><p></p><p></p></div></div></div>`
  }
];

const state = { stage: 0, goalDone: false };
const nav = document.querySelector("#journey-nav");
const content = document.querySelector("#stage-content");
const summary = document.querySelector("#stage-summary");
const path = document.querySelector("#browser-path");
const comparePanel = document.querySelector("#compare-panel");
const browserBody = document.querySelector(".browser-body");

function renderNav() {
  nav.innerHTML = stages.map((stage, index) => `<button class="journey-step ${index === state.stage ? "active" : ""} ${index < state.stage ? "done" : ""}" data-stage="${index}" type="button"><span>0${index + 1}</span><strong>${stage.short}</strong></button>`).join("");
}

function renderStage() {
  const stage = stages[state.stage];
  renderNav();
  path.textContent = `research-buddy-demo.pages.dev/${stage.path}`;
  summary.innerHTML = `<span class="summary-kicker">STAGE 0${state.stage + 1}</span><h3 class="summary-title">${stage.label}</h3><ul class="summary-list">${stage.summary.map((item, index) => `<li class="${index === 0 ? "active" : ""}">${item}</li>`).join("")}</ul>`;
  content.innerHTML = stage.render(state);
  renderCompare();
}

function renderCompare() {
  const stage = stages[state.stage];
  browserBody.classList.add("comparing");
  comparePanel.innerHTML = `<p class="eyebrow">README 对比</p><h4>${stage.short}的工作重心</h4><div class="compare-card bad"><span>开源 AUTORESEARCH 常见侧重</span><strong>${stage.compare[0]}</strong><p>${stage.compare[1]}</p></div><div class="compare-card good"><span>RESEARCH BUDDY 的侧重</span><strong>${stage.title}</strong><p>${stage.compare[2]}</p></div><div class="compare-verdict">两种路线解决的问题不同：这里选择让研究者持续掌握科学判断。</div>`;
}

function setStage(index) {
  state.stage = (index + stages.length) % stages.length;
  renderStage();
}

nav.addEventListener("click", event => {
  const button = event.target.closest("[data-stage]");
  if (!button) return;
  setStage(Number(button.dataset.stage));
});
content.addEventListener("click", event => {
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "complete-goal") { state.goalDone = true; renderStage(); }
  if (action === "profile") {
    event.target.textContent = "✓ 画像已生成";
    event.target.disabled = true;
  }
});
renderStage();
