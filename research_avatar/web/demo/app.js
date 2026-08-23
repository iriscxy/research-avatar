const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const requestedLanguage = new URLSearchParams(window.location.search).get("lang");
const uiLanguage = requestedLanguage === "en" ? "en" : "zh";
const t = (zh, en) => uiLanguage === "en" ? en : zh;
document.documentElement.lang = uiLanguage === "en" ? "en" : "zh-CN";
if (requestedLanguage) localStorage.setItem("research-avatar-language", uiLanguage);
document.querySelector("#demo-label").textContent = t("产品演示", "Product demo");
document.querySelector("#demo-language-label").textContent = t("界面语言", "Interface language");
document.querySelector("#demo-language-select").value = uiLanguage;
document.querySelector("#demo-language-select").addEventListener("change", event => {
  const language = event.target.value === "en" ? "en" : "zh";
  localStorage.setItem("research-avatar-language", language);
  if (window.parent !== window) {
    window.parent.postMessage({type: "research-avatar-language", language}, window.location.origin);
  }
  const url = new URL(window.location.href);
  url.searchParams.set("lang", language);
  window.location.assign(url.toString());
});

const demoTranslations = new Map(Object.entries({
  "第一步 · 研究者画像":"Step 1 · Researcher profile", "建立可复用的研究者画像":"Build a reusable researcher profile",
  "从研究者提供的 Scholar 页面和本地写作样本中，整理研究方向、方法偏好、写作风格与实验习惯。":"Extract research directions, method preferences, writing style, and experimental habits from the supplied Scholar page and local writing samples.",
  "已完成":"Completed", "从本地 Scholar HTML 建立研究者画像":"Build a profile from local Scholar HTML",
  "第二步 · 文献调研":"Step 2 · Literature survey", "把相关工作整理成可核验的研究地图":"Organize related work into a verifiable research map",
  "从不同角度检索并核对论文，梳理主要方向、争议和仍待解决的问题。":"Retrieve and verify papers from multiple angles to identify major directions, disputes, and open problems.",
  "52 篇已核验":"52 papers verified", "整理并核验相关文献":"Survey and verify related literature",
  "第三步 · 研究方向":"Step 3 · Research ideas", "比较候选方向，明确新颖性与风险":"Compare candidate directions, novelty, and risk",
  "每个方向都说明研究空白、核心机制、可证伪条件和最近工作的重合程度，最后由研究者选择。":"Each direction states its gap, mechanism, falsifier, and overlap with recent work; the researcher makes the final choice.",
  "I1 已选择":"I1 selected", "生成候选方向并逐一核验":"Generate and verify candidate directions",
  "第四步 · 实验设计":"Step 4 · Experiment plan", "从论文主张反推实验和证据":"Derive experiments and evidence from paper claims",
  "先明确论文需要回答的问题，再为每个主张安排数据、基线、指标、图表和失败条件。":"Define the paper questions first, then assign data, baselines, metrics, artifacts, and failure conditions to each claim.",
  "方案已确认":"Plan approved", "生成实验设计与待填图表":"Generate the experiment plan and fillable artifacts",
  "第五步 · 实验执行":"Step 5 · Experiment execution", "按证据依赖执行实验":"Execute experiments by evidence dependency",
  "每项任务都明确依赖、产出、完成标准和对应图表，可一次确认或逐项确认。":"Each task specifies dependencies, outputs, completion criteria, and target artifacts, with batch or per-task approval.",
  "全部任务已确认":"All tasks approved", "第六步 · 论文写作":"Step 6 · Paper writing", "撰写正文并制作图表":"Write the manuscript and build its figures",
  "正文、图表、LaTeX 与论文 PDF 在同一工作区同步更新。":"Prose, figures, LaTeX, and the paper PDF stay synchronized in one workspace.",
  "19/19 段 · 草稿已生成":"19/19 paragraphs · draft generated", "论文写作工作区":"Paper-writing workspace",
  "本地当前状态快照 · 只读，输入与写入操作均已锁定":"Current local snapshot · read-only; input and write actions are disabled",
  "Projected Paper · 结构对应":"Projected Paper · Structure mapping", "参考论文各部分均对应到 Rough Paper":"Every reference-paper section maps to the rough paper",
  "结构参考 · Ref Paper":"Structure reference · Ref Paper", "全部 Section 的对应关系":"All section mappings", "两个段落示例":"Two paragraph examples",
  "查看参考论文中的对应写法":"View the corresponding writing move in the reference paper", "具体图表示例：用横纵坐标表生成一条结果曲线":"Artifact example: generate a result curve from x–y coordinates",
  "F2 待填坐标表":"F2 fillable coordinate table", "横坐标 x · 纳入的随机排列数量":"x · Number of random permutations included",
  "纵坐标 y · 答案始终一致的题目比例":"y · Proportion of questions with a consistently identical answer", "待实验":"Pending",
  "每一行就是曲线上的一个点；实验完成后填入 y，右图按 x 的顺序连接。":"Each row is one curve point. After execution, fill y and connect the points in x order.",
  "等待左侧四个坐标点完成后自动绘图":"Automatically plotted after the four coordinates on the left are complete",
  "实验结果示例 · G4.1 已完成":"Experiment result example · G4.1 completed", "实验完成后，左侧四行坐标数据生成右侧答案一致率曲线":"After execution, the four coordinate rows generate the answer-consistency curve on the right",
  "每个绿色数值都是证据链接：悬停可预览来源与处理方式，点击可打开完整得到过程。":"Each green value is an evidence link: hover for provenance and processing, or click for the complete acquisition process.",
  "F2 数值的完整得到过程":"Complete acquisition process for F2", "执行进度":"Execution progress", "已完成":"completed",
  "纳入的随机排列数量":"Number of random permutations included", "始终一致的题目比例 (%)":"Consistently identical answers (%)",
  "F2 · x 表示除原始顺序外累计纳入多少个随机排列；y 表示在原始顺序及这些排列中始终给出同一语义答案的题目比例。":"F2 · x is the cumulative number of random permutations beyond the original order; y is the proportion of questions receiving the same semantic answer across the original order and all included permutations.",
  "先显示全部 Section 的覆盖关系，再展开两个段落示例。系统只迁移论证功能与图表节奏，不迁移研究内容、数据或结论。":"Show complete section coverage, then expand two paragraph examples. The system transfers argumentative function and artifact rhythm, never research content, data, or conclusions.",
  "本任务不直接更新图表":"This task does not directly update an artifact",
  "内容总结":"Content summary", "任务确认":"Task approval", "选择执行方式":"Choose an execution mode",
  "一次确认全部任务":"Approve all tasks once", "逐项确认":"Approve one task at a time", "下一项任务":"Next task", "预期产出":"Expected output", "完成标准":"Completion criterion"
}));

