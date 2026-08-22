(() => {
  const ideas = [
    {
      id: "I1",
      title: "MORE：面向电商对话系统的自适应多目标学习",
      novelty: "新颖",
      scope: "核心必需",
      summary: "将用户画像推理作为训练约束，并根据梯度反馈动态调整生成奖励权重，使单一模型同时兼顾准确性、自然度与效率。",
      difference: "在同一个对话策略中结合受约束的画像推理与基于梯度反馈的奖励协调；最接近的方法只分别处理动态奖励或一致性信号。",
      objection: "私有画像结构和生产流量可能使最强的部署结论难以被独立验证。",
      tier: "A",
      status: "novel",
      selected: true,
    },
    {
      id: "I2",
      title: "帕累托前沿对话对齐",
      novelty: "可区分，但需强化定位",
      scope: "核心必需",
      summary: "维护一组小规模帕累托最优对话策略，并根据用户状态风险学习路由规则，而不是把所有目标压缩成单一奖励。",
      difference: "在多个目标专用策略之间进行路由，而不是对单一策略的目标权重进行动态调整。",
      objection: "路由器可能只是转移而非解决奖励冲突，并增加在线服务复杂度。",
      tier: "B",
      status: "differentiable",
    },
    {
      id: "I3",
      title: "反事实用户画像推理基准",
      novelty: "新颖",
      scope: "核心必需",
      summary: "构造仅改变一个用户属性的反事实样本对，检验对话模型是否只改变逻辑上受该属性影响的回复内容。",
      difference: "把画像正确性转化为基于干预的评测基准，而不是再增加一个裁判模型分数。",
      objection: "私有画像结构可能导致真实的公开反事实样本难以发布。",
      tier: "A",
      status: "novel",
    },
    {
      id: "I4",
      title: "目标冲突下的校准式人工转接",
      novelty: "可区分，但需强化定位",
      scope: "核心必需",
      summary: "预测奖励目标何时发生分歧，只将这些对话转交人工，并在固定转接预算下优化整体质量。",
      difference: "将目标分歧转化为经过校准、同时考虑运营成本的人工升级信号。",
      objection: "如果不固定评测预算，系统可能仅靠转接最困难的样本获得表面提升。",
      tier: "B",
      status: "differentiable",
    },
    {
      id: "I5",
      title: "奖励鲁棒的多语言对话",
      novelty: "可区分，但需强化定位",
      scope: "仅作为评测范围",
      summary: "检验同一电商意图以不同语言和方言表达时，自适应奖励排序能否保持稳定。",
      difference: "直接研究语言变化下奖励模型与梯度排序的漂移。",
      objection: "如果没有相应的纠正机制，贡献可能退化为单纯的扩展评测。",
      tier: "B",
      status: "differentiable",
    },
    {
      id: "I6",
      title: "奖励冲突的因果诊断",
      novelty: "新颖",
      scope: "核心必需",
      summary: "逐一干预奖励通道并测量后续梯度和回复变化，从而区分真实目标冲突与评测噪声。",
      difference: "在选择多目标优化器之前加入因果诊断环节。",
      objection: "对学习得到的奖励进行干预，未必能识别人类真实目标之间的冲突。",
      tier: "A",
      status: "novel",
    },
  ];

  const steps = `
    <ol>
      <li>明确各项目标信号及其原始可观测量。</li>
      <li>统一训练和评测边界，保证方法间可比。</li>
      <li>先检验决定性的证伪条件，再扩展到全面评测。</li>
      <li>同时报告任务效果、人类偏好一致性、稳定性和效率证据。</li>
    </ol>`;

  const render = () => {
    document.documentElement.lang = "zh-CN";
    document.title = "研究方向报告：电商对话的多目标学习";

    const header = document.querySelector("body > header");
    if (header) {
      header.innerHTML = `
        <div class="kicker">研究方向生成</div>
        <h1>围绕自适应多目标对话学习的研究方向</h1>
        <div class="selected"><b>已选择：I1 · MORE：面向电商对话系统的自适应多目标学习</b><br>选择日期：2026-08-21 · 由研究者选择的假设性研究方案；新颖性判断以该工作尚未发表为前提。</div>`;
    }

    const landscape = document.querySelector('[data-report-section="literature-landscape"]');
    if (landscape) {
      landscape.innerHTML = `
        <h2>1. 文献格局</h2>
        <p><a href="/artifact/literature">文献综述</a>显示，任务型对话正在从流水线系统转向端到端模型和 LLM 智能体，奖励学习也从单一标量信号发展为多个可动态协调的目标。当前核心缺口集中在冲突识别、裁判有效性、公开可复现性以及等成本比较。</p>`;
    }

    const ranked = document.querySelector('[data-report-section="ranked-slate"]');
    if (ranked) {
      ranked.innerHTML = `
        <h2>2. 候选方向排序与比较</h2>
        <div class="wide"><table><thead><tr><th>ID</th><th>研究方向</th><th>新颖性</th><th>范围必要性</th><th>与现有工作的具体差异</th><th>最强质疑</th><th>置信度</th></tr></thead>
        <tbody>${ideas.map(idea => `<tr class="${idea.selected ? "selected" : ""}"><td>${idea.id}${idea.selected ? " · 已选择" : ""}</td><td>${idea.title}</td><td>${idea.novelty}</td><td>${idea.scope}</td><td>${idea.difference}</td><td>${idea.objection}</td><td>高</td></tr>`).join("")}</tbody></table></div>
        <p>I1 在“目标工作尚未发表”的反事实前提下被选中。MORE 被视为待提出的方法，其新颖性仅与更早的动态奖励和对话一致性方法比较。</p>`;
    }

    const cards = document.querySelector('[data-report-section="candidate-cards"]');
    if (cards) {
      cards.innerHTML = `
        <h2>3. 候选方向详情</h2>
        <div class="grid">${ideas.map(idea => `<article class="card" data-idea-id="${idea.id}" data-selected="${idea.selected ? "true" : "false"}" data-novelty-status="${idea.status}" data-idea-tier="${idea.tier}" data-default-pick="${idea.selected ? "true" : "false"}" data-scope-necessity="${idea.id === "I5" ? "EVALUATION_SCOPE_ONLY" : "ESSENTIAL"}" data-scope-action="${idea.id === "I5" ? "relabel" : "retain"}">
          <h3>${idea.id}. ${idea.title}</h3>
          <p><b>通俗概述。</b>${idea.summary}</p>
          <p><b>核心机制。</b>${idea.summary}</p>
          ${steps}
          <p><b>研究假设与证伪条件。</b>该机制应改善目标间的权衡且不能掩盖其他指标退化；如果在等计算成本比较或配套直接指标下主要收益消失，则否定该假设。</p>
          <p><b>最接近工作及差异。</b><a href="https://aclanthology.org/2024.lrec-main.483/">Dynamic Reward Adjustment</a>；${idea.difference}</p>
          <p><b>范围必要性。</b>${idea.scope}。<b>可行性。</b>与高朗在对话系统和 LLM 评测方面的研究背景相符。<b>最强质疑。</b>${idea.objection}</p>
        </article>`).join("")}</div>`;
    }

    const selection = document.querySelector('[data-report-section="human-selection"]');
    if (selection) {
      selection.innerHTML = `
        <h2>4. 研究者选择</h2>
        <p>当前选定方案为 I1。其他候选方向仍完整保留以供比较；后续实验计划将在 MORE 尚未发表的反事实前提下评估该方案。</p>`;
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render, { once: true });
  } else {
    render();
  }
})();
