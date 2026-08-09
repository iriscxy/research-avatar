const app = { state: null, stage: 0, selectedIdea: null };
const pipeline = document.querySelector("#pipeline");
const stageBody = document.querySelector("#stage-body");
const previewFrame = document.querySelector("#preview-frame");
const previewEmpty = document.querySelector("#preview-empty");
const previewTitle = document.querySelector("#preview-title");
const previewOpen = document.querySelector("#preview-open");
const toast = document.querySelector("#toast");
const stageStorageKey = "research-studio.active-stage";
const artifactSandbox = "allow-scripts allow-forms allow-popups allow-downloads";

const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const statusLabel = status => ({complete:"完成",in_progress:"进行中",waiting_confirmation:"等待确认",not_started:"未开始"}[status] || status);
const extension = path => path.split(".").pop().toUpperCase();
function savedStage() {
  const value = Number.parseInt(localStorage.getItem(stageStorageKey) || "0", 10);
  return Number.isFinite(value) && value >= 0 ? value : 0;
}

function setStage(index) {
  app.stage = index;
  localStorage.setItem(stageStorageKey, String(index));
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { toast.hidden = true; }, 1800);
}

async function copyText(text, trigger=null) {
  try {
    await navigator.clipboard.writeText(text);
    const feedback = trigger?.querySelector?.(".copy-action");
    if (feedback) {
      feedback.textContent = "已复制 ✓";
      trigger.classList.add("copied");
      setTimeout(() => { feedback.textContent = "⧉ 复制"; trigger.classList.remove("copied"); }, 1600);
    }
    showToast("命令已复制，可回到 Codex 执行");
  }
  catch { showToast("复制失败，请手动选择命令"); }
}

function renderPipeline() {
  pipeline.innerHTML = app.state.stages.map((stage, index) => `<button class="pipeline-button ${index === app.stage ? "active" : ""}" data-stage="${index}" data-status="${escapeHtml(stage.status)}" type="button"><span>0${index + 1} · ${escapeHtml(statusLabel(stage.status))}</span><strong>${escapeHtml(stage.title)}</strong></button>`).join("");
}

function renderSidebar(stage) {
  document.querySelector("#stage-identity").innerHTML = `<span class="stage-number">LIVE PROJECT · STAGE 0${app.stage + 1}</span><h2 class="stage-name">${escapeHtml(stage.title)}</h2><p class="stage-message">${escapeHtml(stage.message)}</p><span class="stage-status ${escapeHtml(stage.status)}"><i></i>${escapeHtml(statusLabel(stage.status))}</span>`;
  document.querySelector("#sidebar-command").innerHTML = `<div class="sidebar-command"><span>下一条 Codex 命令</span><button class="copy-command" data-command="${escapeHtml(stage.command)}" title="复制 ${escapeHtml(stage.command)}" type="button"><code>${escapeHtml(stage.command)}</code><span class="copy-action">⧉ 复制</span></button></div>`;
}

function goalMarkup(stage) {
  if (!stage.goals?.length) return "";
  const currentId = stage.proposed_goal?.id;
  return `<div class="content-section"><div class="content-section-title"><strong>多层 Goal 进度</strong><span>完成后自动推进到下一项</span></div><div class="goal-board">${stage.goals.map(goal => { const current = goal.id === currentId; return `<div class="live-goal ${goal.status === "completed" ? "complete" : ""} ${current ? "current" : ""}"><span>${goal.status === "completed" ? "✓" : current ? "→" : "○"}</span><div><strong>${escapeHtml(goal.id)} · ${escapeHtml(goal.title)}</strong><small>${goal.artifact_ids?.length ? `对应 ${goal.artifact_ids.join(", ")}` : "基础设施 / 无直接图表"}</small></div>${current ? `<div class="goal-execution"><button data-command="${escapeHtml(stage.command)}" type="button">复制命令</button><button class="goal-terminal" data-terminal-command="${escapeHtml(stage.command)}" type="button">打开终端 →</button></div>` : `<b>${goal.status === "completed" ? "DONE" : escapeHtml(goal.status || "locked")}</b>`}</div>`; }).join("")}</div></div>`;
}

function missingStageMarkup(stage) {
  return `<div class="stage-command-card"><div><small>在终端中开始这一步</small><strong>${escapeHtml(stage.title)}尚未生成</strong><p>运行下面的命令。完成后回到这里刷新，页面会直接显示生成好的 canonical artifact。</p><code>${escapeHtml(stage.command)}</code></div><div class="stage-command-actions"><button data-command="${escapeHtml(stage.command)}" type="button">复制命令</button><button class="paper-launch" data-terminal-command="${escapeHtml(stage.command)}" type="button">打开终端 →</button></div></div>`;
}