function translateDemoSubtree(root) {
  if (uiLanguage !== "en" || !root) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(node => {
    const trimmed = node.nodeValue.trim();
    if (!trimmed || !demoTranslations.has(trimmed)) return;
    node.nodeValue = node.nodeValue.replace(trimmed, demoTranslations.get(trimmed));
  });
}

const commandStrip = (title, command, detail = t("生成结果会同步到网页。", "Generated results are synchronized to this page.")) => `
  <div class="command-card">
    <div><span>${t("在本地终端运行", "Run in a local terminal")}</span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></div>
    <code>${escapeHtml(command)}</code><button type="button" data-copy="${escapeHtml(command)}">${t("复制命令", "Copy command")}</button>
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

const projectedPaperStructure = () => {
  const targetSectionLabel = section => ({
    Abstract: "摘要", Introduction: "引言", "Related Work": "相关工作",
    Method: "方法", Experiments: "实验", Discussion: "讨论", Conclusion: "结论",
  }[section] || section);
  const paragraphPlanLabel = plan => ({
    "Explain the closest unresolved gap and why existing approaches do not settle it.": "说明最接近但仍未解决的研究空白，以及现有方法为何不足以回答它。",
    "Introduce the planned main comparison, cite its bound table and data-figure placeholders, and use xx for every unavailable result without claiming an observed outcome.": "介绍计划中的主要比较，引用绑定的表格与数据图占位，并将所有尚未获得的结果写为 xx，不声称已经观察到结论。",
  }[plan] || plan);
  const sectionCoverage = [...expPlanParagraphMappings.reduce((groups, paragraph) => {
    if (!groups.has(paragraph.section)) groups.set(paragraph.section, []);
    groups.get(paragraph.section).push(paragraph);
    return groups;
  }, new Map()).entries()];
  const coverageMap = sectionCoverage.map(([targetSection, paragraphs]) => {
    const referenceSections = [...new Set(paragraphs.map(paragraph => paragraph.referenceHeading).filter(Boolean))];
    const firstId = paragraphs[0]?.id || "";
    const lastId = paragraphs.at(-1)?.id || "";
    const paragraphRange = firstId === lastId ? firstId : `${firstId}–${lastId}`;
    return `<li><span>${t("参考论文", "Ref Paper")} · ${escapeHtml(referenceSections.join(" / ") || t("对应章节", "corresponding section"))}</span><i>→</i><b>${t("论文初稿", "Rough Paper")} · ${escapeHtml(uiLanguage === "zh" ? targetSectionLabel(targetSection) : targetSection)} (${escapeHtml(paragraphRange)})</b></li>`;
  }).join("");
  const examplePrefixes = ["I-", "E-"];
  const examples = examplePrefixes.flatMap(prefix => {
    const candidates = expPlanParagraphMappings.filter(paragraph => paragraph.id.startsWith(prefix));
    return candidates.length ? [candidates[Math.floor((candidates.length - 1) / 2)]] : [];
  });
  const exampleMap = examples.map(paragraph => `
    <article class="paragraph-map-card">
      <header><b>${escapeHtml(uiLanguage === "zh" ? targetSectionLabel(paragraph.section) : paragraph.section)} · ${escapeHtml(paragraph.id)}</b><span>${escapeHtml(paragraph.referenceLabel || t("未绑定参考段落", "No reference paragraph linked"))}</span></header>
      <p>${escapeHtml(uiLanguage === "zh" ? paragraphPlanLabel(paragraph.plan) : paragraph.plan)}</p>
      <details>
        <summary>查看参考论文中的对应写法</summary>
        <p>${escapeHtml(paragraph.referenceBody || "该段落没有嵌入参考原文。")}</p>
        ${paragraph.logic ? `<small>${escapeHtml(paragraph.logic)}</small>` : ""}
      </details>
    </article>`).join("");
  return `
  <section class="workflow-example" data-demo-example="projected-f2">
    <p class="artifact-kicker">${t("预期论文 · 结构对应", "Projected Paper · Structure mapping")}</p>
    <h4>${t("参考论文各部分均对应到论文初稿", "Every reference-paper section maps to the rough paper")}</h4>
    <div class="reference-writing-contract">
      <b>${t("结构参考 · 参考论文", "Structure reference · Ref Paper")}</b>
      <span>${t("先显示全部章节的覆盖关系，再展开两个段落示例。系统只迁移论证功能与图表节奏，不迁移研究内容、数据或结论。", "Show complete section coverage, then expand two paragraph examples. The system transfers argumentative function and artifact rhythm, never research content, data, or conclusions.")}</span>
    </div>
    <div class="section-coverage-map"><h5>${t("全部章节的对应关系", "All section mappings")}</h5><ol>${coverageMap}</ol></div>
    <h5 class="paragraph-example-heading">两个段落示例</h5>
    <div class="paragraph-map-grid example-paragraph-map" aria-label="目标论文段落对应关系示例">${exampleMap || '<p class="demo-load-error">段落示例暂时无法读取。</p>'}</div>
    <h4 class="evidence-shell-heading">具体图表示例：用横纵坐标表生成一条结果曲线</h4>
    <div class="figure-data-pair projected-example-pair">
      <div class="numeric-source">
        <h5>F2 待填坐标表</h5>
        <div class="table-scroll"><table class="source-table projected-f2-table"><thead><tr><th>横坐标 x · 纳入的随机排列数量</th><th>纵坐标 y · 答案始终一致的题目比例</th></tr></thead><tbody>
          <tr><th>1</th><td class="demo-pending">待实验</td></tr>
          <tr><th>2</th><td class="demo-pending">待实验</td></tr>
          <tr><th>3</th><td class="demo-pending">待实验</td></tr>
          <tr><th>4</th><td class="demo-pending">待实验</td></tr>
        </tbody></table></div>
        <p class="field-line">每一行就是曲线上的一个点；实验完成后填入 y，右图按 x 的顺序连接。</p>
      </div>
      <figure class="blank-chart projected-chart" aria-label="图 2 待填图">
        <span class="blank-axis blank-x"></span><span class="blank-axis blank-y"></span>
        <strong>${t("F2 · 排列一致率", "F2 · Permutation consistency")}</strong><span>等待左侧四个坐标点完成后自动绘图</span>
      </figure>
    </div>
  </section>`;
};

const provenanceValue = (value, locator, calculation) => `
  <a class="provenance-number" href="#run-plan" data-provenance-target="demo-f2-provenance">
    ${escapeHtml(value)}
    <span class="provenance-tooltip"><b>点击查看完整实验过程</b><span><strong>命令：</strong>python code/run_option_permutations.py --config code/configs/option_order.json --output results/option_order</span><span><strong>运行文件：</strong>code/run_option_permutations.py</span><span><strong>来源：</strong>${escapeHtml(locator)}</span><span><strong>处理：</strong>${escapeHtml(calculation)}</span><span><strong>核验：</strong>运行清单、日志与数值均已核对</span></span>
  </a>`;

const completedExperimentExample = () => `
  <section class="workflow-example completed-example" data-demo-example="completed-f2">
    <p class="artifact-kicker">实验结果示例 · G4.1 已完成</p>
    <h4>实验完成后，左侧四行坐标数据生成右侧答案一致率曲线</h4>
    <div class="completed-result-grid">
      <div class="table-scroll"><table class="source-table completed-source coordinate-source"><thead><tr><th>横坐标 x · 纳入的随机排列数量</th><th>纵坐标 y · 答案始终一致的题目比例</th></tr></thead><tbody>
        <tr><th>1</th><td>${provenanceValue("94.0%", "results/option_order/G4.1/consistency_by_count.json · permutation_count=1", "读取 consistency_rate")}</td></tr>
        <tr><th>2</th><td>${provenanceValue("91.0%", "results/option_order/G4.1/consistency_by_count.json · permutation_count=2", "读取 consistency_rate")}</td></tr>
        <tr><th>3</th><td>${provenanceValue("89.0%", "results/option_order/G4.1/consistency_by_count.json · permutation_count=3", "读取 consistency_rate")}</td></tr>
        <tr><th>4</th><td>${provenanceValue("88.0%", "results/option_order/G4.1/consistency_by_count.json · permutation_count=4", "读取 consistency_rate")}</td></tr>
      </tbody></table></div>
      <figure class="completed-chart" aria-label="图 2 已完成的选项排列答案一致率曲线">
        <svg viewBox="0 0 560 330" role="img" aria-label="四个坐标点连接成的答案一致率曲线">
          <g class="chart-grid"><line x1="70" y1="55" x2="520" y2="55"/><line x1="70" y1="115" x2="520" y2="115"/><line x1="70" y1="175" x2="520" y2="175"/><line x1="70" y1="235" x2="520" y2="235"/></g>
          <g class="chart-axis"><line x1="70" y1="270" x2="520" y2="270"/><line x1="70" y1="35" x2="70" y2="270"/></g>
          <g class="chart-labels"><text x="31" y="274">85</text><text x="31" y="214">90</text><text x="31" y="154">95</text><text x="25" y="94">100</text><text x="66" y="294">1</text><text x="215" y="294">2</text><text x="365" y="294">3</text><text x="515" y="294">4</text><text x="202" y="319">纳入的随机排列数量</text><text x="8" y="22">始终一致的题目比例 (%)</text></g>
          <polyline class="series-style" points="70,127 220,163 370,187 520,199"/>
          <g class="point-style"><circle cx="70" cy="127" r="5"/><circle cx="220" cy="163" r="5"/><circle cx="370" cy="187" r="5"/><circle cx="520" cy="199" r="5"/></g>
        </svg>
        <figcaption>F2 · x 表示除原始顺序外累计纳入多少个随机排列；y 表示在原始顺序及这些排列中始终给出同一语义答案的题目比例。</figcaption>
      </figure>
    </div>
    <p class="hover-instruction">每个绿色数值都是证据链接：悬停可预览来源与处理方式，点击可打开完整得到过程。</p>
    <details id="demo-f2-provenance" class="provenance-card">
      <summary>F2 数值的完整得到过程</summary>
      <dl><dt>执行 Goal</dt><dd>G3.1 执行调用；G4.1 汇总曲线</dd><dt>实际命令</dt><dd>python code/run_option_permutations.py --config code/configs/option_order.json --output results/option_order</dd><dt>工作目录</dt><dd>项目根目录</dd><dt>运行文件</dt><dd>code/run_option_permutations.py</dd><dt>配置与输入</dt><dd>code/configs/option_order.json；data/questions.jsonl；data/permutations.jsonl</dd><dt>运行清单</dt><dd>results/option_order/run_manifest.json</dd><dt>标准输出 / 错误日志</dt><dd>results/option_order/stdout.log；results/option_order/stderr.log</dd><dt>原始输出</dt><dd>results/option_order/responses.jsonl</dd><dt>坐标数据</dt><dd>results/option_order/G4.1/consistency_by_count.json</dd><dt>计算规则</dt><dd>原始顺序始终作为基准；对 k=1–4，统计在原始顺序和前 k 个随机排列中语义答案始终一致的题目比例</dd><dt>图形生成</dt><dd>以随机排列数量 k 为 x、始终一致的题目比例为 y，连接四个点</dd><dt>验证状态</dt><dd><span class="verified-mark">VERIFIED · 命令退出状态、500 条响应、四行表格与四个图上点逐项核对</span></dd></dl>
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
  P1: t("冻结题目与排列协议", "Freeze questions and permutation protocol"),
  P2: t("生成并核验选项排列", "Generate and verify option permutations"),
  P3: t("执行 500 次模型调用", "Run 500 model calls"),
  P4: t("计算置换不变性指标", "Compute permutation-invariance metrics"),
  P5: t("稳健性与翻转案例分析", "Analyze robustness and answer flips"),
};

