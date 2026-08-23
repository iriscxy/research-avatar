const app = {
  state: null,
  stage: 0,
  previewSignature: "",
  loading: false,
  artifactByStage: {},
};
const pipeline = document.querySelector("#pipeline");
const previewFrame = document.querySelector("#preview-frame");
const previewEmpty = document.querySelector("#preview-empty");
const previewTitle = document.querySelector("#preview-title");
const previewOpen = document.querySelector("#preview-open");
const previewCommand = document.querySelector("#preview-command");
const previewCommandCopy = document.querySelector("#preview-command-copy");
const previewCopyStatus = document.querySelector("#preview-copy-status");
const artifactTabs = document.querySelector("#artifact-tabs");
const stageStorageKey = "research-studio.active-stage";
const artifactSandbox = "allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-downloads";

const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const statusLabel = status => ({complete:"Complete",in_progress:"In progress",waiting_confirmation:"Awaiting confirmation",not_started:"Not started"}[status] || status);

async function copyText(value) {
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

async function copyGoalFromArtifact(value) {
  if (!value.startsWith("/goal ") || value.length > 20000) return false;
  return copyText(value);
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
  document.body.classList.toggle("paper-focus", stage.id === "paper");
  renderPipeline();
  const command = stage.command || "Waiting for this stage to be generated";
  const copyableCommand = command.startsWith("python3 -m ");
  previewCommand.textContent = command;
  previewCommandCopy.hidden = !copyableCommand;
  previewCommandCopy.disabled = false;
  previewCommandCopy.textContent = "Copy command";
  previewCopyStatus.textContent = "";
  const availableArtifacts = stage.artifacts?.filter(item => item.exists) || [];
  const rememberedKey = app.artifactByStage[stage.id];
  const primaryArtifact = availableArtifacts.find(item => item.key === rememberedKey)
    || availableArtifacts.find(item => item.key === stage.default_artifact_key)
    || availableArtifacts[0];
  renderArtifactTabs(stage, primaryArtifact?.key || "");
  if (primaryArtifact) selectArtifact(primaryArtifact.key); else clearPreview();
}

function renderArtifactTabs(stage, selectedKey) {
  const available = stage.artifacts?.filter(item => item.exists) || [];
  artifactTabs.hidden = available.length < 2;
  artifactTabs.innerHTML = available.map(artifact => (
    `<button type="button" data-artifact-key="${escapeHtml(artifact.key)}" `
    + `class="artifact-tab ${artifact.key === selectedKey ? "active" : ""}">`
    + `${escapeHtml(artifact.key === "results" ? "Experiment results" : artifact.key === "runplan" ? "Run plan" : artifact.title)}`
    + "</button>"
  )).join("");
}

previewCommandCopy.addEventListener("click", async () => {
  const command = previewCommand.textContent.trim();
  if (!command.startsWith("python3 -m ")) return;
  previewCommandCopy.disabled = true;
  const copied = await copyText(command);
  previewCommandCopy.textContent = copied ? "Copied ✓" : "Copy failed";
  previewCopyStatus.textContent = copied
    ? "Command copied. Paste it into the project terminal."
    : "The browser cannot access the clipboard. Select the command manually.";
  window.setTimeout(() => {
    previewCommandCopy.disabled = false;
    previewCommandCopy.textContent = "Copy command";
    previewCopyStatus.textContent = "";
  }, 2200);
});

function clearPreview() {
  if (!app.previewSignature && !previewFrame.getAttribute("src")) return;
  app.previewSignature = "";
  previewFrame.hidden = true; previewFrame.removeAttribute("src");
  previewFrame.setAttribute("sandbox", artifactSandbox);
  previewEmpty.hidden = false; previewOpen.hidden = true; previewTitle.textContent = "Waiting for output";
}

function selectArtifact(key) {
  const stage = app.state.stages[app.stage];
  const artifact = stage.artifacts.find(item => item.key === key && item.exists);
  if (!artifact) return;
  app.artifactByStage[stage.id] = key;
  renderArtifactTabs(stage, key);
  previewTitle.textContent = artifact.title || artifact.path;
  previewOpen.href = artifact.url; previewOpen.hidden = artifact.interactive === true;
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

artifactTabs.addEventListener("click", event => {
  const button = event.target.closest("[data-artifact-key]");
  if (button) selectArtifact(button.dataset.artifactKey);
});

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
    previewTitle.textContent = `Load failed: ${error.message}`;
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