function ideaMarkup(stage) {
  const selection = stage.idea_selection;
  if (stage.id !== "ideas" || !selection?.candidates?.length) return "";
  app.selectedIdea = app.selectedIdea || selection.selected_id || selection.candidates[0].id;
  return `<div class="content-section idea-picker"><div class="content-section-title"><strong>选择研究 Idea</strong><span>确认后写入 02_IDEA_REPORT.html</span></div><div class="idea-options">${selection.candidates.map(idea => `<button class="idea-option ${app.selectedIdea === idea.id ? "selected" : ""}" data-idea-id="${escapeHtml(idea.id)}" type="button"><span>${escapeHtml(idea.id)}</span><div><strong>${escapeHtml(idea.title)}</strong><small>${escapeHtml(idea.pitch)}</small></div><b>${selection.selected_id === idea.id ? "已确认" : "选择"}</b></button>`).join("")}</div><label class="idea-reason"><span>选择理由（可选）</span><textarea id="idea-reason" rows="2" maxlength="1000" placeholder="为什么它最值得进入实验规划？">${escapeHtml(selection.reason || "")}</textarea></label><div class="idea-confirm-row"><small>这是人工决策门；确认后，$expplan 将读取该选择。</small><button id="idea-confirm" class="paper-launch" type="button">${selection.selected_id === app.selectedIdea ? "更新确认" : "确认这个 Idea →"}</button></div></div>`;
}

function paperMarkup(stage) {
  if (stage.id !== "paper") return "";
  if (!stage.paper_studio?.configured) {
    return `<div class="content-section paper-entry unavailable"><div class="paper-studio-card"><span class="paper-studio-mark">P</span><div><small>PAPER WRITING WORKSPACE</small><strong>等待论文项目生成</strong><p>先运行 $paperwrite 创建论文配置，之后这里会出现“打开 Paper Studio”按钮。</p></div><button class="paper-launch" type="button" disabled>尚未配置</button></div></div>`;
  }
  return `<div class="content-section paper-entry"><div class="paper-studio-card"><span class="paper-studio-mark">P</span><div><small>PAPER WRITING WORKSPACE</small><strong>打开 Paper Studio</strong><p>在独立写作界面中逐段确认正文、编辑图表并编译论文 PDF。</p></div><button id="paper-launch" class="paper-launch" type="button">启动并打开 →</button></div></div>`;
}

function expplanApprovalMarkup(stage) {
  if (stage.id !== "expplan" || !stage.approval?.can_approve) return "";
  const approved = stage.approval.status === "approved";
  return `<div class="content-section approval-card ${approved ? "approved" : "pending"}"><span class="approval-mark">${approved ? "✓" : "!"}</span><div><small>HUMAN APPROVAL GATE</small><strong>${approved ? "实验设计已批准" : "确认实验设计"}</strong><p>${approved ? `批准日期：${escapeHtml(stage.approval.approved_at || "已记录")}。现在可以生成 Run Plan。` : "请先在右侧审阅图表、数据集、指标、baseline 与预算，再批准该设计。"}</p></div><button id="expplan-approve" class="paper-launch" type="button" ${approved ? "disabled" : ""}>${approved ? "已批准 ✓" : "批准实验设计 →"}</button></div>`;
}

function renderStage() {
  const stage = app.state.stages[app.stage];
  renderPipeline(); renderSidebar(stage);
  const primaryArtifact = stage.artifacts?.find(item => item.exists);
  const actionMarkup = `${paperMarkup(stage)}${ideaMarkup(stage)}${expplanApprovalMarkup(stage)}${goalMarkup(stage)}`;
  const bodyMarkup = `${primaryArtifact ? "" : missingStageMarkup(stage)}${actionMarkup}`;
  stageBody.innerHTML = bodyMarkup;
  stageBody.hidden = !bodyMarkup.trim();
  document.querySelector(".artifact-preview").hidden = !primaryArtifact;
  document.querySelector(".stage-surface").classList.toggle("missing-stage", !primaryArtifact);
  document.querySelector(".stage-surface").classList.toggle("preview-only", !bodyMarkup.trim());
  if (primaryArtifact) selectArtifact(primaryArtifact.key); else clearPreview();
}

function clearPreview() {
  previewFrame.hidden = true; previewFrame.removeAttribute("src");
  previewFrame.setAttribute("sandbox", artifactSandbox);
  previewEmpty.hidden = false; previewOpen.hidden = true; previewTitle.textContent = "等待生成";
}