const publicArtifactLabels = {
  F1: t("图 1", "Figure 1"), F2: t("图 2", "Figure 2"),
  F3: t("图 3", "Figure 3"), F4: t("图 4", "Figure 4"), F5: t("图 5", "Figure 5"),
  T1: t("表 1", "Table 1"), T2: t("表 2", "Table 2"),
  T3: t("表 3", "Table 3"), T4: t("表 4", "Table 4"),
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
  const completed = runPlanDemoState.goals.filter(goal => goal.status === "completed").length;
  const representativeGoalIds = runPlanDemoState.goals.map(goal => goal.id);
  const representativeParts = representativeGoalIds.map(goalId => {
    const goal = goals[goalId];
    const part = runPlanDemoState.parts.find(item => item.id === goal.part_id);
    return {part, goal};
  });
  return `<section class="goal-hierarchy compact-goal-hierarchy"><div class="compact-goal-head"><b>执行进度</b><span>${completed}/${runPlanDemoState.goals.length} ${t("已完成", "completed")}</span></div><ol>${representativeParts.map(({part, goal}) => {
    const destination = goal.artifact_ids?.length ? goal.artifact_ids.map(id => publicArtifactLabels[id] || id).join(t("、", ", ")) : t("本任务不直接更新图表", "This task does not directly update an artifact");
    return `<li><span>${escapeHtml(part.id)}</span><b>${runStatusMark(goal.status)} ${escapeHtml(goal.id)} · ${escapeHtml(publicPartTitles[part.id] || goal.title)}</b><em>${escapeHtml(destination)}</em></li>`;
  }).join("")}</ol></section>`;
};

