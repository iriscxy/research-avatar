(() => {
  const ideas = [
    {
      id: "I1",
      title: "MORE:Adaptive multi objective learning for ecommerce dialogue systems.",
      novelty: "novel",
      scope: "Core requirements",
      summary: "Treat user portrait reasoning as a training constraint and dynamically adjust generation reward weights based on gradient feedback to make a single model balance accuracy naturalness and efficiency.",
      difference: "Combine constrained portrait reasoning with gradient feedback based reward coordination within the same dialogue strategy; the closest approaches handle dynamic rewards or consistency signals separately.",
      objection: "Private image structure and production throughput may make strongest deployment conclusions hard to independently verify.",
      tier: "A",
      status: "novel",
      selected: true,
    },
    {
      id: "I2",
      title: "Pareto frontier dialogue alignment.",
      novelty: "Distinguishable but localization needs strengthening.",
      scope: "Core requirements",
      summary: "Maintain a small set of Pareto optimal dialogue strategies and learn routing rules from user state risk, rather than compressing all goals into a single reward.",
      difference: "Routing among multiple target specific strategies rather than dynamically adjusting the target weights of a single strategy.",
      objection: "Routers may simply transfer rather than resolve reward conflicts, and increase online service complexity.",
      tier: "B",
      status: "differentiable",
    },
    {
      id: "I3",
      title: "Counterfactual user profile reasoning benchmark.",
      novelty: "novel",
      scope: "Core requirements",
      summary: "Construct counterfactual example pairs that alter only a single user attribute to test whether the dialogue model changes only responses logically affected by that attribute.",
      difference: "Convert image fidelity into an intervention based evaluation metric rather than adding another judge model score.",
      objection: "Private image structures may make real open counterfactual samples difficult to publish.",
      tier: "A",
      status: "novel",
    },
    {
      id: "I4",
      title: "Calibrated manual handoff under target conflict.",
      novelty: "Distinguishable but localization needs strengthening.",
      scope: "Core requirements",
      summary: "When the reward targets diverge, those dialogues are handed to humans, and overall quality is optimized under a fixed transfer budget.",
      difference: "Convert target disagreements into calibrated human upgrade signals that also consider operating costs.",
      objection: "If evaluation budget is not fixed, the system may achieve superficial gains by routing the most difficult samples.",
      tier: "B",
      status: "differentiable",
    },
    {
      id: "I5",
      title: "Promote robust multilingual dialogue.",
      novelty: "Distinguishable but localization needs strengthening.",
      scope: "Only for evaluation purposes.",
      summary: "Test whether adaptive reward ranking remains stable when the same ecommerce intent is expressed in different languages and dialects.",
      difference: "Directly study drift in reward models and gradient ordering under language variation.",
      objection: "Without an appropriate correction mechanism, contributions may degenerate into mere extended evaluation.",
      tier: "B",
      status: "differentiable",
    },
    {
      id: "I6",
      title: "Causal diagnosis of reward conflicts",
      novelty: "novel",
      scope: "Core requirements",
      summary: "Intervene reward channels one by one and measure subsequent gradients and response changes to distinguish real objective conflicts from evaluation noise.",
      difference: "Add a causal diagnostic step before selecting a multi objective optimizer.",
      objection: "Intervening with learned rewards may not detect conflicts between human real objectives.",
      tier: "A",
      status: "novel",
    },
  ];

  const steps = `
    <ol>
      <li>Clarify each objective signal and its raw observable quantity.</li>
      <li>Harmonize training and evaluation boundaries to ensure comparability across methods.</li>
      <li>First test decisive falsification conditions, then expand to comprehensive evaluation.</li>
      <li>Also report task effects, human preference alignment, stability, and efficiency evidence.</li>
    </ol>`;

  const render = () => {
    document.documentElement.lang = "zh-CN";
    document.title = "Research direction report: multi objective learning for ecommerce dialogue.";

    const header = document.querySelector("body > header");
    if (header) {
      header.innerHTML = `
        <div class="kicker">Research direction generation</div>
        <h1>Research directions around adaptive multi objective dialogue learning.</h1>
        <div class="selected"><b>Selected I1 MORE Adaptive Multi-Objective Learning for E-commerce Dialogue Systems.</b><br>Date selected: 2026-08-21 · Hypothetical research plan chosen by the researcher; novelty assessment is conditioned on the work not yet published.</div>`;
    }

    const landscape = document.querySelector('[data-report-section="literature-landscape"]');
    if (landscape) {
      landscape.innerHTML = `
        <h2>1. Literature landscape</h2>
        <p><a href="/artifact/literature">Literature review</a>Note that task oriented dialogue is moving from a pipeline system to end to end models and LLM agents, and reward learning has evolved from a single scalar signal to multiple dynamically coordinated objectives. The current core gaps concentrate on conflict identification, adjudication effectiveness, public reproducibility, and cost comparisons.</p>`;
    }

    const ranked = document.querySelector('[data-report-section="ranked-slate"]');
    if (ranked) {
      ranked.innerHTML = `
        <h2>2. Sorting and comparison of candidate directions</h2>
        <div class="wide"><table><thead><tr><th>ID</th><th>Research direction</th><th>Novelty</th><th>Scope necessity.</th><th>Specific differences from existing work.</th><th>Strongest doubt</th><th>Confidence</th></tr></thead>
        <tbody>${ideas.map(idea => `<tr class="${idea.selected ? "selected" : ""}"><td>${idea.id}${idea.selected ? " · Selected" : ""}</td><td>${idea.title}</td><td>${idea.novelty}</td><td>${idea.scope}</td><td>${idea.difference}</td><td>${idea.objection}</td><td>high</td></tr>`).join("")}</tbody></table></div>
        <p>I1 Selected under the counterfactual premise that the target work has not yet been published. MORE is regarded as a method to be proposed, and its novelty is only compared with earlier dynamic reward and dialogue consistency approaches.</p>`;
    }

    const cards = document.querySelector('[data-report-section="candidate-cards"]');
    if (cards) {
      cards.innerHTML = `
        <h2>3. Candidate direction details</h2>
        <div class="grid">${ideas.map(idea => `<article class="card" data-idea-id="${idea.id}" data-selected="${idea.selected ? "true" : "false"}" data-novelty-status="${idea.status}" data-idea-tier="${idea.tier}" data-default-pick="${idea.selected ? "true" : "false"}" data-scope-necessity="${idea.id === "I5" ? "EVALUATION_SCOPE_ONLY" : "ESSENTIAL"}" data-scope-action="${idea.id === "I5" ? "relabel" : "retain"}">
          <h3>${idea.id}. ${idea.title}</h3>
          <p><b>Plain-language overview.</b>${idea.summary}</p>
          <p><b>Core mechanism.</b>${idea.summary}</p>
          ${steps}
          <p><b>Research hypotheses and falsification conditions.</b>This mechanism should improve the tradeoffs among targets and must not mask degradation on other metrics; if the main benefit vanishes under equal cost comparisons or accompanying direct metrics, then reject this hypothesis.</p>
          <p><b>Closest work and differences.</b><a href="https://aclanthology.org/2024.lrec-main.483/">Dynamic Reward Adjustment</a>; ${idea.difference}</p>
          <p><b>Necessity of scope.</b>${idea.scope}.<b>Feasibility.</b>Consistent with Gao Lang research background in dialogue systems and LLM evaluation.<b>The strongest doubt.</b>${idea.objection}</p>
        </article>`).join("")}</div>`;
    }

    const selection = document.querySelector('[data-report-section="human-selection"]');
    if (selection) {
      selection.innerHTML = `
        <h2>4. Investigator selection.</h2>
        <p>The current selected plan is I1. Other candidate directions remain intact for comparison; subsequent experiments will evaluate this plan under the counterfactual premise that MORE has not yet been published.</p>`;
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render, { once: true });
  } else {
    render();
  }
})();