function selectArtifact(key) {
  const stage = app.state.stages[app.stage];
  const artifact = stage.artifacts.find(item => item.key === key && item.exists);
  if (!artifact) return;
  previewTitle.textContent = artifact.title || artifact.path;
  previewOpen.href = artifact.url; previewOpen.hidden = false;
  const isPdf = artifact.path.toLowerCase().endsWith(".pdf");
  if (isPdf) previewFrame.removeAttribute("sandbox");
  else previewFrame.setAttribute("sandbox", artifactSandbox);
  previewFrame.src = isPdf ? `${artifact.url}#view=FitH` : artifact.url;
  previewFrame.hidden = false; previewEmpty.hidden = true;
}

async function loadState({preserveStage = true} = {}) {
  document.querySelector("#refresh").disabled = true;
  try {
    const response = await fetch("/api/state", {cache:"no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    app.state = await response.json();
    if (!preserveStage) setStage(Math.min(savedStage(), app.state.stages.length - 1));
    else if (app.stage >= app.state.stages.length) setStage(0);
    document.querySelector("#project-name").textContent = app.state.project.name;
    document.querySelector("#project-root").textContent = app.state.project.root;
    renderStage();
    showToast("已从项目文件刷新状态");
  } catch (error) {
    stageBody.innerHTML = `<div class="empty-guidance"><div><strong>Research Studio 加载失败</strong><p>${escapeHtml(error.message)}</p></div></div>`;
  } finally { document.querySelector("#refresh").disabled = false; }
}

async function startPaperStudio() {
  const button = document.querySelector("#paper-launch");
  if (button) { button.disabled = true; button.textContent = "正在启动…"; }
  try {
    const response = await fetch("/api/paper-studio/start", {method:"POST"});
    const result = await response.json();
    if (!result.ok) throw new Error(result.error || "启动失败");
    window.open(result.url, "paper-studio");
    showToast(result.already_running ? "Paper Studio 已在运行" : "Paper Studio 已启动");
  } catch (error) { showToast(`Paper Studio：${error.message}`); }
  finally { if (button) { button.disabled = false; button.textContent = "启动并打开 →"; } }
}

async function saveIdeaSelection() {
  const button = document.querySelector("#idea-confirm");
  if (!app.selectedIdea || !button) return;
  button.disabled = true; button.textContent = "正在写入…";
  try {
    const response = await fetch("/api/idea-selection", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({idea_id:app.selectedIdea, reason:document.querySelector("#idea-reason")?.value || ""})});
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "确认失败");
    await loadState();
    showToast(`${app.selectedIdea} 已写入 Idea Report`);
  } catch (error) { showToast(`Idea 选择：${error.message}`); }
  finally { if (button?.isConnected) button.disabled = false; }
}

async function approveExpplan() {
  const button = document.querySelector("#expplan-approve");
  if (!button || button.disabled) return;
  button.disabled = true; button.textContent = "正在写入批准状态…";
  try {
    const response = await fetch("/api/expplan/approve", {method:"POST"});
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "批准失败");
    await loadState();
    showToast("实验设计已批准，可运行 $runplan");
  } catch (error) {
    button.disabled = false; button.textContent = "批准实验设计 →";
    showToast(`实验设计审批：${error.message}`);
  }
}

async function openTerminal(command) {
  try {
    await navigator.clipboard.writeText(command);
    const response = await fetch("/api/terminal/open", {method:"POST"});
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "无法打开终端");
    showToast("终端已打开，Goal 命令已复制；粘贴后执行");
  } catch (error) { showToast(`打开终端：${error.message}`); }
}

pipeline.addEventListener("click", event => {
  const button = event.target.closest("[data-stage]");
  if (!button) return;
  setStage(Number(button.dataset.stage)); renderStage();
});
stageBody.addEventListener("click", event => {
  const idea = event.target.closest("[data-idea-id]");
  if (idea) { app.selectedIdea = idea.dataset.ideaId; renderStage(); }
  const command = event.target.closest("[data-command]");
  if (command) copyText(command.dataset.command);
  if (event.target.closest("#paper-launch")) startPaperStudio();
  if (event.target.closest("#idea-confirm")) saveIdeaSelection();
  if (event.target.closest("#expplan-approve")) approveExpplan();
  const terminalOpen = event.target.closest("[data-terminal-command]");
  if (terminalOpen) openTerminal(terminalOpen.dataset.terminalCommand);
});
document.querySelector("#sidebar-command").addEventListener("click", event => {
  const command = event.target.closest("[data-command]");
  if (command) copyText(command.dataset.command, command);
});
document.querySelector("#refresh").addEventListener("click", () => loadState());
document.addEventListener("keydown", event => {
  if (!app.state || !["ArrowLeft","ArrowRight"].includes(event.key)) return;
  const delta = event.key === "ArrowRight" ? 1 : -1;
  setStage((app.stage + delta + app.state.stages.length) % app.state.stages.length);
  renderStage();
});

loadState({preserveStage:false});