const paperStudioScreenshots = () => `<section class="paper-studio-live">
  <p class="artifact-kicker">论文写作工作区</p>
  <h4>Paper Studio</h4>
  <div class="paper-studio-frame-shell">
    <div class="paper-studio-frame-bar"><span>本地当前状态快照 · 只读，输入与写入操作均已锁定</span></div>
    <iframe src="/demo-studio/" title="Paper Studio read-only demo" loading="lazy"></iframe>
  </div>
</section>`;

let reportStructures = {};
let artifactManifest = {};
let expPlanParagraphMappings = [];

async function loadExpPlanParagraphMappings(artifact) {
  if (!artifact?.url) throw new Error("experiment plan artifact URL is missing");
  const response = await fetch(`${artifact.url}?v=${encodeURIComponent(artifact.sha256 || "current")}`);
  if (!response.ok) throw new Error(`experiment plan artifact HTTP ${response.status}`);
  // Report artifacts are standalone HTML documents and may contain an inline
  // <style> block. Parsing that block inside the hosted page triggers a CSP
  // violation even though this function only reads semantic report nodes.
  const reportSource = (await response.text()).replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "");
  const documentNode = new DOMParser().parseFromString(reportSource, "text/html");
  const structure = documentNode.querySelector('[data-report-subsection="projected-paper-structure"]');
  if (!structure) throw new Error("projected paper structure is missing from experiment plan");
  let section = "";
  const mappings = [];
  [...structure.children].forEach(node => {
    if (node.matches("h4")) {
      section = node.textContent.trim();
      return;
    }
    if (!node.matches(".paragraph")) return;
    const id = node.querySelector(":scope > b")?.textContent.trim() || "";
    const planNode = node.cloneNode(true);
    planNode.querySelectorAll("b, br, small, details").forEach(child => child.remove());
    const referenceParagraphs = node.querySelectorAll("details article > p");
    const referenceLabel = referenceParagraphs[0]?.textContent.trim() || "";
    mappings.push({
      section,
      id,
      plan: planNode.textContent.replace(/^\s*·\s*/, "").trim(),
      logic: node.querySelector(":scope > small")?.textContent.trim() || "",
      referenceLabel,
      referenceHeading: referenceLabel.split(" · ").slice(1).join(" · ").trim(),
      referenceBody: referenceParagraphs[1]?.textContent.trim() || "",
    });
  });
  if (!mappings.length) throw new Error("experiment plan contains no paragraph mappings");
  expPlanParagraphMappings = mappings;
}

