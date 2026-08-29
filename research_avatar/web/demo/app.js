const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const requestedLanguage = new URLSearchParams(window.location.search).get("lang");
const embeddedDemo = new URLSearchParams(window.location.search).get("embedded") === "1";
const uiLanguage = requestedLanguage === "en" ? "en" : "zh";
const t = (zh, en) => uiLanguage === "en" ? en : zh;
document.documentElement.lang = uiLanguage === "en" ? "en" : "zh-CN";
document.body.classList.toggle("embedded-demo", embeddedDemo);
if (requestedLanguage) localStorage.setItem("research-avatar-language", uiLanguage);
document.querySelector("#demo-label").textContent = t("Product demonstration", "Product demo");
document.querySelector("#demo-language-label").textContent = t("Interface language", "Interface language");
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
  "Step 1 · Researcher portrait.":"Step 1 · Researcher profile", "Create reusable researcher profiles.":"Build a reusable researcher profile",
  "From the researcher's Scholar page and local writing samples, compile research directions method preferences writing style and experimental habits.":"Extract research directions, method preferences, writing style, and experimental habits from the supplied Scholar page and local writing samples.",
  "Completed":"Completed", "Build researcher profile from local Scholar HTML.":"Build a profile from local Scholar HTML",
  "Step 2 · Literature review":"Step 2 · Literature survey", "Organize related work into a verifiable research map.":"Organize related work into a verifiable research map",
  "Search and verify papers from different angles, outlining main directions, disputes and unresolved issues.":"Retrieve and verify papers from multiple angles to identify major directions, disputes, and open problems.",
  "52 Section verified":"52 papers verified", "Organize and verify relevant literature":"Survey and verify related literature",
  "Step three · Research direction":"Step 3 · Research ideas", "Compare candidate directions, clarify novelty and risk.":"Compare candidate directions, novelty, and risk",
  "For each direction describe research gaps core mechanisms testable conditions and the extent of overlap with recent work, and then the researcher selects.":"Each direction states its gap, mechanism, falsifier, and overlap with recent work; the researcher makes the final choice.",
  "I1 Selected":"I1 selected", "Generate candidate directions and verify each one.":"Generate and verify candidate directions",
  "Step four · Experimental design":"Step 4 · Experiment plan", "Infer experiments and evidence from the paper claims.":"Derive experiments and evidence from paper claims",
  "First clarify the questions the paper needs to answer, then for each claim arrange data, baselines, metrics, figures, and failure conditions.":"Define the paper questions first, then assign data, baselines, metrics, artifacts, and failure conditions to each claim.",
  "Plan confirmed.":"Plan approved", "Generate experimental design and pending charts.":"Generate the experiment plan and fillable artifacts",
  "Step five · Experiment execution":"Step 5 · Experiment execution", "Execute experiments according to evidence dependencies":"Execute experiments by evidence dependency",
  "Each task clearly states dependencies, outputs, completion criteria, and corresponding figures; can be confirmed at once or per item.":"Each task specifies dependencies, outputs, completion criteria, and target artifacts, with batch or per-task approval.",
  "All tasks confirmed":"All tasks approved", "Step six · Paper writing":"Step 6 · Paper writing", "Drafting the main text and creating charts":"Write the manuscript and build its figures",
  "The body text, figures, LaTeX, and the paper PDF are synchronized and updated in the same workspace.":"Prose, figures, LaTeX, and the paper PDF stay synchronized in one workspace.",
  "19/19 Section · draft has been generated.":"19/19 paragraphs · draft generated", "Paper writing workspace":"Paper-writing workspace",
  "Local status snapshot is read only; input and write operations are locked.":"Current local snapshot · read-only; input and write actions are disabled",
  "Projected Paper · Structure mapping":"Projected Paper · Structure mapping", "All parts of the reference paper map to Rough Paper.":"Every reference-paper section maps to the rough paper",
  "Structure reference · Ref Paper":"Structure reference · Ref Paper", "Correspondences for all sections.":"All section mappings", "Two paragraph examples":"Two paragraph examples",
  "View the corresponding writing in the reference paper.":"View the corresponding writing move in the reference paper", "Concrete diagram example: generate a result curve from an X-Y coordinate table.":"Artifact example: generate a result curve from x–y coordinates",
  "F2 Pending coordinate table.":"F2 fillable coordinate table", "X axis x · number of included random permutations.":"x · Number of random permutations included",
  "Proportion of questions where the answer on the Y axis is always the same.":"y · Proportion of questions with a consistently identical answer", "Pending experiments":"Pending",
  "Each line is a point on the curve; after the experiment, fill in y, and connect the right-hand chart in x order.":"Each row is one curve point. After execution, fill y and connect the points in x order.",
  "Wait for the four coordinates on the left to complete before automatic plotting.":"Automatically plotted after the four coordinates on the left are complete",
  "Experiment results example · G4.1 completed.":"Experiment result example · G4.1 completed", "After the experiment, the four left side coordinate rows generate the right side answer accuracy curve.":"After execution, the four coordinate rows generate the answer-consistency curve on the right",
  "Each green number is an evidence link; hover to preview the source and processing, click to open the full derivation.":"Each green value is an evidence link: hover for provenance and processing, or click for the complete acquisition process.",
  "F2 Full process for obtaining the value.":"Complete acquisition process for F2", "Execution progress":"Execution progress", "Completed":"completed",
  "Number of included random permutations":"Number of random permutations included", "Always consistent title ratio. (%)":"Consistently identical answers (%)",
  "F2 · x Indicate the total number of random permutations included in addition to the original order; y denotes the fraction of items that yield the same semantic answer across the original order and all these permutations.":"F2 · x is the cumulative number of random permutations beyond the original order; y is the proportion of questions receiving the same semantic answer across the original order and all included permutations.",
  "First show the coverage of all sections, then expand two paragraph examples. The system only migrates argument flow and chart pacing, not research content, data, or conclusions.":"Show complete section coverage, then expand two paragraph examples. The system transfers argumentative function and artifact rhythm, never research content, data, or conclusions.",
  "This task does not directly update charts.":"This task does not directly update an artifact",
  "Content summary":"Content summary", "Task confirmation":"Task approval", "Select execution method":"Choose an execution mode",
  "Confirm all tasks at once":"Approve all tasks once", "Itemized confirmation":"Approve one task at a time", "Next task.":"Next task", "Optimal value:":"Expected output", "Completion criteria":"Completion criterion"
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

