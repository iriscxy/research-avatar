const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));

const commandStrip = (title, command, detail = "生成结果会同步到网页。") => `
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

const projectedPaperExample = () => `
  <section class="workflow-example" data-demo-example="projected-f2">
    <p class="artifact-kicker">具体例子 · Projected Paper</p>
    <h4>参照结构论文规划写作逻辑，再为 Introduction 的图 2 保留待填证据</h4>
    <div class="reference-writing-contract">
      <b>结构参考 · Ref Paper</b>
      <span>下面逐项给出 Ref Paper 段落位置与目标论文段落的对应关系；只迁移论证功能与图表节奏，不迁移研究内容、数据或结论。</span>
    </div>
    <div class="paper-structure-flow" aria-label="预期论文结构">
      <div><b>Ref Paper · §1 P3</b><em>失败现象 → 研究缺口</em><span>目标论文 · Introduction I-P3：提出固定目标组合导致训练波动。</span><strong>目标证据 · F2</strong></div>
      <i>→</i><div><b>Ref Paper · §3.1</b><em>按问题顺序展开方法</em><span>目标论文 · Method M-P1–P3：定义分阶段训练与自适应权重。</span><strong>目标证据 · F3</strong></div>
      <i>→</i><div><b>Ref Paper · §4.2–§4.3</b><em>主结果 → 消融</em><span>目标论文 · Experiments E-P2–P4：比较任务效果、效率与组件贡献。</span><strong>目标证据 · T1–T4</strong></div>
      <i>→</i><div><b>Ref Paper · §4.4</b><em>观察 → 解释 → 边界</em><span>目标论文 · Analysis A-P1–P3：分析人评、权重变化和失败案例。</span><strong>目标证据 · F4–F5</strong></div>
    </div>
    <div class="figure-data-pair projected-example-pair">
      <div class="numeric-source">
        <h5>F2 待填数据表</h5>
        <div class="table-scroll"><table class="source-table projected-f2-table"><thead><tr><th>Objective</th><th>Metric</th><th>Statistic</th><th>Value</th></tr></thead><tbody>
          <tr><th>Reasoning only</th><td>Reasoning accuracy</td><td>Average std</td><td class="demo-pending">待实验</td></tr>
          <tr><th>Rsn+Gen</th><td>Reasoning accuracy</td><td>Average std</td><td class="demo-pending">待实验</td></tr>
          <tr><th>Generation only</th><td>Response quality</td><td>Std range</td><td class="demo-pending">待实验</td></tr>
          <tr><th>Rsn+Gen</th><td>Response quality</td><td>Std range</td><td class="demo-pending">待实验</td></tr>
        </tbody></table></div>
        <p class="field-line">预先固定：训练目标、指标、统计量、数值与来源定位；结果生成前不允许补造。</p>
      </div>
      <figure class="blank-chart projected-chart" aria-label="图 2 待填图">
        <span class="blank-axis blank-x"></span><span class="blank-axis blank-y"></span>
        <strong>F2 · Training dynamics</strong><span>等待左侧数据合同完成后自动绘图</span>
      </figure>
    </div>
  </section>`;

const provenanceValue = (value, locator, calculation) => `
  <a class="provenance-number" href="#run-plan" data-provenance-target="demo-f2-provenance">
    ${escapeHtml(value)}
    <span class="provenance-tooltip"><b>点击查看得到过程</b><span><strong>来源：</strong>${escapeHtml(locator)}</span><span><strong>处理：</strong>${escapeHtml(calculation)}</span><span><strong>核验：</strong>两次定位核对 · VERIFIED</span></span>
  </a>`;

const completedExperimentExample = () => `
  <section class="workflow-example completed-example" data-demo-example="completed-f2">
    <p class="artifact-kicker">具体例子 · 已完成 Goal G1.1</p>
    <h4>同一张 F2 已填入数据，并由表格直接生成结果图</h4>
    <div class="completed-result-grid">
      <div class="table-scroll"><table class="source-table completed-source"><thead><tr><th>Objective</th><th>Metric</th><th>Statistic</th><th>Value</th></tr></thead><tbody>
        <tr><th>Reasoning only</th><td>Reasoning accuracy</td><td>Average std</td><td>${provenanceValue("0.030", "runs/G1.1/reasoning_only/metrics.jsonl", "汇总 3 个种子的 checkpoint 标准差后取平均")}</td></tr>
        <tr><th>Rsn+Gen</th><td>Reasoning accuracy</td><td>Average std</td><td>${provenanceValue("0.073", "runs/G1.1/joint/metrics.jsonl", "汇总 3 个种子的 checkpoint 标准差后取平均")}</td></tr>
        <tr><th>Reasoning only</th><td>Reasoning accuracy</td><td>Std range</td><td>${provenanceValue("0.02–0.04", "runs/G1.1/reasoning_only/metrics.jsonl", "读取各随机种子的最小值与最大值")}</td></tr>
        <tr><th>Rsn+Gen</th><td>Reasoning accuracy</td><td>Std range</td><td>${provenanceValue("0.07–0.08", "runs/G1.1/joint/metrics.jsonl", "读取各随机种子的最小值与最大值")}</td></tr>
        <tr><th>Generation only</th><td>Response quality</td><td>Std range</td><td>${provenanceValue("0.06–0.07", "runs/G1.1/generation_only/metrics.jsonl", "读取各随机种子的最小值与最大值")}</td></tr>
        <tr><th>Rsn+Gen</th><td>Response quality</td><td>Std range</td><td>${provenanceValue("0.11–0.13", "runs/G1.1/joint/metrics.jsonl", "读取各随机种子的最小值与最大值")}</td></tr>
      </tbody></table></div>
      <figure class="completed-chart" aria-label="图 2 已完成的训练波动结果">
        <svg viewBox="0 0 560 330" role="img" aria-label="四个训练目标的标准差范围">
          <g class="chart-grid"><line x1="145" y1="55" x2="515" y2="55"/><line x1="145" y1="115" x2="515" y2="115"/><line x1="145" y1="175" x2="515" y2="175"/><line x1="145" y1="235" x2="515" y2="235"/></g>
          <g class="chart-axis"><line x1="145" y1="270" x2="515" y2="270"/><line x1="145" y1="35" x2="145" y2="270"/></g>
          <g class="chart-labels"><text x="10" y="59">Reasoning only</text><text x="64" y="119">Rsn+Gen</text><text x="20" y="179">Generation only</text><text x="64" y="239">Rsn+Gen</text><text x="140" y="292">0.00</text><text x="268" y="292">0.05</text><text x="400" y="292">0.10</text><text x="500" y="292">0.14</text></g>
          <g stroke="#203f4d" stroke-width="8" stroke-linecap="round"><line x1="198" y1="55" x2="251" y2="55"/><line x1="330" y1="115" x2="356" y2="115"/></g>
          <g stroke="#0a8a78" stroke-width="8" stroke-linecap="round"><line x1="303" y1="175" x2="330" y2="175"/><line x1="435" y1="235" x2="488" y2="235"/></g>
          <g fill="#fff" stroke="#203f4d" stroke-width="4"><circle cx="224" cy="55" r="7"/><circle cx="338" cy="115" r="7"/></g>
        </svg>
        <figcaption>F2 · 表中范围决定线段，精确平均值决定圆点；没有公开的 checkpoint 数组不被伪造。</figcaption>
      </figure>
    </div>
    <p class="hover-instruction">每个绿色数值都是证据链接：悬停可预览来源与处理方式，点击可打开完整得到过程。</p>
    <details id="demo-f2-provenance" class="provenance-card">
      <summary>F2 数值的完整得到过程</summary>
      <dl><dt>执行 Goal</dt><dd>G1.1 · 采集训练动态</dd><dt>原始数据</dt><dd>三个随机种子的结构化训练日志</dd><dt>定位</dt><dd>runs/G1.1/&lt;condition&gt;/metrics.jsonl</dd><dt>获取方式</dt><dd>Code Agent 读取每个 checkpoint 的指标并写入结构化 F2 数据表</dd><dt>计算规则</dt><dd>先按种子计算波动，再汇总平均值与范围；不从图形反推数据</dd><dt>图形生成</dt><dd>读取当前表格序列化值：范围→线段，平均值→圆点</dd><dt>验证状态</dt><dd><span class="verified-mark">VERIFIED · 数据行数、种子数与聚合结果核对通过</span></dd></dl>
    </details>
  </section>`;

const resultTable = ({ id, title, headers, rows, note }) => `
  <section class="evidence-artifact result-table-artifact">
    <p class="artifact-kicker">${id} · 等待实验结果</p>
    <h4>${title}</h4>
    ${pendingTable({headers,rows,className:"main-result"})}
    <p>${note}</p>
  </section>`;

let runPlanDemoState = null;

const runStatusMark = status => ({completed:"✅",running:"▶",proposed:"→",locked:"○",pending:"○",blocked:"⚠",invalidated:"⚠"}[status] || "○");

const publicPartTitles = {
  P1: "来源与重建政策",
  P2: "离线比较证据",
  P3: "线上 A/B 证据",
  P4: "组件消融证据",
  P5: "人评、权重与案例图",
};

const publicArtifactLabels = {
  F1: "图 1",
  F2: "图 2",
  F3: "图 3",
  F4: "图 4",
  F5: "图 5",
  T1: "表 1",
  T2: "表 2",
  T3: "表 3",
  T4: "表 4",
};

const runPlanTraceMap = () => {
  if (!runPlanDemoState) return "";
  const artifacts = goal => goal?.artifact_ids?.map(id => publicArtifactLabels[id] || id).join("、") || "无";
  const goalMap = runPlanDemoState.goals.map(goal => `${goal.id} → ${artifacts(goal)}`).join("；");
  const partMap = runPlanDemoState.parts.map(part => `${part.id} → ${(part.goals || []).join("、")}`).join("；");
  return `<section class="runplan-trace-map" aria-label="执行计划四部分与实验任务的对应关系">
    <div class="trace-map-head"><p class="artifact-kicker">从计划到执行</p><h4>上方 1–4 如何落实到下面的实验任务</h4><p>1–3 定义每项任务必须遵守的资源、实现和图表合同；第 4 部分给出任务层级。下方任务卡是这四部分的可执行展开，不是另一套计划。</p></div>
    <div class="trace-map-grid">
      <div><b>1 · 资源与时间估算</b><span>约束证据获取与原论文训练成本</span><strong>6 项证据任务已完成；论文训练披露为 8 张 GPU、约 47 小时。</strong></div>
      <div><b>2 · 实现来源</b><span>规定精确复用和图形重建的边界</span><strong>表格逐格核对论文数值；曲线与案例图明确标记近似或定性重建。</strong></div>
      <div><b>3 · 图表与任务对应</b><span>规定每项任务完成后回填什么论文证据</span><strong>${escapeHtml(goalMap)}</strong></div>
      <div><b>4 · 阶段与任务</b><span>把前三项约束组织成依赖有序的执行单元</span><strong>${escapeHtml(partMap)}</strong></div>
    </div>
    <div class="trace-map-arrow"><span>上方执行合同</span><i>↓</i><strong>下方六张任务卡逐项执行并核验</strong></div>
  </section>`;
};

const executionModePanel = goal => `<div class="demo-current-goal execution-mode-panel" data-demo-current-goal="${escapeHtml(goal.id)}">
  <p class="artifact-kicker">任务确认</p>
  <h5>选择执行方式</h5>
  <div class="execution-mode-options">
    <div class="selected"><b>一次确认全部任务</b><span>系统按依赖顺序执行，并分别保存和核验结果。</span></div>
    <div><b>逐项确认</b><span>每项任务开始前查看产出和完成标准。</span></div>
  </div>
  <p class="execution-stop-rule">遇到验证失败、预算耗尽或需要新的研究判断时，自动执行会立即停止。</p>
  <dl><dt>下一项任务</dt><dd>${escapeHtml(goal.id)} · ${escapeHtml(goal.title)}</dd><dt>预期产出</dt><dd>${(goal.outputs || []).map(escapeHtml).join(" · ")}</dd><dt>完成标准</dt><dd>${escapeHtml(goal.completion_check)}</dd></dl>