const publicReportTitles = {
  profile: t("研究者画像", "Researcher Profile"),
  literature: t("文献调研报告", "Literature Survey"),
  ideas: t("研究方向评估", "Research-Idea Assessment"),
  expplan: t("实验设计", "Experiment Plan"),
  runplan: t("实验执行计划", "Experiment Execution Plan"),
  results: t("实验结果与证据", "Experiment Results and Evidence"),
  "paper-studio": t("论文写作工作区", "Paper-Writing Workspace"),
};

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
        ${key === "runplan" && String(section.number) === "4" ? goalHierarchy() : ""}
      </section>`).join("")}</div>
    </section>
  </article>`;
};

const canonicalArtifact = key => {
  const artifact = artifactManifest[key];
  const title = publicReportTitles[key] || reportStructures[key]?.artifact || key;
  return `<section class="canonical-artifact" data-canonical-artifact="${escapeHtml(key)}">
    <div class="canonical-artifact-head"><span>内容总结</span><strong>${escapeHtml(title)}</strong><small>${artifact?.source ? `${t("对应本地", "Local artifact:")} ${escapeHtml(artifact.source)}` : t("对应本地 Research Studio 产物", "Corresponding local Research Studio artifact")}</small></div>
    ${reportDocument(key)}
  </section>`;
};

