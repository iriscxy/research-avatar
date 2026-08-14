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
  const methods = ["No Defense", "ABD", "RTV", "JBShield", "TrajGuard", "First-Divergence Repair"];
  return `
    <article class="actual-expplan">
      <header class="expplan-title">
        <p class="artifact-kicker">实验方案 · 已确认</p>
        <h4>First-Divergence Repair</h4>
        <p>先明确论文需要回答的问题，再为每个主张安排可核验的实验、图表和失败条件。</p>
        <div class="expplan-facts"><span>ACL 2027</span><span>4 张图</span><span>3 张表</span><span>144 个待填数据单元</span><span>4×A100 · 约 428 GPU 小时</span></div>
      </header>

      <section class="plain-section">
        <p class="artifact-kicker">研究目标与参考依据</p>
        <h4>明确投稿目标与参考边界</h4>
        <ul><li><strong>投稿目标：</strong>ACL 2027 主会长文。</li><li><strong>方法参照：</strong>以 RTV 界定科学问题、轨迹机制和核心比较基线。</li><li><strong>写作参照：</strong>以研究者自己的 ABD 论文校准段落功能、章节比例和图表节奏。</li></ul>
      </section>

      <section class="plain-section projected-paper-overview">
        <p class="artifact-kicker">论文结构</p>
        <h4>先确定论文要讲清楚什么</h4>
        <p>标题、摘要方向、段落结构、图表、可证伪主张、实现方案和预算在实验开始前统一规划。</p>
      </section>

      <section class="plain-section projected-abstract">
        <p class="artifact-kicker">标题与摘要方向</p>
        <h4>First-Divergence Repair: Causal Single-Layer Recovery from Style-Induced Jailbreaks</h4>
        <p>We test whether intent-preserving style transformations cause a reproducible first exit from a model's safety trajectory and whether repairing only that layer restores downstream safety. A unified white-box framework compares five rerun representation defenses across AdvBench, HarmBench, XSTest, and Just-Eval. The claim survives only if first-exit repair uniquely beats wrong-layer and repeated-repair controls while improving the safety–utility–cost frontier.</p>
      </section>

      <section class="plain-section">
        <p class="artifact-kicker">图表规划</p>
        <h4>让每张图表承担明确的论证任务</h4>
        <p>方案包含 4 张图和 3 张表。本页选取一张数据图和一张主结果表，说明实验数据将如何进入论文。</p>
      </section>

      <section class="plain-section setup-section">
        <p class="artifact-kicker">段落与证据</p><h4>每个关键段落都对应具体证据</h4>
        <h5 class="embedded-heading">实验设置</h5>
        <dl class="setup-grid"><dt>模型</dt><dd>Llama-3.1-8B-Instruct · Mistral-7B-Instruct-v0.3 · Qwen2.5-7B-Instruct</dd><dt>安全评测</dt><dd>AdvBench 50 行为子集 · HarmBench 1.0</dd><dt>正常任务与质量评测</dt><dd>XSTest · Just-Eval · Alpaca 正常任务对照</dd><dt>安全评估器</dt><dd>SORRY-Bench</dd><dt>比较方法</dt><dd>No Defense · ABD · RTV · JBShield · TrajGuard</dd><dt>核心指标</dt><dd>首次偏离稳定性 · 下游轨迹恢复 · DSR · XSTest 误拒率 · Just-Eval 保持率 · 延迟开销</dd></dl>
      </section>

      <section class="evidence-artifact">
        <p class="artifact-kicker">代表性图表 · 轨迹首次偏离</p><h4>安全轨迹从哪一层开始发生变化</h4>
        ${projectedPanel({title:"图 2A · 安全轨迹的首次偏离位置",dataset:"AdvBench 50 + 意图匹配的风格改写",metric:"纵轴为安全轨迹偏离率，横轴为归一化网络深度",fields:"model_id · intent_id · style_id · layer_id · tube_exit",xLabel:"归一化网络深度",xs:["0.0","0.14","0.29","0.43","0.57","0.71","0.86","1.0"],series:["直接有害请求","风格改写后的有害请求"],image:"assets/expplan/F2_exit_depth.png"})}
      </section>

      ${resultTable({id:"代表性结果表",title:"安全性与可用性的统一比较",headers:["方法或条件","AdvBench DSR ↑（%，95% CI）","HarmBench DSR ↑（%，95% CI）","XSTest 误拒率 ↓（%，95% CI）","Just-Eval 保持率 ↑（%，95% CI）"],rows:methods,note:"所有方法使用相同的生成与评测设置重新运行，表中只接收本项目实际得到的结果。"})}

      <section class="plain-section claim-contract">
        <p class="artifact-kicker">主张与失败条件</p><h4>在实验前说明什么结果会推翻主张</h4>
        <div class="claim-rows"><div><b>C1</b><p>匹配意图的风格变换产生可复现的最早 safety-tube exit。</p><span>若 exit depth 跨 paraphrase、seed 或 model 不稳定，则失败。</span></div><div><b>C2</b><p>只修 first-exit layer 足以恢复下游安全几何并降低 harmful compliance。</p><span>若随机层、ABD 层、后续层或重复修复并列或更优，则失败。</span></div><div><b>C3</b><p>一次修复改善 safety–utility–cost frontier。</p><span>若 DSR 增益必须以更差的 XSTest、Just-Eval 或 latency 换取，则失败。</span></div></div>
      </section>

      <section class="plain-section implementation-section">
        <p class="artifact-kicker">实现方案</p><h4>所有方法在同一实验框架中比较</h4>
        <div class="table-scroll"><table class="implementation-table"><thead><tr><th>方法</th><th>采用的实现方式</th></tr></thead><tbody><tr><th>No Defense</th><td>复用统一生成流程，关闭所有防御。</td></tr><tr><th>ABD</th><td>在本地框架中实现安全边界估计、惩罚项和层选择，并复用统一的激活接口。</td></tr><tr><th>RTV</th><td>在本地框架中实现拒绝方向指纹与多层 Mahalanobis 轨迹评分。</td></tr><tr><th>JBShield</th><td>通过本地适配器接入官方的概念提取、评分、缓解和混合输入门控；<a href="https://github.com/NISPLab/JBShield" target="_blank" rel="noreferrer">查看官方代码</a>。</td></tr><tr><th>TrajGuard</th><td>在本地框架中实现滑动窗口隐状态聚合、持续性阈值和语义判定。</td></tr><tr><th>本文方法：First-Divergence Repair</th><td>在同一模型、轨迹、生成和评测接口上实现首次偏离定位、单次修复与下游恢复。</td></tr></tbody></table></div>
      </section>

      <section class="plain-section">
        <p class="artifact-kicker">预算与决策标准</p><h4>提前确定资源上限和停止条件</h4>
        <p>预算为 4×A100、约 428 GPU 小时；先验证首次偏离现象，再冻结阈值与修复强度。进入最终实验后不再调参；任一关键失败条件成立时，收窄或放弃对应主张。</p>
      </section>

      <section class="approval-line"><strong>方案确认</strong><span>已确认 · 2026-08-09</span><p>研究者确认图表、待测结果、预算和判断标准；如果证据不支持，就收窄或放弃相应主张。</p></section>
    </article>`;
};