</div>`;

const goalHierarchy = () => {
  if (!runPlanDemoState) return `<section class="goal-hierarchy"><p>实验计划暂时无法加载。</p></section>`;
  const goals = Object.fromEntries(runPlanDemoState.goals.map(goal => [goal.id, goal]));
  const currentId = runPlanDemoState.active_goal || runPlanDemoState.proposed_goal_id;
  const completed = runPlanDemoState.goals.filter(goal => goal.status === "completed").length;
  const representativeGoalIds = runPlanDemoState.goals.map(goal => goal.id);
  const representativeParts = representativeGoalIds.map(goalId => {
    const goal = goals[goalId];
    const part = runPlanDemoState.parts.find(item => item.id === goal.part_id);
    return {part, goal};
  });
  return `<section class="goal-hierarchy"><p class="artifact-kicker">实验任务</p><p class="runplan-demo-note">六项任务依次核验来源、离线比较、线上 A/B、组件消融以及人评与案例图。当前 ${completed}/${runPlanDemoState.goals.length} 项已完成。</p>${representativeParts.map(({part, goal}) => {
    const destination = goal.artifact_ids?.length ? goal.artifact_ids.map(id => publicArtifactLabels[id] || id).join("、") : "本任务不直接更新图表";
    return `<div class="part-row"><h4><span>${escapeHtml(part.id.replace("P", "阶段 "))}</span>${escapeHtml(publicPartTitles[part.id] || part.title)}</h4><p class="part-decision">${escapeHtml(part.decision)}</p><div class="expanded-goal"><b>${runStatusMark(goal.status)}</b><strong>${escapeHtml(goal.id)} · ${escapeHtml(goal.title)}</strong><span>对应论文内容：${escapeHtml(destination)}</span><p>${escapeHtml(goal.visible_work)} ${escapeHtml(goal.visible_evidence)} 完成标准：${escapeHtml(goal.completion_check)}</p>${goal.id === currentId ? executionModePanel(goal) : ""}</div></div>`;
  }).join("")}</section>`;
};

const paperStudioScreenshots = () => `<section class="paper-studio-live">
  <p class="artifact-kicker">论文写作工作区</p>
  <h4>Paper Studio</h4>
  <div class="paper-studio-frame-shell">
    <div class="paper-studio-frame-bar"><span>本地当前状态快照 · 只读，输入与写入操作均已锁定</span></div>
    <iframe src="/demo-studio/" title="Paper Studio 通用只读 Demo" loading="lazy"></iframe>
  </div>
