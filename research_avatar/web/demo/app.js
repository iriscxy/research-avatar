const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));

const commandStrip = (title, command, detail = "在本地终端运行；生成内容会自动出现在网页中。") => `
  <div class="command-card">
    <div><span>在本地终端运行</span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></div>
    <code>${escapeHtml(command)}</code><button type="button" data-copy="${escapeHtml(command)}">复制命令</button>
  </div>`;

const pendingRows = (xs, series) => xs.map(x => `<tr><th>${x}</th>${series.map(() => `<td class="demo-pending">待实验</td>`).join("")}</tr>`).join("");

const pendingTable = ({ headers, rows, className = "" }) => `
  <div class="table-scroll"><table class="result-shell source-table ${className}"><thead><tr>${headers.map(name => `<th>${name}</th>`).join("")}</tr></thead><tbody>${rows.map(name => `<tr><th>${name}</th>${headers.slice(1).map(() => `<td class="demo-pending">待实验</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;

const projectedPanel = ({ title, dataset, metric, fields, xLabel, xs, series, image }) => `
  <section class="projected-panel">
    <h5>${title}</h5>
    <p><strong>数据与评测集：</strong>${dataset}</p>
    <p><strong>指标与坐标轴：</strong>${metric}</p>
    <div class="figure-data-pair">
      <div class="numeric-source">
        ${pendingTable({headers:[xLabel,...series],rows:xs})}
        <p class="field-line">生成图表所需字段：${fields}</p>
      </div>
      <figure class="projected-chart">
        <img src="${image}" alt="${title} projected preview">
        <figcaption>图形预览：实验完成后，将使用左侧经过核验的数据自动生成。</figcaption>
      </figure>
    </div>
  </section>`;

const resultTable = ({ id, title, headers, rows, note }) => `
  <section class="evidence-artifact result-table-artifact">
    <p class="artifact-kicker">${id} · 等待实验结果</p>
    <h4>${title}</h4>
    ${pendingTable({headers,rows,className:"main-result"})}
    <p>${note}</p>
  </section>`;

const experimentPlanDemo = () => {
  const methods = ["仅干净数据", "同预算随机增强", "MTA（本文方法）", "四倍完整混合增强"];
  return `
    <article class="actual-expplan">
      <header class="expplan-title">
        <p class="artifact-kicker">实验方案 · 已确认</p>
        <h4>Margin-Targeted Typo Augmentation</h4>
        <p>在相同类别配额和最终重训练样本数下，验证优先选择低真实标签分数差的 typo 是否稳定优于随机选择。</p>
        <div class="expplan-facts"><span>COLING 2027 Short</span><span>3 张图</span><span>2 张表</span><span>40 个待填数据单元</span><span>本地 CPU · 0 GPU 小时</span></div>
      </header>

      <section class="plain-section projected-abstract">
        <p class="artifact-kicker">标题与摘要方向</p>
        <h4>Spend Typo Budget Where the Classifier Is Unsure</h4>
        <p>MTA 为每条训练样本生成 swap、delete、insert 和 keyboard 四种候选 typo，用干净分类器计算真实标签分数差，再按类别等额选择最低分数差候选。实验只改变选择策略，候选池、模型、类别分布、重训练数量和测试集保持一致。</p>
      </section>

      <section class="plain-section setup-section">
        <p class="artifact-kicker">段落与证据</p><h4>每个关键主张都有对应图表和失败条件</h4>
        <dl class="setup-grid"><dt>数据</dt><dd>固定版本 CLINC150；50-intent 主实验与 20-intent 范围检查</dd><dt>模型</dt><dd>共享的 multinomial Naive Bayes word-count 分类器</dd><dt>比较方法</dt><dd>仅干净数据 · 类别平衡随机预算 · MTA · 类别平衡完整混合</dd><dt>主要指标</dt><dd>干净准确率 · 四种 typo 的平均与最差准确率 · 配对 bootstrap 95% 区间</dd><dt>固定种子</dt><dd>六个设置复用同一组 8 个、与探索阶段分离的种子</dd><dt>证据产物</dt><dd>F1 动机图 · T1 主表 · F2 六设置区间图 · T2 操作符表 · F3 固定 20-intent 预算曲线</dd></dl>
      </section>

      ${resultTable({id:"T1",title:"50-intent 主比较",headers:["方法","干净准确率 ↑","平均 typo 准确率 ↑","最差操作符准确率 ↑","增强样本数 ↓"],rows:methods,note:"C1 只有在 MTA−随机的配对 95% 区间下界大于 0 时成立；C2 只有在 MTA−完整混合的区间下界大于 −0.01 时成立。"})}

      <section class="evidence-artifact">
        <p class="artifact-kicker">F2 · 六设置确认图</p><h4>同一冻结种子组上的结果必须全部为正</h4>
        ${pendingTable({headers:["设置","MTA − 随机 · 平均 typo 准确率","配对 95% 区间"],rows:["50 intents","20 intents","severity 0.30","severity 0.60","budget 10%","budget 50%"]})}
        <p class="field-line">图表源字段：case_id · seed · random_noisy_accuracy · mta_noisy_accuracy · bootstrap_ci</p>
      </section>

      <section class="plain-section claim-contract">
        <p class="artifact-kicker">主张与失败条件</p><h4>正结果必须同时满足这些预先固定的边界</h4>
        <div class="claim-rows"><div><b>C1</b><p>MTA 在全部六个设置中优于同预算随机选择。</p><span>任一配对区间下界不高于 0，则对应广度主张失败。</span></div><div><b>C2</b><p>主设置用四分之一增强样本达到完整混合的一点以内。</p><span>MTA−完整混合区间下界不高于 −0.01，则非劣主张失败。</span></div><div><b>C3</b><p>优势覆盖 swap、delete、insert、keyboard 四种测试操作符。</p><span>任一操作符点估计不优于随机，则收窄跨操作符主张。</span></div></div>
      </section>

      <section class="plain-section">
        <p class="artifact-kicker">解释边界</p><h4>验证完整选择器效果，不冒充几何机制证明</h4>
        <p>低分数差选择还可能改变编辑强度和难例来源的重复权重，因此当前设计只识别整个选择策略的效果；编辑数匹配与每来源唯一候选是后续机制对照，不作为当前论文已经证明的结论。</p>
      </section>

      <section class="approval-line"><strong>方案确认</strong><span>已确认 · 2026-08-17</span><p>阈值和设置固定在确认脚本中；若证据不支持，就报告失败条件而不是改写判断标准。</p></section>
    </article>`;
};

let runPlanDemoState = null;

const runStatusMark = status => ({completed:"✅",running:"▶",proposed:"→",locked:"○",pending:"○",blocked:"⚠",invalidated:"⚠"}[status] || "○");

const publicPartTitles = {
  P1: "基础通路验证",
  P2: "正结果确认",
};

const publicArtifactLabels = {
  F1: "图 1",
  F2: "图 2",
  F3: "图 3",
  T1: "表 1",
  T2: "表 2",
};

const executionModePanel = goal => `<div class="demo-current-goal execution-mode-panel" data-demo-current-goal="${escapeHtml(goal.id)}">
  <p class="artifact-kicker">Goal 确认</p>
  <h5>查看完整计划后，选择如何确认</h5>
  <div class="execution-mode-options">
    <div class="selected"><b>一次确认全部 Goals</b><span>系统按依赖顺序自动执行；每个 Goal 仍分别保存、核验、更新图表和标记完成。</span></div>
    <div><b>逐个查看并确认</b><span>每个 Goal 开始前先查看任务、产出和完成标准，再决定是否执行。</span></div>
  </div>
  <p class="execution-stop-rule">遇到验证失败、预算耗尽或需要新的研究判断时，自动执行会立即停止。</p>
  <dl><dt>下一个 Goal</dt><dd>${escapeHtml(goal.id)} · ${escapeHtml(goal.title)}</dd><dt>预期产出</dt><dd>${(goal.outputs || []).map(escapeHtml).join(" · ")}</dd><dt>完成标准</dt><dd>${escapeHtml(goal.completion_check)}</dd></dl>
</div>`;

const goalHierarchy = () => {
  if (!runPlanDemoState) return `<section class="goal-hierarchy"><p>实验计划暂时无法加载。</p></section>`;
  const goals = Object.fromEntries(runPlanDemoState.goals.map(goal => [goal.id, goal]));
  const currentId = runPlanDemoState.active_goal || runPlanDemoState.proposed_goal_id;
  const completed = runPlanDemoState.goals.filter(goal => goal.status === "completed").length;
  const representativeGoalIds = [currentId, "G1.1", "G2.1"].filter((id, index, ids) => id && goals[id] && ids.indexOf(id) === index);
  const representativeParts = representativeGoalIds.map(goalId => {
    const goal = goals[goalId];
    const part = runPlanDemoState.parts.find(item => item.id === goal.part_id);
    return {part, goal};
  });
  return `<section class="goal-hierarchy"><p class="artifact-kicker">Goal 执行计划</p><p class="runplan-demo-note">这个本地 CPU 研究被拆为两个可验证 Goal：先固定可复现通路，再运行六设置确认并一次填充全部实证图表。当前 ${completed}/${runPlanDemoState.goals.length} 个 Goal 已完成。</p>${representativeParts.map(({part, goal}) => {
    const destination = goal.artifact_ids?.length ? goal.artifact_ids.map(id => publicArtifactLabels[id] || id).join("、") : "本任务不直接更新图表";
    const completedExample = goal.id === "G2.1";
    return `<div class="part-row"><h4><span>${escapeHtml(part.id.replace("P", "阶段 "))}</span>${escapeHtml(publicPartTitles[part.id] || part.title)}</h4><p class="part-decision">${escapeHtml(part.decision)}</p><div class="expanded-goal ${completedExample ? "demo-completed-goal" : ""}"><b>${completedExample ? "✅" : runStatusMark(goal.status)}</b><strong>${escapeHtml(goal.id)} · ${escapeHtml(goal.title)}${completedExample ? '<small>完成效果示例</small>' : ""}</strong><span>对应论文内容：${escapeHtml(destination)}</span><p>${escapeHtml(goal.visible_work)} ${escapeHtml(goal.visible_evidence)} 完成标准：${escapeHtml(goal.completion_check)}</p>${goal.id === currentId ? executionModePanel(goal) : ""}${completedExample ? resultProvenanceDemo() : ""}</div></div>`;
  }).join("")}</section>`;
};

const completedF2Rows = [
  ["50 intents", 0.01675, 0.01317, 0.02079],
  ["20 intents", 0.01307, 0.00802, 0.01688],
  ["severity .30", 0.00745, 0.00547, 0.00943],
  ["severity .60", 0.01641, 0.01016, 0.02172],
  ["budget 10%", 0.00682, 0.00344, 0.01073],
  ["budget 50%", 0.01740, 0.01359, 0.02120],
];

const provenanceNumber = (value, setting, field) => `<span class="provenance-number" tabindex="0">${value.toFixed(4)}<span class="provenance-tooltip" role="tooltip"><b>已核验科学结果</b><span><strong>任务</strong> G2.1</span><span><strong>设置</strong> ${setting} · ${field}</span><span><strong>原始结果</strong> results/typo_margin/confirmatory_results.json</span><span><strong>派生数据</strong> results/typo_margin/paper_values.json</span><span><strong>计算</strong> 8 个冻结种子的配对准确率差与 percentile bootstrap</span><span><strong>运行命令</strong> python3 code/typo_margin/confirm.py</span><span><strong>验证</strong> 40/40 ledger cells REAL / VERIFIED</span></span></span>`;

const completedF2Chart = () => {
  const x = value => 55 + value / 0.025 * 410;
  return `<figure class="completed-chart"><svg viewBox="0 0 520 260" role="img" aria-label="六个确认设置的 MTA 减随机准确率及 95% 区间"><g class="chart-grid"><line x1="55" y1="25" x2="55" y2="225"/><line x1="219" y1="25" x2="219" y2="225"/><line x1="383" y1="25" x2="383" y2="225"/></g>${completedF2Rows.map((row,index) => { const y=42+index*32; return `<text x="7" y="${y+4}" class="setting-label">${row[0]}</text><line x1="${x(row[2])}" y1="${y}" x2="${x(row[3])}" y2="${y}" class="ci-line"/><line x1="${x(row[2])}" y1="${y-5}" x2="${x(row[2])}" y2="${y+5}" class="ci-line"/><line x1="${x(row[3])}" y1="${y-5}" x2="${x(row[3])}" y2="${y+5}" class="ci-line"/><circle cx="${x(row[1])}" cy="${y}" r="4" class="point-style"/>`; }).join("")}<g class="chart-labels"><text x="50" y="247">0</text><text x="207" y="247">0.01</text><text x="371" y="247">0.02</text><text x="438" y="247">MTA − random</text></g></svg><figcaption>圆点为平均差，横线为配对 bootstrap 95% 区间；所有下界均高于零。</figcaption></figure>`;
};

const resultProvenanceDemo = () => `
  <section class="evidence-artifact completed-result future-result-example"><p class="artifact-kicker">真实完成结果</p><h4>六个设置中的 MTA − 随机选择</h4>
    <div class="simulated-run-summary"><strong>✅ 确认运行已完成</strong><span>40/40 数据单元已核验</span><span>配对区间可重算</span><span>图形可重新生成</span></div>
    <p>这里展示当前正结果研究的真实确认数据。每个数字都能查看结果路径、计算方法、命令和验证状态。</p>
    <div class="provenance-flow"><span>冻结种子结果</span><i>→</i><span>配对差值</span><i>→</i><span>bootstrap 区间</span><i>→</i><span>证据台账</span><i>→</i><span>论文图形</span></div>
    <div class="completed-result-grid"><div class="table-scroll"><table class="result-shell source-table completed-source"><thead><tr><th>设置</th><th>平均差</th><th>95% 下界</th><th>95% 上界</th></tr></thead><tbody>${completedF2Rows.map(([setting,estimate,low,high]) => `<tr><th>${setting}</th><td>${provenanceNumber(estimate,setting,"estimate")}</td><td>${provenanceNumber(low,setting,"CI low")}</td><td>${provenanceNumber(high,setting,"CI high")}</td></tr>`).join("")}</tbody></table><p class="hover-instruction">鼠标停在任一数字上，或用键盘聚焦，即可查看来源、计算和验证过程。</p></div>${completedF2Chart()}</div>
  </section>`;

const paperStudioScreenshots = () => `<section class="paper-studio-live">
  <p class="artifact-kicker">论文写作工作区</p>
  <h4>这就是完成论文后的真实 Paper Studio</h4>
  <p>下面加载固定应用本身，而不是截图或重新绘制的假界面。可以切换正文、图和表，浏览每个已写段落、生成历史、可编辑图表与最终 PDF；Demo 使用完成态项目的只读副本，不会产生 API 费用。</p>
  <div class="paper-studio-frame-shell">
    <div class="paper-studio-frame-bar"><span>完成态 Demo · 只读</span><a href="/demo-studio/" target="_blank" rel="noopener">在新页面打开</a></div>
    <iframe src="/demo-studio/" title="完成态 Paper Studio 交互 Demo" loading="lazy"></iframe>
  </div>
</section>`;

let reportStructures = {};

const publicReportTitles = {
  profile: "研究者画像",
  literature: "文献调研报告",
  ideas: "研究方向评估",
  expplan: "实验设计",
  runplan: "实验执行计划",
  results: "实验结果与证据",
  "paper-studio": "论文写作工作区",
};

const publicSectionTitles = {
  profile: {H:"数据来源与覆盖", 1:"研究方向", 2:"研究脉络", 3:"写作风格", 4:"实验习惯", 5:"工作偏好", 6:"论文记录"},
  literature: {1:"调研范围与分类", 2:"主题地图", 3:"文献对比", 4:"当前争议", 5:"趋势与研究空白", 6:"核验过的参考文献"},
  ideas: {1:"文献边界", 2:"候选方向排序", 3:"候选方案", 4:"研究者选择"},
  expplan: {1:"投稿目标与参考依据", 2:"论文结构与证据规划", 3:"方案确认"},
  runplan: {1:"资源与时间估算", 2:"实现来源", 3:"图表与任务对应", 4:"阶段与任务"},
  results: {1:"完成进度", 2:"论文图表", 3:"数字如何生成"},
  "paper-studio": {正文:"正文写作", 图:"图片制作", 表:"表格编辑"},
};

const reportDocument = (key, kicker = "内容预览") => {
  const report = reportStructures[key];
  if (!report) return "";
  return `<article class="report-document" aria-label="${report.artifact}内容预览">
    <header><span>${kicker}</span><h4>${publicReportTitles[key] || report.artifact}</h4><p>${report.note}</p></header>
    ${report.sections.map(section => `<section data-structure-section="${key}:${section.number}">
      <div class="report-section-title"><span>${section.number}</span><h5>${publicSectionTitles[key]?.[section.number] || section.title}</h5></div>
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
      <div class="stage-head"><div><p class="eyebrow">第一步 · 研究者画像</p><h3>建立可复用的研究者画像</h3><p>从研究者提供的 Scholar 页面和本地写作样本中，整理研究方向、方法偏好、写作风格与实验习惯。</p></div><span class="status-pill">已完成</span></div>
      ${commandStrip("从本地 Scholar HTML 建立研究者画像", "$profileconstruct 使用 ~/Downloads/scholar_profile.html")}
      ${reportDocument("profile", "画像预览")}`
  },
  {
    id: "literature", short: "文献调研", path: "literature", title: "先建立可核验的文献地图", compare: null,
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第二步 · 文献调研</p><h3>把相关工作整理成可核验的研究地图</h3><p>从不同角度检索并核对论文，梳理主要方向、争议和仍待解决的问题。</p></div><span class="status-pill">30 篇已核验</span></div>
      ${commandStrip("整理并核验相关文献", "$researchlit typographical robustness in lightweight intent classification")}
      ${reportDocument("literature")}`
  },
  {
    id: "ideas", short: "方向选择", path: "ideas", title: "候选先过门槛，再由研究者选择",
    compare: ["通常用排序快速呈现候选方向", "研究者再判断价值与新颖性", "把新颖性与可证伪性设为独立硬门槛"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第三步 · 研究方向</p><h3>比较候选方向，明确新颖性与风险</h3><p>每个方向都说明研究空白、核心机制、可证伪条件和最近工作的重合程度，最后由研究者选择。</p></div><span class="status-pill">I7 已选择</span></div>
      ${commandStrip("生成候选方向并逐一核验", "$ideagen")}
      ${reportDocument("ideas")}`
  },
  {
    id: "expplan", short: "实验设计", path: "experiment-plan", title: "先明确论文主张，再反推所需实验",
    compare: ["先列实验清单，再根据结果补充论证", "容易出现实验很多、论文主张却没有被直接验证", "先确定论文要证明什么，再为每个主张安排图表、指标和失败条件"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第四步 · 实验设计</p><h3>从论文主张反推实验和证据</h3><p>先明确论文需要回答的问题，再为每个主张安排数据、基线、指标、图表和失败条件。</p></div><span class="status-pill">方案已确认</span></div>
      ${commandStrip("生成实验设计与待填图表", "$expplan")}
      ${experimentPlanDemo()}`
  },
  {
    id: "runplan", short: "实验执行", path: "run-plan", title: "把完整实验拆成一个个可验证的 Goal",
    compare: ["强调连续自主探索与整体吞吐", "执行过程通常缺少清晰的证据边界", "先展示完整 Goals；可一次确认后自动执行，也可逐个查看并确认"],
    render: () => {
      const currentId = runPlanDemoState?.active_goal || runPlanDemoState?.proposed_goal_id || "NONE";
      const allGoalsConfirmed = runPlanDemoState?.goal_confirmation?.scope === "all_goals";
      return `
      <div class="stage-head"><div><p class="eyebrow">第五步 · 实验执行</p><h3>把完整实验拆成一个个 Goal</h3><p>先查看全部 Goal 的任务、依赖、完成标准和对应图表；随后可以一次确认全部 Goals 自动执行，也可以逐个查看并确认。</p></div><span class="status-pill">${allGoalsConfirmed ? "全部 Goals 已确认" : `${escapeHtml(currentId)} 等待确认`}</span></div>
      ${reportDocument("runplan")}
      ${goalHierarchy()}`;
    }
  },
  {
    id: "paper", short: "论文写作", path: "paper-writing", title: "逐段写作、实时编译、图表可编辑",
    compare: ["倾向批量生成 Markdown 或 LaTeX 草稿", "适合快速获得整体版本", "正文调用 LLM API（不是 Code Agent）逐段生成；确认接受后才写入 LaTeX 并实时编译"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第六步 · 论文写作</p><h3>在统一工作区中完成正文、图片和表格</h3><p>逐段完善正文，制作可编辑图表，并在每次确认后查看重新编译的论文 PDF。</p></div><span class="status-pill">写作工作区</span></div>
      ${commandStrip("结果完成后启动论文写作", "$paperwrite", "系统准备论文项目并打开写作工作区；LLM API 生成正文候选，本地工具负责可复现图表与排版。")}
      ${paperStudioScreenshots()}
      <section class="plain-section"><p class="artifact-kicker">写作与确认</p><h4>每项内容都经过确认后进入论文</h4><ul><li>正文：LLM API 生成可编辑候选，研究者确认后写入 LaTeX。</li><li>图片：实验数据生成结果图；机制图同时保留构图参考和可编辑文件。</li><li>表格：只使用经过核验的实验数字，确认后更新右侧 PDF。</li></ul></section>`
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
  comparePanel.innerHTML = stage.compare ? `<p class="eyebrow">工作方式对比</p><h4>${stage.short}的工作重心</h4><div class="compare-card bad"><span>常见自动化研究工具</span><strong>${stage.compare[0]}</strong><p>${stage.compare[1]}</p></div><div class="compare-card good"><span>Research Avatar</span><strong>${stage.title}</strong><p>${stage.compare[2]}</p></div>` : "";
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
window.addEventListener("message", event => {
  if (event.origin !== window.location.origin) return;
  const paperFrame = document.querySelector('.paper-studio-live iframe[src="/demo-studio/"]');
  if (
    !paperFrame
    || event.source !== paperFrame.contentWindow
    || event.data?.type !== "paper-studio-demo-api-key-required"
  ) return;
  if (window.parent && window.parent !== window) {
    window.parent.postMessage(event.data, window.location.origin);
  }
});

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
      fetch("report-structures.json?v=20260815-goal-modes"),
      fetch("runplan-state.json?v=20260817-mta-positive")
    ]);
    if (!structureResponse.ok) throw new Error(`report structures HTTP ${structureResponse.status}`);
    if (!runPlanResponse.ok) throw new Error(`run plan snapshot HTTP ${runPlanResponse.status}`);
    reportStructures = await structureResponse.json();
    runPlanDemoState = await runPlanResponse.json();
    state.stage = stageIndexFromLocation();
    renderStage();
  } catch (error) {
    content.innerHTML = `<div class="demo-load-error"><strong>页面内容暂时无法加载。</strong><span>${String(error)}</span></div>`;
  }
}

initializeDemo();