let runPlanDemoState = null;

const runStatusMark = status => ({completed:"✅",running:"▶",proposed:"→",locked:"○",pending:"○",blocked:"⚠",invalidated:"⚠"}[status] || "○");

const publicPartTitles = {
  P1: "基础通路验证",
  P2: "关键现象验证",
  P5: "主结果验证",
};

const publicArtifactLabels = {
  F1: "图 1",
  F2: "图 2",
  T1: "表 1",
};

const currentGoalPanel = goal => `<div class="demo-current-goal" data-demo-current-goal="${escapeHtml(goal.id)}">
  <p class="artifact-kicker">当前任务 · ${escapeHtml(goal.id)}</p>
  <h5>${escapeHtml(goal.title)}</h5>
  <pre>${escapeHtml(goal.goal_command)}</pre>
  <button type="button" data-copy="${escapeHtml(goal.goal_command)}">复制 /goal</button>
  <dl><dt>预期产出</dt><dd>${(goal.outputs || []).map(escapeHtml).join(" · ")}</dd><dt>所需资源</dt><dd>${escapeHtml(goal.budget)}</dd><dt>完成标准</dt><dd>${escapeHtml(goal.completion_check)}</dd></dl>
</div>`;

const goalHierarchy = () => {
  if (!runPlanDemoState) return `<section class="goal-hierarchy"><p>实验计划暂时无法加载。</p></section>`;
  const goals = Object.fromEntries(runPlanDemoState.goals.map(goal => [goal.id, goal]));
  const currentId = runPlanDemoState.active_goal || runPlanDemoState.proposed_goal_id;
  const completed = runPlanDemoState.goals.filter(goal => goal.status === "completed").length;
  const representativeGoalIds = [currentId, "G2.1", "G5.1"].filter((id, index, ids) => id && goals[id] && ids.indexOf(id) === index);
  const representativeParts = representativeGoalIds.map(goalId => {
    const goal = goals[goalId];
    const part = runPlanDemoState.parts.find(item => item.id === goal.part_id);
    return {part, goal};
  });
  return `<section class="goal-hierarchy"><p class="artifact-kicker">实验进度示例</p><p class="runplan-demo-note">这里选取当前任务、下一阶段和主结果三个里程碑，展示任务如何逐步解锁，以及完成后数据表和图如何回到对应任务中。</p>${representativeParts.map(({part, goal}) => {
    const destination = goal.artifact_ids?.length ? goal.artifact_ids.map(id => publicArtifactLabels[id] || id).join("、") : "本任务不直接更新图表";
    const completedExample = goal.id === "G2.1";
    return `<div class="part-row"><h4><span>${escapeHtml(part.id.replace("P", "阶段 "))}</span>${escapeHtml(publicPartTitles[part.id] || part.title)}</h4><p class="part-decision">${escapeHtml(part.decision)}</p><div class="expanded-goal ${completedExample ? "demo-completed-goal" : ""}"><b>${completedExample ? "✅" : runStatusMark(goal.status)}</b><strong>${escapeHtml(goal.id)} · ${escapeHtml(goal.title)}${completedExample ? '<small>完成效果示例</small>' : ""}</strong><span>对应论文内容：${escapeHtml(destination)}</span><p>${escapeHtml(goal.visible_work)} ${escapeHtml(goal.visible_evidence)} 完成标准：${escapeHtml(goal.completion_check)}</p>${goal.id === currentId ? currentGoalPanel(goal) : ""}${completedExample ? resultProvenanceDemo() : ""}</div></div>`;
  }).join("")}</section>`;
};