</section>`;

let reportStructures = {};
let artifactManifest = {};

const publicReportTitles = {
  profile: "研究者画像",
  literature: "文献调研报告",
  ideas: "研究方向评估",
  expplan: "实验设计",
  runplan: "实验执行计划",
  results: "实验结果与证据",
  "paper-studio": "论文写作工作区",
};

const runPlanGoalExample = () => `<div class="goal-status-example" aria-label="Parts and Goals 执行状态示例">
  <div class="goal-status-legend"><span>✅ 已完成</span><span>▶ 执行中</span><span>❌ 未通过完成标准</span><span>○ 等待依赖</span></div>
  <ol>
    <li><span>Part 1</span><b>✅ G1.1 · 训练动态</b><em>F2 数据表与曲线已生成并核验</em></li>
    <li><span>Part 1</span><b>✅ G1.2 · 主结果比较</b><em>T1 已填入全部基线与置信区间</em></li>
    <li><span>Part 2</span><b>▶ G2.1 · 组件消融</b><em>3 组配置已完成 2 组</em></li>
    <li><span>Part 2</span><b>○ G2.2 · 稳健性检查</b><em>等待 G2.1 产出最佳配置</em></li>
    <li><span>Part 3</span><b>❌ G3.1 · 效率约束</b><em>延迟超过预设阈值，失败证据已保存</em></li>
    <li><span>Part 3</span><b>○ G3.2 · 错误分析</b><em>等待前置结果完成后启动</em></li>
  </ol>