const commandStrip = (title, command, detail = t("Generated results will be synchronized to the webpage.", "Generated results are synchronized to this page.")) => `
  <div class="command-card">
    <div><span>${t("Run in a local terminal", "Run in a local terminal")}</span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></div>
    <code>${escapeHtml(command)}</code><button type="button" data-copy="${escapeHtml(command)}">${t("Copy command", "Copy command")}</button>
  </div>`;

const pendingRows = (xs, series) => xs.map(x => `<tr><th>${x}</th>${series.map(() => `<td class="demo-pending">Pending experiments</td>`).join("")}</tr>`).join("");

const pendingTable = ({ headers, rows, className = "" }) => `
  <div class="table-scroll"><table class="result-shell source-table ${className}"><thead><tr>${headers.map(name => `<th>${name}</th>`).join("")}</tr></thead><tbody>${rows.map(name => `<tr><th>${name}</th>${headers.slice(1).map(() => `<td class="demo-pending">Pending experiments</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;

const projectedPanel = ({ title, dataset, metric, fields, xLabel, xs, series, image }) => `
  <section class="projected-panel">
    <h5>${title}</h5>
    <p><strong>Data and evaluation sets:</strong>${dataset}</p>
    <p><strong>Metrics and axes:</strong>${metric}</p>
    <div class="figure-data-pair">
      <div class="numeric-source">
        ${pendingTable({headers:[xLabel,...series],rows:xs})}
        <p class="field-line">Fields required to generate charts:${fields}</p>
      </div>
      <figure class="projected-chart">
        <img src="${image}" alt="${title} projected preview">
        <figcaption>Graphic preview: after the experiment is completed, it will be auto generated from the verified data on the left.</figcaption>
      </figure>
    </div>
  </section>`;

const projectedPaperStructure = () => {
  const targetSectionLabel = section => ({
    Abstract: "abstract", Introduction: "introduction", "Related Work": "Related work",
    Method: "method", Experiments: "experiment", Discussion: "discussion", Conclusion: "conclusion",
  }[section] || section);
  const paragraphPlanLabel = plan => ({
    "Explain the closest unresolved gap and why existing approaches do not settle it.": "Describe the closest yet unresolved research gap and why existing methods are insufficient to answer it.",
    "Introduce the planned main comparison, cite its bound table and data-figure placeholders, and use xx for every unavailable result without claiming an observed outcome.": "Describe the planned key comparisons, cite bound Tables and data figure placeholders, and write all not yet obtained results as xx without claiming observations.",
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
    return `<li><span>${t("Reference papers", "Ref Paper")} · ${escapeHtml(referenceSections.join(" / ") || t("Corresponding chapter", "corresponding section"))}</span><i>→</i><b>${t("Paper draft", "Rough Paper")} · ${escapeHtml(uiLanguage === "zh" ? targetSectionLabel(targetSection) : targetSection)} (${escapeHtml(paragraphRange)})</b></li>`;
  }).join("");
  const examplePrefixes = ["I-", "E-"];
  const examples = examplePrefixes.flatMap(prefix => {
    const candidates = expPlanParagraphMappings.filter(paragraph => paragraph.id.startsWith(prefix));
    return candidates.length ? [candidates[Math.floor((candidates.length - 1) / 2)]] : [];
  });
  const exampleMap = examples.map(paragraph => `
    <article class="paragraph-map-card">
      <header><b>${escapeHtml(uiLanguage === "zh" ? targetSectionLabel(paragraph.section) : paragraph.section)} · ${escapeHtml(paragraph.id)}</b><span>${escapeHtml(paragraph.referenceLabel || t("Unbound reference paragraph.", "No reference paragraph linked"))}</span></header>
      <p>${escapeHtml(uiLanguage === "zh" ? paragraphPlanLabel(paragraph.plan) : paragraph.plan)}</p>
      <details>
        <summary>View the corresponding writing in the reference paper.</summary>
        <p>${escapeHtml(paragraph.referenceBody || "This paragraph does not embed the reference text.")}</p>
        ${paragraph.logic ? `<small>${escapeHtml(paragraph.logic)}</small>` : ""}
      </details>
    </article>`).join("");
  return `
  <section class="workflow-example" data-demo-example="projected-f2">
    <p class="artifact-kicker">${t("Expected paper · Structure correspondence.", "Projected Paper · Structure mapping")}</p>
    <h4>${t("All parts of the reference paper correspond to the manuscript initial draft.", "Every reference-paper section maps to the rough paper")}</h4>
    <div class="reference-writing-contract">
      <b>${t("Structure reference · Reference paper.", "Structure reference · Ref Paper")}</b>
      <span>${t("First display the coverage relationships of all sections, then expand two paragraph examples. The system only migrates argument flow and chart pacing, not research content, data or conclusions.", "Show complete section coverage, then expand two paragraph examples. The system transfers argumentative function and artifact rhythm, never research content, data, or conclusions.")}</span>
    </div>
    <div class="section-coverage-map"><h5>${t("Mapping for all chapters.", "All section mappings")}</h5><ol>${coverageMap}</ol></div>
    <h5 class="paragraph-example-heading">Two paragraph examples</h5>
    <div class="paragraph-map-grid example-paragraph-map" aria-label="Example of the target paper paragraph correspondence.">${exampleMap || '<p class="demo-load-error">Paragraph example cannot be read at the moment.</p>'}</div>
    <h4 class="evidence-shell-heading">Concrete diagram example: generate a result curve from an X-Y coordinate table.</h4>
    <div class="figure-data-pair projected-example-pair">
      <div class="numeric-source">
        <h5>F2 Pending coordinate table.</h5>
        <div class="table-scroll"><table class="source-table projected-f2-table"><thead><tr><th>X axis x · number of included random permutations.</th><th>Proportion of questions where the answer on the Y axis is always the same.</th></tr></thead><tbody>
          <tr><th>1</th><td class="demo-pending">Pending experiments</td></tr>
          <tr><th>2</th><td class="demo-pending">Pending experiments</td></tr>
          <tr><th>3</th><td class="demo-pending">Pending experiments</td></tr>
          <tr><th>4</th><td class="demo-pending">Pending experiments</td></tr>
        </tbody></table></div>
        <p class="field-line">Each line is a point on the curve; after the experiment, fill in y, and connect the right-hand chart in x order.</p>
      </div>
      <figure class="blank-chart projected-chart" aria-label="Figure 2 to be filled.">
        <span class="blank-axis blank-x"></span><span class="blank-axis blank-y"></span>
        <strong>${t("F2 · Ordering consistency.", "F2 · Permutation consistency")}</strong><span>Wait for the four coordinates on the left to complete before automatic plotting.</span>
      </figure>
    </div>
  </section>`;
};

const provenanceValue = (value, locator, calculation) => `
  <a class="provenance-number" href="#run-plan" data-provenance-target="demo-f2-provenance">
    ${escapeHtml(value)}
    <span class="provenance-tooltip"><b>Click to view the full experimental process.</b><span><strong>Command:</strong>python code/run_option_permutations.py --config code/configs/option_order.json --output results/option_order</span><span><strong>Executable file:</strong>code/run_option_permutations.py</span><span><strong>Source:</strong>${escapeHtml(locator)}</span><span><strong>Processing:</strong>${escapeHtml(calculation)}</span><span><strong>Verification:</strong>Runbook, logs, and numerical values have all been verified.</span></span>
  </a>`;

const completedExperimentExample = () => `
  <section class="workflow-example completed-example" data-demo-example="completed-f2">
    <p class="artifact-kicker">Experiment results example · G4.1 completed.</p>
    <h4>After the experiment, the four left side coordinate rows generate the right side answer accuracy curve.</h4>
    <div class="completed-result-grid">
      <div class="table-scroll"><table class="source-table completed-source coordinate-source"><thead><tr><th>X axis x · number of included random permutations.</th><th>Proportion of questions where the answer on the Y axis is always the same.</th></tr></thead><tbody>
        <tr><th>1</th><td>${provenanceValue("94.0%", "results/option_order/G4.1/consistency_by_count.json · permutation_count=1", "Read consistency_rate.")}</td></tr>
        <tr><th>2</th><td>${provenanceValue("91.0%", "results/option_order/G4.1/consistency_by_count.json · permutation_count=2", "Read consistency_rate.")}</td></tr>
        <tr><th>3</th><td>${provenanceValue("89.0%", "results/option_order/G4.1/consistency_by_count.json · permutation_count=3", "Read consistency_rate.")}</td></tr>
        <tr><th>4</th><td>${provenanceValue("88.0%", "results/option_order/G4.1/consistency_by_count.json · permutation_count=4", "Read consistency_rate.")}</td></tr>
      </tbody></table></div>
      <figure class="completed-chart" aria-label="Figure 2 completed option arrangement answer consistency curve.">
        <svg viewBox="0 0 560 330" role="img" aria-label="Consistency rate curve formed by four coordinate points.">
          <g class="chart-grid"><line x1="70" y1="55" x2="520" y2="55"/><line x1="70" y1="115" x2="520" y2="115"/><line x1="70" y1="175" x2="520" y2="175"/><line x1="70" y1="235" x2="520" y2="235"/></g>
          <g class="chart-axis"><line x1="70" y1="270" x2="520" y2="270"/><line x1="70" y1="35" x2="70" y2="270"/></g>
          <g class="chart-labels"><text x="31" y="274">85</text><text x="31" y="214">90</text><text x="31" y="154">95</text><text x="25" y="94">100</text><text x="66" y="294">1</text><text x="215" y="294">2</text><text x="365" y="294">3</text><text x="515" y="294">4</text><text x="202" y="319">Number of included random permutations</text><text x="8" y="22">Always consistent title ratio. (%)</text></g>
          <polyline class="series-style" points="70,127 220,163 370,187 520,199"/>
          <g class="point-style"><circle cx="70" cy="127" r="5"/><circle cx="220" cy="163" r="5"/><circle cx="370" cy="187" r="5"/><circle cx="520" cy="199" r="5"/></g>
        </svg>
        <figcaption>F2 · x Indicate the total number of random permutations included in addition to the original order; y denotes the fraction of items that yield the same semantic answer across the original order and all these permutations.</figcaption>
      </figure>
    </div>
    <p class="hover-instruction">Each green number is an evidence link; hover to preview the source and processing, click to open the full derivation.</p>
    <details id="demo-f2-provenance" class="provenance-card">
      <summary>F2 Full process for obtaining the value.</summary>
      <dl><dt>Execute Goal</dt><dd>G3.1 Execute call; G4.1 Summary Curve.</dd><dt>Actual command</dt><dd>python code/run_option_permutations.py --config code/configs/option_order.json --output results/option_order</dd><dt>Working directory</dt><dd>Project root directory.</dd><dt>run file</dt><dd>code/run_option_permutations.py</dd><dt>Configuration and input.</dt><dd>code/configs/option_order.json; data/questions.jsonl; data/permutations.jsonl</dd><dt>Execution list</dt><dd>results/option_order/run_manifest.json</dd><dt>Standard output / error log</dt><dd>results/option_order/stdout.log; results/option_order/stderr.log</dd><dt>Raw output</dt><dd>results/option_order/responses.jsonl</dd><dt>Coordinate data</dt><dd>results/option_order/G4.1/consistency_by_count.json</dd><dt>Calculation rules</dt><dd>The original order always serves as the baseline; for k.=1–4, Compute the proportion of items whose semantic answers are consistent across the original order and the first k random permutations.</dd><dt>Figure generation</dt><dd>Using k as the x value for the number of random orders and y as the fixed task ratio, connect four points.</dd><dt>Validation status</dt><dd><span class="verified-mark">VERIFIED · Command exit status, 500 responses, four-line table, and four plotted points checked item by item.</span></dd></dl>
    </details>
  </section>`;

const resultTable = ({ id, title, headers, rows, note }) => `
  <section class="evidence-artifact result-table-artifact">
    <p class="artifact-kicker">${id} · Waiting for experiment results.</p>
    <h4>${title}</h4>
    ${pendingTable({headers,rows,className:"main-result"})}
    <p>${note}</p>
  </section>`;

let runPlanDemoState = null;

const runStatusMark = status => ({completed:"✅",running:"▶",proposed:"→",locked:"○",pending:"○",blocked:"⚠",invalidated:"⚠"}[status] || "○");

const publicPartTitles = {
  P1: t("Freeze question and permutation protocol", "Freeze questions and permutation protocol"),
  P2: t("Generate and verify option ordering", "Generate and verify option permutations"),
  P3: t("Execute 500 model calls.", "Run 500 model calls"),
  P4: t("Compute permutation invariance metric", "Compute permutation-invariance metrics"),
  P5: t("Robustness and reversal case analysis.", "Analyze robustness and answer flips"),
};

const publicArtifactLabels = {
  F1: t("Figure 1", "Figure 1"), F2: t("Figure 2", "Figure 2"),
  F3: t("Figure 3", "Figure 3"), F4: t("Figure 4", "Figure 4"), F5: t("Figure 5", "Figure 5"),
  T1: t("Table 1", "Table 1"), T2: t("Table 2", "Table 2"),
  T3: t("Table 3", "Table 3"), T4: t("Table 4", "Table 4"),
};

const executionModePanel = goal => `<div class="demo-current-goal execution-mode-panel" data-demo-current-goal="${escapeHtml(goal.id)}">
  <p class="artifact-kicker">Task confirmation</p>
  <h5>Select execution method</h5>
  <div class="execution-mode-options">
    <div class="selected"><b>Confirm all tasks at once</b><span>The system executes in dependency order, and saves and verifies results separately.</span></div>
    <div><b>Itemized confirmation</b><span>Review outputs and completion criteria before starting each task.</span></div>
  </div>
  <p class="execution-stop-rule">If validation fails, budget is exhausted, or new research judgments are needed, automated execution will stop immediately.</p>
  <dl><dt>Next task.</dt><dd>${escapeHtml(goal.id)} · ${escapeHtml(goal.title)}</dd><dt>Optimal value:</dt><dd>${(goal.outputs || []).map(escapeHtml).join(" · ")}</dd><dt>Completion criteria</dt><dd>${escapeHtml(goal.completion_check)}</dd></dl>
</div>`;

const goalHierarchy = () => {
  if (!runPlanDemoState) return `<section class="goal-hierarchy"><p>The experimental plan cannot be loaded at the moment.</p></section>`;
  const goals = Object.fromEntries(runPlanDemoState.goals.map(goal => [goal.id, goal]));
  const completed = runPlanDemoState.goals.filter(goal => goal.status === "completed").length;
  const representativeGoalIds = runPlanDemoState.goals.map(goal => goal.id);
  const representativeParts = representativeGoalIds.map(goalId => {
    const goal = goals[goalId];
    const part = runPlanDemoState.parts.find(item => item.id === goal.part_id);
    return {part, goal};
  });
  return `<section class="goal-hierarchy compact-goal-hierarchy"><div class="compact-goal-head"><b>Execution progress</b><span>${completed}/${runPlanDemoState.goals.length} ${t("Completed", "completed")}</span></div><ol>${representativeParts.map(({part, goal}) => {
    const destination = goal.artifact_ids?.length ? goal.artifact_ids.map(id => publicArtifactLabels[id] || id).join(t(", ", ", ")) : t("This task does not directly update charts.", "This task does not directly update an artifact");
    return `<li><span>${escapeHtml(part.id)}</span><b>${runStatusMark(goal.status)} ${escapeHtml(goal.id)} · ${escapeHtml(publicPartTitles[part.id] || goal.title)}</b><em>${escapeHtml(destination)}</em></li>`;
  }).join("")}</ol></section>`;
};

const paperStudioScreenshots = () => `<section class="paper-studio-live">
  <p class="artifact-kicker">Paper writing workspace</p>
  <h4>Paper Studio</h4>
  <div class="paper-studio-frame-shell">
    <div class="paper-studio-frame-bar"><span>Local status snapshot is read only; input and write operations are locked.</span></div>
    <iframe src="/demo-studio/?lang=${encodeURIComponent(uiLanguage)}&embedded=research-studio" title="Paper Studio read-only demo" loading="lazy"></iframe>
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
  profile: t("Investigator portrait.", "Researcher Profile"),
  literature: t("Literature review report", "Literature Survey"),
  ideas: t("Research direction evaluation", "Research-Idea Assessment"),
  expplan: t("Experimental design", "Experiment Plan"),
  runplan: t("Experiment execution plan.", "Experiment Execution Plan"),
  results: t("Experimental results and evidence", "Experiment Results and Evidence"),
  "paper-studio": t("Paper writing workspace", "Paper-Writing Workspace"),
};

const reportDocument = key => {
  const report = reportStructures[key];
  if (!report) return "";
  return `<article class="report-document" aria-label="${escapeHtml(report.artifact)}Content summary">
    <section class="report-structure-summary" aria-label="${escapeHtml(report.artifact)}Structure summary">
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
    <div class="canonical-artifact-head"><span>Content summary</span><strong>${escapeHtml(title)}</strong><small>${artifact?.source ? `${t("Corresponding local", "Local artifact:")} ${escapeHtml(artifact.source)}` : t("Corresponds to the local Research Studio product.", "Corresponding local Research Studio artifact")}</small></div>
    ${reportDocument(key)}
  </section>`;
};

const stages = [
  {
    id: "profile", short: t("Research profile", "Profile"), path: "profile", title: t("First understand the researcher, then begin the research.", "Understand the researcher before starting research"),
    compare: [t("Use task context and general configuration as the primary starting point.", "Starts from task context and general configuration"), t("Suitable for rapid entry into automatic exploration", "Useful for entering automated exploration quickly"), t("First establish verifiable personalized basis.", "First establish inspectable personalization evidence")],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">Step 1 · Researcher portrait.</p><h3>Create reusable researcher profiles.</h3><p>From the researcher's Scholar page and local writing samples, compile research directions method preferences writing style and experimental habits.</p></div><span class="status-pill">Completed</span></div>
      ${commandStrip(t("Build researcher profile from local Scholar HTML.", "Build a profile from local Scholar HTML"), t("$profileconstruct use ~/Downloads/scholar_profile.html", "$profileconstruct use ~/Downloads/scholar_profile.html"))}
      ${canonicalArtifact("profile")}`
  },
  {
    id: "literature", short: t("Literature review", "Literature"), path: "literature", title: t("Create a verifiable literature map using a four step structure.", "Build a verifiable literature map in four steps"),
    compare: [t("Return a large batch of papers, abstracts, and scattered conclusions.", "Returns many papers, abstracts, and disconnected findings at once"), t("The results are too numerous and messy, with method categories, evaluation criteria, and real research gaps all mixed together, making direct judgment difficult.", "Method families, evaluation evidence, and genuine gaps are mixed together, making decisions difficult."), t("Consolidate validated evidence into Problem. → Approaches → Evaluation → Gaps:First define the problem, then categorize methods, compare evaluations, and finally identify the research gaps, clearly, concisely, and accurately.", "Organizes verified evidence as Problem → Approaches → Evaluation → Gaps for a concise, decision-ready field map.")],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">Step 2 · Literature review</p><h3>Organize related work into a verifiable research map.</h3><p>Search and verify papers from different angles, outlining main directions, disputes and unresolved issues.</p></div><span class="status-pill">52 Section verified</span></div>
      ${commandStrip("Organize and verify relevant literature", "$researchlit <research topic>")}
      ${canonicalArtifact("literature")}`
  },
  {
    id: "ideas", short: t("Direction selection", "Ideas"), path: "ideas", title: t("Candidates must first meet the threshold, then be selected by the researcher.", "Screen candidates before researcher selection"),
    compare: [t("Typically used to quickly present candidate directions by sorting.", "Ranks candidate directions for quick review"), t("The researcher reevaluates value and novelty.", "The researcher then judges value and novelty"), t("Set novelty and falsifiability as independent hard thresholds.", "Treats novelty and falsifiability as separate hard gates")],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">Step three · Research direction</p><h3>Compare candidate directions, clarify novelty and risk.</h3><p>For each direction describe research gaps core mechanisms testable conditions and the extent of overlap with recent work, and then the researcher selects.</p></div><span class="status-pill">I1 Selected</span></div>
      ${commandStrip("Generate candidate directions and verify each one.", "$ideagen")}
      ${canonicalArtifact("ideas")}`
  },
  {
    id: "expplan", short: t("Experimental design", "Experiment plan"), path: "experiment-plan", title: t("First clarify the main claim of the paper, then deduce the required experiments.", "Derive experiments from the paper claims"),
    compare: [t("First enumerate the experimental checklist, then supplement the argument with the results.", "Lists experiments first and constructs the argument afterward"), t("Many experiments are performed, but the paper claims have not been directly validated.", "This can produce many experiments without directly testing the paper's claims."), t("First determine what the paper must prove, then assign charts, metrics, and failure conditions for each claim.", "Defines what the paper must establish, then assigns artifacts, metrics, and failure conditions to each claim.")],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">Step four · Experimental design</p><h3>Infer experiments and evidence from the paper claims.</h3><p>First clarify the questions the paper needs to answer, then for each claim arrange data, baselines, metrics, figures, and failure conditions.</p></div><span class="status-pill">Plan confirmed.</span></div>
      ${commandStrip("Generate experimental design and pending charts.", "$expplan")}
      ${canonicalArtifact("expplan")}
      ${projectedPaperStructure()}`
  },
  {
    id: "runplan", short: t("Experiment execution", "Execution"), path: "run-plan", title: t("Execute experiments according to evidence dependencies", "Execute experiments by evidence dependency"),
    compare: [t("Emphasize continuous autonomous exploration and overall throughput.", "Emphasizes continuous autonomous exploration and throughput"), t("The execution process usually lacks a clear evidence boundary.", "Execution often lacks explicit evidence boundaries."), t("First display all tasks, then confirm again either as a whole or item by item.", "Shows all tasks first, then supports batch or per-task approval.")],
    render: () => {
      const currentId = runPlanDemoState?.active_goal || runPlanDemoState?.proposed_goal_id || "NONE";
      const allGoalsConfirmed = runPlanDemoState?.goal_confirmation?.scope === "all_goals";
      return `
      <div class="stage-head"><div><p class="eyebrow">Step five · Experiment execution</p><h3>Execute experiments according to evidence dependencies</h3><p>Each task clearly states dependencies, outputs, completion criteria, and corresponding figures; can be confirmed at once or per item.</p></div><span class="status-pill">${allGoalsConfirmed ? "All tasks confirmed" : `${escapeHtml(currentId)} Awaiting confirmation`}</span></div>
      ${canonicalArtifact("runplan")}
      ${completedExperimentExample()}`;
    }
  },
  {
    id: "paper", short: t("Paper writing", "Writing"), path: "paper-writing", title: t("Paragraph by paragraph writing, real-time compilation, editable charts.", "Paragraph writing, live compilation, and editable figures"),
    compare: [t("Prefer bulk generation of Markdown or LaTeX drafts.", "Often generates a Markdown or LaTeX draft in one batch"), t("Suitable for rapidly obtaining an overall version.", "Useful for obtaining a complete draft quickly"), t("The main text uses the LLM API (not Code Agent) to generate content paragraph by paragraph; write to LaTeX and compile in real time only after acceptance.", "Uses the LLM API paragraph by paragraph; accepted text is then written to LaTeX and compiled live.")],
    render: () => `
      <div class="stage-head"><div><p class="eyebrow">Step six · Paper writing</p><h3>Drafting the main text and creating charts</h3><p>The body text, figures, LaTeX, and the paper PDF are synchronized and updated in the same workspace.</p></div><span class="status-pill">19/19 Section · draft has been generated.</span></div>
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
  comparePanel.innerHTML = stage.compare ? `<p class="eyebrow">${t("Workflow comparison.", "Workflow comparison")}</p><h4>${stage.short}${t("The focus of the work.", " focus")}</h4><div class="compare-card bad"><span>${t("Common automation tools for research", "Typical automated research tools")}</span><strong>${stage.compare[0]}</strong><p>${stage.compare[1]}</p></div><div class="compare-card good"><span>Research Avatar</span><strong>${stage.title}</strong><p>${stage.compare[2]}</p></div>` : "";
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
    button.textContent = t("Copied ✓", "Copied ✓");
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
    button.textContent = copied ? t("Copied ✓", "Copied ✓") : t("Please select the command to copy", "Select the command to copy");
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
    content.innerHTML = `<div class="demo-load-error"><strong>Page content is temporarily unavailable.</strong><span>${String(error)}</span></div>`;
  }
}

initializeDemo();