const stages = [
  {
    id: "profile", short: t("研究画像", "Profile"), path: "profile", title: t("先理解研究者，再开始研究", "Understand the researcher before starting research"),
    compare: [t("以任务上下文和通用配置为主要起点", "Starts from task context and general configuration"), t("适合快速进入自动探索", "Useful for entering automated exploration quickly"), t("先建立可检查的个性化依据", "First establish inspectable personalization evidence")],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第一步 · 研究者画像</p><h3>建立可复用的研究者画像</h3><p>从研究者提供的 Scholar 页面和本地写作样本中，整理研究方向、方法偏好、写作风格与实验习惯。</p></div><span class="status-pill">已完成</span></div>
      ${commandStrip(t("从本地 Scholar HTML 建立研究者画像", "Build a profile from local Scholar HTML"), t("$profileconstruct 使用 ~/Downloads/scholar_profile.html", "$profileconstruct use ~/Downloads/scholar_profile.html"))}
      ${canonicalArtifact("profile")}`
  },
  {
    id: "literature", short: t("文献调研", "Literature"), path: "literature", title: t("用四步结构提炼可核验的文献地图", "Build a verifiable literature map in four steps"),
    compare: [t("一次返回大量论文、摘要和零散结论", "Returns many papers, abstracts, and disconnected findings at once"), t("结果太多、太乱，方法类别、评测依据和真正的研究空白混在一起，很难直接用于判断。", "Method families, evaluation evidence, and genuine gaps are mixed together, making decisions difficult."), t("把核验过的证据归纳为 Problem → Approaches → Evaluation → Gaps：先界定问题，再分类方法、比较评测，最后推出研究空白，清晰、简洁、准确。", "Organizes verified evidence as Problem → Approaches → Evaluation → Gaps for a concise, decision-ready field map.")],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第二步 · 文献调研</p><h3>把相关工作整理成可核验的研究地图</h3><p>从不同角度检索并核对论文，梳理主要方向、争议和仍待解决的问题。</p></div><span class="status-pill">52 篇已核验</span></div>
      ${commandStrip("整理并核验相关文献", "$researchlit <research topic>")}
      ${canonicalArtifact("literature")}`
  },
  {
    id: "ideas", short: t("方向选择", "Ideas"), path: "ideas", title: t("候选先过门槛，再由研究者选择", "Screen candidates before researcher selection"),
    compare: [t("通常用排序快速呈现候选方向", "Ranks candidate directions for quick review"), t("研究者再判断价值与新颖性", "The researcher then judges value and novelty"), t("把新颖性与可证伪性设为独立硬门槛", "Treats novelty and falsifiability as separate hard gates")],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第三步 · 研究方向</p><h3>比较候选方向，明确新颖性与风险</h3><p>每个方向都说明研究空白、核心机制、可证伪条件和最近工作的重合程度，最后由研究者选择。</p></div><span class="status-pill">I1 已选择</span></div>
      ${commandStrip("生成候选方向并逐一核验", "$ideagen")}
      ${canonicalArtifact("ideas")}`
  },
  {
    id: "expplan", short: t("实验设计", "Experiment plan"), path: "experiment-plan", title: t("先明确论文主张，再反推所需实验", "Derive experiments from the paper claims"),
    compare: [t("先列实验清单，再根据结果补充论证", "Lists experiments first and constructs the argument afterward"), t("容易出现实验很多、论文主张却没有被直接验证", "This can produce many experiments without directly testing the paper's claims."), t("先确定论文要证明什么，再为每个主张安排图表、指标和失败条件", "Defines what the paper must establish, then assigns artifacts, metrics, and failure conditions to each claim.")],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第四步 · 实验设计</p><h3>从论文主张反推实验和证据</h3><p>先明确论文需要回答的问题，再为每个主张安排数据、基线、指标、图表和失败条件。</p></div><span class="status-pill">方案已确认</span></div>
      ${commandStrip("生成实验设计与待填图表", "$expplan")}
      ${canonicalArtifact("expplan")}
      ${projectedPaperStructure()}`
  },
  {
    id: "runplan", short: t("实验执行", "Execution"), path: "run-plan", title: t("按证据依赖执行实验", "Execute experiments by evidence dependency"),
    compare: [t("强调连续自主探索与整体吞吐", "Emphasizes continuous autonomous exploration and throughput"), t("执行过程通常缺少清晰的证据边界", "Execution often lacks explicit evidence boundaries."), t("先展示全部任务，再一次确认或逐项确认", "Shows all tasks first, then supports batch or per-task approval.")],
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
    id: "paper", short: t("论文写作", "Writing"), path: "paper-writing", title: t("逐段写作、实时编译、图表可编辑", "Paragraph writing, live compilation, and editable figures"),
    compare: [t("倾向批量生成 Markdown 或 LaTeX 草稿", "Often generates a Markdown or LaTeX draft in one batch"), t("适合快速获得整体版本", "Useful for obtaining a complete draft quickly"), t("正文调用 LLM API（不是 Code Agent）逐段生成；确认接受后才写入 LaTeX 并实时编译", "Uses the LLM API paragraph by paragraph; accepted text is then written to LaTeX and compiled live.")],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">第六步 · 论文写作</p><h3>撰写正文并制作图表</h3><p>正文、图表、LaTeX 与论文 PDF 在同一工作区同步更新。</p></div><span class="status-pill">19/19 段 · 草稿已生成</span></div>
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
  comparePanel.innerHTML = stage.compare ? `<p class="eyebrow">${t("工作方式对比", "Workflow comparison")}</p><h4>${stage.short}${t("的工作重心", " focus")}</h4><div class="compare-card bad"><span>${t("常见自动化研究工具", "Typical automated research tools")}</span><strong>${stage.compare[0]}</strong><p>${stage.compare[1]}</p></div><div class="compare-card good"><span>Research Avatar</span><strong>${stage.title}</strong><p>${stage.compare[2]}</p></div>` : "";
}

function renderStage() {
  const stage = stages[state.stage];
  document.body.classList.toggle("paper-focus", stage.id === "paper");
  renderNav();
  path.textContent = `research-avatar-demo.pages.dev/${stage.path}`;
  content.innerHTML = stage.render();
  translateDemoSubtree(content);
  content.scrollTop = 0;
  renderCompare();
  translateDemoSubtree(comparePanel);
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
    button.textContent = t("已复制 ✓", "Copied ✓");
  } catch {
    const area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "");
    area.className = "clipboard-fallback";
    document.body.appendChild(area);
    area.focus();
    area.select();
    area.setSelectionRange(0, value.length);
    let copied = false;
    try { copied = document.execCommand("copy"); } catch {}
    area.remove();
    button.textContent = copied ? t("已复制 ✓", "Copied ✓") : t("请选中命令复制", "Select the command to copy");
  }
  setTimeout(() => { button.textContent = original; }, 1400);
});

async function initializeDemo() {
  try {
    const [structureResponse, runPlanResponse, artifactResponse] = await Promise.all([
      fetch(`${uiLanguage === "en" ? "report-structures.en.json" : "report-structures.json"}?v=20260823-bilingual`),
      fetch("runplan-state.json?v=20260822-generic-workflow"),
      fetch("artifact-manifest.json?v=20260822-canonical-artifacts")
    ]);
    if (!structureResponse.ok) throw new Error(`report structures HTTP ${structureResponse.status}`);
    if (!runPlanResponse.ok) throw new Error(`run plan snapshot HTTP ${runPlanResponse.status}`);
    if (!artifactResponse.ok) throw new Error(`artifact manifest HTTP ${artifactResponse.status}`);
    reportStructures = await structureResponse.json();
    runPlanDemoState = await runPlanResponse.json();
    artifactManifest = await artifactResponse.json();
    await loadExpPlanParagraphMappings(artifactManifest.expplan);
    state.stage = stageIndexFromLocation();
    renderStage();
  } catch (error) {
    content.innerHTML = `<div class="demo-load-error"><strong>页面内容暂时无法加载。</strong><span>${String(error)}</span></div>`;
  }
}

initializeDemo();