</div>`;

const reportDocument = key => {
  const report = reportStructures[key];
  if (!report) return "";
  return `<article class="report-document" aria-label="${escapeHtml(report.artifact)}内容总结">
    <section class="report-structure-summary" aria-label="${escapeHtml(report.artifact)}结构总结">
      <p class="report-overview">${escapeHtml(report.note)}</p>
      <div class="report-section-grid">${report.sections.map(section => `<section data-structure-section="${escapeHtml(key)}:${escapeHtml(section.number)}">
        <div class="report-section-title"><span>${escapeHtml(section.number)}</span><h5>${escapeHtml(section.title)}</h5></div>
        <p>${escapeHtml(section.content)}</p>
        ${section.details?.length ? `<ul>${section.details.map(detail => `<li>${escapeHtml(detail)}</li>`).join("")}</ul>` : ""}
        ${key === "runplan" && String(section.number) === "4" ? runPlanGoalExample() : ""}
      </section>`).join("")}</div>
    </section>
  </article>`;
};

const canonicalArtifact = key => {
  const artifact = artifactManifest[key];
  const title = publicReportTitles[key] || reportStructures[key]?.artifact || key;
  return `<section class="canonical-artifact" data-canonical-artifact="${escapeHtml(key)}">
    <div class="canonical-artifact-head"><span>内容总结</span><strong>${escapeHtml(title)}</strong><small>${artifact?.source ? `对应本地 ${escapeHtml(artifact.source)}` : "对应本地 Research Studio 产物"}</small></div>
    ${reportDocument(key)}
  </section>`;
};

const stages = [
  {
    id: "profile", short: "研究画像", path: "profile", title: "先理解研究者，再开始研究",
    compare: ["以任务上下文和通用配置为主要起点", "适合快速进入自动探索", "先建立可检查的个性化依据"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第一步 · 研究者画像</p><h3>建立可复用的研究者画像</h3><p>从研究者提供的 Scholar 页面和本地写作样本中，整理研究方向、方法偏好、写作风格与实验习惯。</p></div><span class="status-pill">已完成</span></div>
      ${commandStrip("从本地 Scholar HTML 建立研究者画像", "$profileconstruct 使用 ~/Downloads/scholar_profile.html")}
      ${canonicalArtifact("profile")}`
  },
  {
    id: "literature", short: "文献调研", path: "literature", title: "用四步结构提炼可核验的文献地图",
    compare: ["一次返回大量论文、摘要和零散结论", "结果太多、太乱，方法类别、评测依据和真正的研究空白混在一起，很难直接用于判断。", "把核验过的证据归纳为 Problem → Approaches → Evaluation → Gaps：先界定问题，再分类方法、比较评测，最后推出研究空白，清晰、简洁、准确。"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第二步 · 文献调研</p><h3>把相关工作整理成可核验的研究地图</h3><p>从不同角度检索并核对论文，梳理主要方向、争议和仍待解决的问题。</p></div><span class="status-pill">52 篇已核验</span></div>
      ${commandStrip("整理并核验相关文献", "$researchlit <research topic>")}
      ${canonicalArtifact("literature")}`
  },
  {
    id: "ideas", short: "方向选择", path: "ideas", title: "候选先过门槛，再由研究者选择",
    compare: ["通常用排序快速呈现候选方向", "研究者再判断价值与新颖性", "把新颖性与可证伪性设为独立硬门槛"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第三步 · 研究方向</p><h3>比较候选方向，明确新颖性与风险</h3><p>每个方向都说明研究空白、核心机制、可证伪条件和最近工作的重合程度，最后由研究者选择。</p></div><span class="status-pill">I1 已选择</span></div>
      ${commandStrip("生成候选方向并逐一核验", "$ideagen")}
      ${canonicalArtifact("ideas")}`
  },
  {
    id: "expplan", short: "实验设计", path: "experiment-plan", title: "先明确论文主张，再反推所需实验",
    compare: ["先列实验清单，再根据结果补充论证", "容易出现实验很多、论文主张却没有被直接验证", "先确定论文要证明什么，再为每个主张安排图表、指标和失败条件"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第四步 · 实验设计</p><h3>从论文主张反推实验和证据</h3><p>先明确论文需要回答的问题，再为每个主张安排数据、基线、指标、图表和失败条件。</p></div><span class="status-pill">方案已确认</span></div>
      ${commandStrip("生成实验设计与待填图表", "$expplan")}
      ${canonicalArtifact("expplan")}
      ${projectedPaperExample()}`
  },
  {
    id: "runplan", short: "实验执行", path: "run-plan", title: "按证据依赖执行实验",
    compare: ["强调连续自主探索与整体吞吐", "执行过程通常缺少清晰的证据边界", "先展示全部任务，再一次确认或逐项确认"],
    render: () => {
      const currentId = runPlanDemoState?.active_goal || runPlanDemoState?.proposed_goal_id || "NONE";
      const allGoalsConfirmed = runPlanDemoState?.goal_confirmation?.scope === "all_goals";
      return `
      <div class="stage-head"><div><p class="eyebrow">第五步 · 实验执行</p><h3>按证据依赖执行实验</h3><p>每项任务都明确依赖、产出、完成标准和对应图表，可一次确认或逐项确认。</p></div><span class="status-pill">${allGoalsConfirmed ? "全部任务已确认" : `${escapeHtml(currentId)} 等待确认`}</span></div>
      ${canonicalArtifact("runplan")}
      ${completedExperimentExample()}`;
    }
  },
  {
    id: "paper", short: "论文写作", path: "paper-writing", title: "逐段写作、实时编译、图表可编辑",
    compare: ["倾向批量生成 Markdown 或 LaTeX 草稿", "适合快速获得整体版本", "正文调用 LLM API（不是 Code Agent）逐段生成；确认接受后才写入 LaTeX 并实时编译"],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第六步 · 论文写作</p><h3>撰写正文并制作图表</h3><p>正文、图表、LaTeX 与论文 PDF 在同一工作区同步更新。</p></div><span class="status-pill">20/26 段 · 进行中</span></div>
      ${paperStudioScreenshots()}`
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
  document.body.classList.toggle("paper-focus", stage.id === "paper");
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
  const provenanceLink = event.target.closest("[data-provenance-target]");
  if (provenanceLink) {
    event.preventDefault();
    const target = document.getElementById(provenanceLink.dataset.provenanceTarget);
    if (target) {
      target.open = true;
      target.classList.add("is-open");
      target.scrollIntoView({behavior:"smooth", block:"center"});
      target.querySelector("summary")?.focus();
    }
    return;
  }
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
    const [structureResponse, runPlanResponse, artifactResponse] = await Promise.all([
      fetch("report-structures.json?v=20260822-generic-workflow"),
      fetch("runplan-state.json?v=20260822-generic-workflow"),
      fetch("artifact-manifest.json?v=20260822-canonical-artifacts")
    ]);
    if (!structureResponse.ok) throw new Error(`report structures HTTP ${structureResponse.status}`);
    if (!runPlanResponse.ok) throw new Error(`run plan snapshot HTTP ${runPlanResponse.status}`);
    if (!artifactResponse.ok) throw new Error(`artifact manifest HTTP ${artifactResponse.status}`);
    reportStructures = await structureResponse.json();
    runPlanDemoState = await runPlanResponse.json();
    artifactManifest = await artifactResponse.json();
    state.stage = stageIndexFromLocation();
    renderStage();
  } catch (error) {
    content.innerHTML = `<div class="demo-load-error"><strong>页面内容暂时无法加载。</strong><span>${String(error)}</span></div>`;
  }
}

initializeDemo();