const completedF2Rows = [
  ["0.00", 0.04, 0.06], ["0.14", 0.05, 0.11], ["0.29", 0.08, 0.26], ["0.43", 0.13, 0.47],
  ["0.57", 0.19, 0.68], ["0.71", 0.25, 0.79], ["0.86", 0.29, 0.84], ["1.00", 0.32, 0.86]
];

const provenanceNumber = (value, depth, series) => `<span class="provenance-number" tabindex="0">${value.toFixed(2)}<span class="provenance-tooltip" role="tooltip"><b>演示数值 · 非科学结果</b><span><strong>任务</strong> G2.1</span><span><strong>数据切片</strong> depth=${depth} · ${series}</span><span><strong>原始记录</strong> results/demo/g2_1/raw_trace.jsonl</span><span><strong>筛选条件</strong> approved model + matched intent/style IDs</span><span><strong>计算公式</strong> sum(tube_exit) / valid records = ${value.toFixed(4)}</span><span><strong>运行命令</strong> python -m code.first_divergence.acquire --goal G2.1</span><span><strong>验证</strong> ledger schema, config digest, rerun match, source path reopen</span></span></span>`;

const completedF2Chart = () => {
  const points = column => completedF2Rows.map((row, index) => `${54 + index * 61},${202 - row[column] * 170}`).join(" ");
  return `<figure class="completed-chart"><svg viewBox="0 0 520 245" role="img" aria-label="Demo F2A safety tube exit rate chart"><g class="chart-grid"><line x1="54" y1="32" x2="481" y2="32"/><line x1="54" y1="117" x2="481" y2="117"/><line x1="54" y1="202" x2="481" y2="202"/></g><g class="chart-axis"><line x1="54" y1="25" x2="54" y2="202"/><line x1="54" y1="202" x2="486" y2="202"/></g><g class="chart-labels"><text x="18" y="36">1.0</text><text x="18" y="121">0.5</text><text x="18" y="206">0.0</text><text x="51" y="224">0.0</text><text x="256" y="224">depth</text><text x="466" y="224">1.0</text></g><polyline class="series-direct" points="${points(1)}"/><polyline class="series-style" points="${points(2)}"/>${completedF2Rows.map((row,index) => `<circle class="point-direct" cx="${54 + index * 61}" cy="${202 - row[1] * 170}" r="3.5"/><circle class="point-style" cx="${54 + index * 61}" cy="${202 - row[2] * 170}" r="3.5"/>`).join("")}<g class="chart-legend"><line x1="286" y1="18" x2="309" y2="18" class="series-direct"/><text x="315" y="22">Direct harmful</text><line x1="397" y1="18" x2="420" y2="18" class="series-style"/><text x="426" y="22">Styled</text></g></svg><figcaption>由左侧同一张数字源表生成；没有独立的 plot-only 数据源。</figcaption></figure>`;
};

