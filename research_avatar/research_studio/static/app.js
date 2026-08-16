const app = { state: null, stage: 0, previewSignature: "", loading: false };
const pipeline = document.querySelector("#pipeline");
const previewFrame = document.querySelector("#preview-frame");
const previewEmpty = document.querySelector("#preview-empty");
const previewTitle = document.querySelector("#preview-title");
const previewOpen = document.querySelector("#preview-open");
const previewCommand = document.querySelector("#preview-command");
const stageStorageKey = "research-studio.active-stage";
const artifactSandbox = "allow-scripts allow-forms allow-popups allow-downloads";

const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const statusLabel = status => ({complete:"完成",in_progress:"进行中",waiting_confirmation:"等待确认",not_started:"未开始"}[status] || status);

async function copyGoalFromArtifact(value) {
  if (!value.startsWith("/goal ") || value.length > 20000) return false;
  try {
    if (!navigator.clipboard || !window.isSecureContext) throw new Error("clipboard unavailable");
    await navigator.clipboard.writeText(value);
    return true;
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
    return copied;
  }
}

window.addEventListener("message", async event => {
  if (event.source !== previewFrame.contentWindow) return;
  const message = event.data || {};
  if (message.type !== "research-studio-copy-goal" || typeof message.requestId !== "string") return;
  const copied = await copyGoalFromArtifact(String(message.value || ""));
  event.source.postMessage({
    type: "research-studio-copy-goal-result",
    requestId: message.requestId,
    copied,
  }, "*");
});
function savedStage() {
  const value = Number.parseInt(localStorage.getItem(stageStorageKey) || "0", 10);
  return Number.isFinite(value) && value >= 0 ? value : 0;
}

function setStage(index) {
  app.stage = index;
  localStorage.setItem(stageStorageKey, String(index));
}

function renderPipeline() {
  pipeline.innerHTML = app.state.stages.map((stage, index) => `<button class="pipeline-button ${index === app.stage ? "active" : ""}" data-stage="${index}" data-status="${escapeHtml(stage.status)}" type="button"><span>0${index + 1} · ${escapeHtml(statusLabel(stage.status))}</span><strong>${escapeHtml(stage.title)}</strong></button>`).join("");
}

function renderStage() {
  const stage = app.state.stages[app.stage];
  renderPipeline();
  previewCommand.textContent = stage.command || "请在终端运行对应 Skill";
  const primaryArtifact = stage.artifacts?.find(item => item.exists);
  if (primaryArtifact) selectArtifact(primaryArtifact.key); else clearPreview();
}

function clearPreview() {
  if (!app.previewSignature && !previewFrame.getAttribute("src")) return;
  app.previewSignature = "";
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
  const signature = `${app.stage}:${artifact.key}:${artifact.size}:${artifact.modified_ns || 0}`;
  if (signature === app.previewSignature) return;
  app.previewSignature = signature;
  const isPdf = artifact.path.toLowerCase().endsWith(".pdf");
  const isInteractive = artifact.interactive === true;
  if (isPdf || isInteractive) previewFrame.removeAttribute("sandbox");
  else previewFrame.setAttribute("sandbox", artifactSandbox);
  const versionedUrl = isInteractive
    ? artifact.url
    : `${artifact.url}?v=${artifact.modified_ns || artifact.size}`;
  previewFrame.src = isPdf ? `${versionedUrl}#view=FitH` : versionedUrl;
  previewFrame.hidden = false; previewEmpty.hidden = true;
  document.querySelectorAll("[data-artifact-key]").forEach(button => button.classList.toggle("active", button.dataset.artifactKey === key));
}

async function loadState({preserveStage = true} = {}) {
  if (app.loading) return;
  app.loading = true;
  try {
    const response = await fetch("/api/state", {cache:"no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    app.state = await response.json();
    if (!preserveStage) setStage(Math.min(savedStage(), app.state.stages.length - 1));
    else if (app.stage >= app.state.stages.length) setStage(0);
    renderStage();
  } catch (error) {
    clearPreview();
    previewTitle.textContent = `加载失败：${error.message}`;
  } finally {
    app.loading = false;
  }
}

pipeline.addEventListener("click", event => {
  const button = event.target.closest("[data-stage]");
  if (!button) return;
  setStage(Number(button.dataset.stage));
  // Navigation must remain immediate even when the two-second background
  // refresh currently owns loadState().  Otherwise a click can appear to be
  // ignored until the next poll and a quick reload opens a different tab.
  if (app.state) renderStage();
  loadState();
});
document.addEventListener("keydown", event => {
  if (!app.state || !["ArrowLeft","ArrowRight"].includes(event.key)) return;
  const delta = event.key === "ArrowRight" ? 1 : -1;
  setStage((app.stage + delta + app.state.stages.length) % app.state.stages.length);
  renderStage();
  loadState();
});
window.addEventListener("focus", () => { if (app.state) loadState(); });
document.addEventListener("visibilitychange", () => { if (!document.hidden && app.state) loadState(); });
setInterval(() => { if (!document.hidden) loadState(); }, 2000);

loadState({preserveStage:false});