const resultProvenanceDemo = () => `
  <section class="evidence-artifact completed-result future-result-example"><p class="artifact-kicker">完成后的结果示例</p><h4>首次偏离率随网络深度的变化</h4>
    <div class="simulated-run-summary"><strong>✅ 演示运行已完成</strong><span>16 个数据点全部核验</span><span>原始记录可重新打开</span><span>图形可重新生成</span></div>
    <p>以下数据用于演示任务完成后的呈现方式，并非当前研究结论。每个数字都能查看来源、计算公式和运行命令。</p>
    <div class="provenance-flow"><span>原始记录</span><i>→</i><span>结果核验</span><i>→</i><span>指标计算</span><i>→</i><span>填入数据表</span><i>→</i><span>生成图形</span></div>
    <div class="completed-result-grid"><div class="table-scroll"><table class="result-shell source-table completed-source"><thead><tr><th>Normalized depth</th><th>Direct harmful</th><th>Style-transformed harmful</th></tr></thead><tbody>${completedF2Rows.map(([depth,direct,styled]) => `<tr><th>${depth}</th><td>${provenanceNumber(direct,depth,"direct harmful")}</td><td>${provenanceNumber(styled,depth,"style-transformed harmful")}</td></tr>`).join("")}</tbody></table><p class="hover-instruction">鼠标停在任一数字上，或用键盘聚焦，即可查看 raw path、筛选、公式、命令与验证过程。</p></div>${completedF2Chart()}</div>
  </section>`;

const paperStudioScreenshots = () => `<section class="paper-studio-screenshots">
  <p class="artifact-kicker">论文写作工作区</p>
  <h4>正文、图片和表格在同一环境中完成</h4>
  <p>以下界面展示逐段写作、图片制作和表格编辑。右侧 PDF 会在内容确认后自动重新编译。</p>
  ${[
    ["writing.png", "逐段完善正文", "查看候选段落、提出修改意见，确认后写入 LaTeX 并更新右侧 PDF。", true],
    ["figures.png", "制作论文图片", "查看生成的构图方案，并继续整理为可编辑的 PPT 和论文 PDF。", false],
    ["tables.png", "编辑结果表格", "从已核验数据生成表格，调整 LaTeX 和正文位置后再确认插入。", false],
  ].map(([file, title, caption, isWriting]) => `<figure><img src="assets/paper-studio/${file}?v=20260814-reader-copy" alt="Paper Studio ${title}界面" loading="lazy"><figcaption><div><strong>${title}</strong><span>${caption}</span></div>${isWriting ? `<aside class="writing-api-note"><b>正文由 LLM API 写作</b><span>不是 Code Agent 生成正文</span></aside>` : ""}</figcaption></figure>`).join("")}
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
      <div class="stage-head"><div><p class="eyebrow">第二步 · 文献调研</p><h3>把相关工作整理成可核验的研究地图</h3><p>从不同角度检索并核对论文，梳理主要方向、争议和仍待解决的问题。</p></div><span class="status-pill">54 篇已核验</span></div>
      ${commandStrip("整理并核验相关文献", "$researchlit stylish jailbreak")}
      ${reportDocument("literature")}`
  },
  {
    id: "ideas", short: "方向选择", path: "ideas", title: "候选先过门槛，再由研究者选择",
    compare: ["通常用排序快速呈现候选方向", "研究者再判断价值与新颖性", "把新颖性与可证伪性设为独立硬门槛"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第三步 · 研究方向</p><h3>比较候选方向，明确新颖性与风险</h3><p>每个方向都说明研究空白、核心机制、可证伪条件和最近工作的重合程度，最后由研究者选择。</p></div><span class="status-pill">待研究者选择</span></div>
      ${commandStrip("生成候选方向并逐一核验", "$ideagen")}
      ${reportDocument("ideas")}`
  },
  {
    id: "expplan", short: "实验设计", path: "experiment-plan", title: "先明确证据需求，再设计实验",
    compare: null,
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第四步 · 实验设计</p><h3>从论文主张反推实验和证据</h3><p>先明确论文需要回答的问题，再为每个主张安排数据、基线、指标、图表和失败条件。</p></div><span class="status-pill">方案已确认</span></div>
      ${commandStrip("生成实验设计与待填图表", "$expplan")}
      ${experimentPlanDemo()}`
  },
  {
    id: "runplan", short: "实验执行", path: "run-plan", title: "把实验拆成一个个 Goal，完成一个再继续下一个",
    compare: ["强调连续自主探索与整体吞吐", "适合可自动判分的大规模搜索", "每个 Goal 落盘、验证、填表、打勾，再解锁下一项"],
    render: () => {
      const currentId = runPlanDemoState?.active_goal || runPlanDemoState?.proposed_goal_id || "NONE";
      return `
      <div class="stage-head"><div><p class="eyebrow">第五步 · 实验执行</p><h3>把实验拆成一个个 Goal，逐项完成</h3><p>每个 Goal 都有明确的任务、完成标准和对应图表；完成并核验一个后，再继续下一个。</p></div><span class="status-pill">${escapeHtml(currentId)} ${runPlanDemoState?.active_goal ? "执行中" : "可开始"}</span></div>
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
      fetch("report-structures.json?v=20260814-reader-copy"),
      fetch("runplan-state.json?v=20260814-reader-copy")
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
