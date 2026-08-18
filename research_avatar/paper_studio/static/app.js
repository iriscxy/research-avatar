const $ = (id) => document.getElementById(id);
const STUDIO_BASE_PATH = window.location.pathname === "/demo-studio"
  || window.location.pathname.startsWith("/demo-studio/")
  ? "/demo-studio"
  : "";

function studioPath(path) {
  const value = String(path || "");
  if (!STUDIO_BASE_PATH || !value.startsWith("/") || value.startsWith("//")) return value;
  if (value === STUDIO_BASE_PATH || value.startsWith(STUDIO_BASE_PATH + "/")) return value;
  return STUDIO_BASE_PATH + value;
}

function normalizeStateUrls(value, key = "") {
  if (Array.isArray(value)) return value.map((item) => normalizeStateUrls(item));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([childKey, child]) => [
        childKey,
        normalizeStateUrls(child, childKey),
      ]),
    );
  }
  const urlLikeKey = key.endsWith("_url")
    || ["pdf", "png", "pptx", "preview", "draft"].includes(key);
  return typeof value === "string" && urlLikeKey ? studioPath(value) : value;
}
const ACTIVE_SECTION_KEY = "paper-studio.active-section";
const ACTIVE_VIEW_KEY = "paper-studio.active-view";
const ACTIVE_FIGURE_KEY = "paper-studio.active-figure";
const PDF_NAVIGATION_KEY = "paper-studio.pdf-navigation-visible";
const CAPTION_DRAFTS_KEY_PREFIX = "paper-studio.caption-drafts.";
const FIGURE_EDITOR_DRAFTS_KEY_PREFIX = "paper-studio.figure-editor-drafts.";
const PROSE_DRAFTS_KEY_PREFIX = "paper-studio.prose-drafts.";
const TITLE_DRAFTS_KEY_PREFIX = "paper-studio.title-drafts.";
const COMMENT_DRAFTS_KEY_PREFIX = "paper-studio.comment-drafts.";
const LEGACY_DRAFT_KEY_PREFIXES = [
  "paperstudio.caption-drafts.",
  "paperstudio.figure-editor-drafts.",
  "paperstudio.prose-drafts.",
  "paperstudio.title-drafts.",
  "paperstudio.comment-drafts.",
];
let state = null;
let pdfNavigationVisible = (() => {
  try {
    return localStorage.getItem(PDF_NAVIGATION_KEY) === "true";
  } catch (_error) {
    return false;
  }
})();
let activeView = (() => {
  const requested = new URLSearchParams(window.location.search).get("view");
  if (["writing", "figures", "tables"].includes(requested)) return requested;
  try {
    return localStorage.getItem(ACTIVE_VIEW_KEY) || "writing";
  } catch (_error) {
    return "writing";
  }
})();
let activeSection = (() => {
  const requested = new URLSearchParams(window.location.search).get("section");
  if (requested) return requested;
  try {
    return localStorage.getItem(ACTIVE_SECTION_KEY) || "abstract";
  } catch (_error) {
    return "abstract";
  }
})();
let activeFigure = (() => {
  try {
    return localStorage.getItem(ACTIVE_FIGURE_KEY) || "";
  } catch (_error) {
    return "";
  }
})();
const autoAttempted = new Set();
const autoFigurePromptAttempted = new Set();
const autoDataPanelAttempted = new Set();
const autoTableGenerateAttempted = new Set();
let figurePollTimer = null;
let fullDraftPollTimer = null;
let titleBusy = false;
let acceptRequestBusy = false;
let proseRequestBusy = false;
let paragraphRequestBusy = false;
let compileRequestBusy = false;
let conversationResetBusy = false;
let figureRequestBusy = false;
let generatedResetBusy = false;
let fullDraftRequestBusy = false;
let pdfLocateRequestId = 0;
let proseBaselineKey = "";
let proseBaselineText = "";
const mechanismPreviewModes = new Map();
const captionDrafts = new Map();
let captionDraftProjectId = "";
const figureEditorDrafts = new Map();
let figureEditorDraftProjectId = "";
const proseDrafts = new Map();
let proseDraftProjectId = "";
const titleDrafts = new Map();
let titleDraftProjectId = "";
const commentDrafts = new Map();
let commentDraftProjectId = "";

function syncCaptionDraftProject() {
  const projectId = String((state && state.project && state.project.id) || "");
  if (projectId === captionDraftProjectId) return;
  captionDraftProjectId = projectId;
  captionDrafts.clear();
  if (!projectId) return;
  try {
    const stored = JSON.parse(localStorage.getItem(CAPTION_DRAFTS_KEY_PREFIX + projectId) || "{}");
    Object.entries(stored).forEach(([figureId, value]) => {
      if (typeof value === "string") captionDrafts.set(figureId, value);
    });
  } catch (_error) {
    // Ignore unavailable storage and malformed browser-local drafts.
  }
}

function persistCaptionDrafts() {
  if (!captionDraftProjectId) return;
  try {
    localStorage.setItem(
      CAPTION_DRAFTS_KEY_PREFIX + captionDraftProjectId,
      JSON.stringify(Object.fromEntries(captionDrafts)),
    );
  } catch (_error) {
    // Storage can be unavailable in strict browser privacy modes.
  }
}

function rememberCaptionDraft(figureId, caption) {
  syncCaptionDraftProject();
  captionDrafts.set(figureId, caption);
  persistCaptionDrafts();
}

function forgetCaptionDraft(figureId) {
  syncCaptionDraftProject();
  captionDrafts.delete(figureId);
  persistCaptionDrafts();
}

function syncFigureEditorDraftProject() {
  const projectId = String((state && state.project && state.project.id) || "");
  if (projectId === figureEditorDraftProjectId) return;
  figureEditorDraftProjectId = projectId;
  figureEditorDrafts.clear();
  if (!projectId) return;
  try {
    const stored = JSON.parse(localStorage.getItem(FIGURE_EDITOR_DRAFTS_KEY_PREFIX + projectId) || "{}");
    Object.entries(stored).forEach(([figureId, fields]) => {
      if (fields && typeof fields === "object" && !Array.isArray(fields)) {
        figureEditorDrafts.set(figureId, fields);
      }
    });
  } catch (_error) {
    // Ignore unavailable storage and malformed browser-local drafts.
  }
}

function persistFigureEditorDrafts() {
  if (!figureEditorDraftProjectId) return;
  try {
    localStorage.setItem(
      FIGURE_EDITOR_DRAFTS_KEY_PREFIX + figureEditorDraftProjectId,
      JSON.stringify(Object.fromEntries(figureEditorDrafts)),
    );
  } catch (_error) {
    // Storage can be unavailable in strict browser privacy modes.
  }
}

function figureEditorDraft(figureId, field) {
  syncFigureEditorDraftProject();
  const fields = figureEditorDrafts.get(figureId);
  return fields && Object.prototype.hasOwnProperty.call(fields, field)
    ? fields[field]
    : undefined;
}

function rememberFigureEditorDraft(figureId, field, value, canonicalValue = "") {
  syncFigureEditorDraftProject();
  const canonical = String(canonicalValue || "");
  if (value === canonical) {
    forgetFigureEditorDraft(figureId, field);
    return;
  }
  const fields = {...(figureEditorDrafts.get(figureId) || {})};
  fields[field] = value;
  figureEditorDrafts.set(figureId, fields);
  persistFigureEditorDrafts();
}

function forgetFigureEditorDraft(figureId, field) {
  syncFigureEditorDraftProject();
  const fields = {...(figureEditorDrafts.get(figureId) || {})};
  delete fields[field];
  if (Object.keys(fields).length) figureEditorDrafts.set(figureId, fields);
  else figureEditorDrafts.delete(figureId);
  persistFigureEditorDrafts();
}

function renderFigureEditorInput(input, figureId, field, canonicalValue = "") {
  const canonical = String(canonicalValue || "");
  let draft = figureEditorDraft(figureId, field);
  if (draft === canonical) {
    forgetFigureEditorDraft(figureId, field);
    draft = undefined;
  }
  if (draft === undefined && input.value === canonical) {
    input.dataset.dirty = "false";
  }
  const changedFigure = input.dataset.figureId !== figureId;
  if (changedFigure || (input.dataset.dirty !== "true" && document.activeElement !== input)) {
    input.value = draft !== undefined ? draft : canonical;
    input.dataset.figureId = figureId;
    input.dataset.dirty = String(draft !== undefined);
  }
}

function syncProseDraftProject() {
  const projectId = String((state && state.project && state.project.id) || "");
  if (projectId === proseDraftProjectId) return;
  proseDraftProjectId = projectId;
  proseDrafts.clear();
  if (!projectId) return;
  try {
    const stored = JSON.parse(localStorage.getItem(PROSE_DRAFTS_KEY_PREFIX + projectId) || "{}");
    Object.entries(stored).forEach(([editorKey, draft]) => {
      if (draft && typeof draft.value === "string" && typeof draft.baseline === "string") {
        proseDrafts.set(editorKey, draft);
      }
    });
  } catch (_error) {
    // Ignore unavailable storage and malformed browser-local drafts.
  }
}

function persistProseDrafts() {
  if (!proseDraftProjectId) return;
  try {
    localStorage.setItem(
      PROSE_DRAFTS_KEY_PREFIX + proseDraftProjectId,
      JSON.stringify(Object.fromEntries(proseDrafts)),
    );
  } catch (_error) {
    // Storage can be unavailable in strict browser privacy modes.
  }
}

function rememberProseDraft(editorKey, value, baseline) {
  syncProseDraftProject();
  if (value === baseline) {
    forgetProseDraft(editorKey);
    return;
  }
  proseDrafts.set(editorKey, {value, baseline});
  persistProseDrafts();
}

function forgetProseDraft(editorKey) {
  syncProseDraftProject();
  proseDrafts.delete(editorKey);
  persistProseDrafts();
}

function syncTitleDraftProject() {
  const projectId = String((state && state.project && state.project.id) || "");
  if (projectId === titleDraftProjectId) return;
  titleDraftProjectId = projectId;
  titleDrafts.clear();
  if (!projectId) return;
  try {
    const stored = JSON.parse(localStorage.getItem(TITLE_DRAFTS_KEY_PREFIX + projectId) || "{}");
    Object.entries(stored).forEach(([field, value]) => {
      if (typeof value === "string") titleDrafts.set(field, value);
    });
  } catch (_error) {
    // Ignore unavailable storage and malformed browser-local drafts.
  }
}

function persistTitleDrafts() {
  if (!titleDraftProjectId) return;
  try {
    localStorage.setItem(
      TITLE_DRAFTS_KEY_PREFIX + titleDraftProjectId,
      JSON.stringify(Object.fromEntries(titleDrafts)),
    );
  } catch (_error) {
    // Storage can be unavailable in strict browser privacy modes.
  }
}

function rememberTitleDraft(field, value, canonicalValue = "") {
  syncTitleDraftProject();
  if (value === canonicalValue) titleDrafts.delete(field);
  else titleDrafts.set(field, value);
  persistTitleDrafts();
}

function forgetTitleDraft(field) {
  syncTitleDraftProject();
  titleDrafts.delete(field);
  persistTitleDrafts();
}

function renderTitleDraftInput(input, field, canonicalValue, force = false) {
  let draft = titleDrafts.get(field);
  if (draft === canonicalValue) {
    forgetTitleDraft(field);
    draft = undefined;
  }
  if (force || (input.dataset.dirty !== "true" && document.activeElement !== input)) {
    input.value = draft !== undefined ? draft : canonicalValue;
    input.dataset.dirty = String(draft !== undefined);
  }
}

function syncCommentDraftProject() {
  const projectId = String((state && state.project && state.project.id) || "");
  if (projectId === commentDraftProjectId) return;
  commentDraftProjectId = projectId;
  commentDrafts.clear();
  if (!projectId) return;
  try {
    const stored = JSON.parse(localStorage.getItem(COMMENT_DRAFTS_KEY_PREFIX + projectId) || "{}");
    Object.entries(stored).forEach(([editorKey, value]) => {
      if (typeof value === "string" && value) commentDrafts.set(editorKey, value);
    });
  } catch (_error) {
    // Ignore unavailable storage and malformed browser-local drafts.
  }
}

function persistCommentDrafts() {
  if (!commentDraftProjectId) return;
  try {
    localStorage.setItem(
      COMMENT_DRAFTS_KEY_PREFIX + commentDraftProjectId,
      JSON.stringify(Object.fromEntries(commentDrafts)),
    );
  } catch (_error) {
    // Storage can be unavailable in strict browser privacy modes.
  }
}

function rememberCommentDraft(editorKey, value) {
  syncCommentDraftProject();
  if (value) commentDrafts.set(editorKey, value);
  else commentDrafts.delete(editorKey);
  persistCommentDrafts();
}

function forgetCommentDraft(editorKey) {
  syncCommentDraftProject();
  commentDrafts.delete(editorKey);
  persistCommentDrafts();
}

function clearBrowserDraftsForProject(projectId) {
  if (!projectId) return;
  captionDrafts.clear();
  figureEditorDrafts.clear();
  proseDrafts.clear();
  titleDrafts.clear();
  commentDrafts.clear();
  mechanismPreviewModes.clear();
  proseBaselineKey = "";
  proseBaselineText = "";
  [
    CAPTION_DRAFTS_KEY_PREFIX,
    FIGURE_EDITOR_DRAFTS_KEY_PREFIX,
    PROSE_DRAFTS_KEY_PREFIX,
    TITLE_DRAFTS_KEY_PREFIX,
    COMMENT_DRAFTS_KEY_PREFIX,
    ...LEGACY_DRAFT_KEY_PREFIXES,
  ].forEach((prefix) => {
    try {
      localStorage.removeItem(prefix + projectId);
    } catch (_error) {
      // Storage can be unavailable in strict browser privacy modes.
    }
  });
}

function rememberActiveSection(section) {
  try {
    localStorage.setItem(ACTIVE_SECTION_KEY, section);
  } catch (_error) {
    // Storage can be unavailable in strict browser privacy modes.
  }
}

function uniqueArtifacts(artifacts = []) {
  const seen = new Set();
  return artifacts.filter((artifact) => {
    if (!artifact.id || seen.has(artifact.id)) return false;
    seen.add(artifact.id);
    return true;
  });
}

// POST-shaped but read-only: the gateway lets these through on a demo
// session too (see DEMO_SAFE_WRITE_PATHS in online_studio/server.py).
const DEMO_SAFE_WRITE_PATHS = new Set(["/api/pdf/locate"]);

async function request(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  // The gateway already refuses every other non-GET/HEAD request against a
  // demo session unconditionally; applyReadOnlyDemoRestrictions() keeps
  // every mutating control disabled so this should be unreachable in
  // normal use. This stays only as a defensive fallback -- no dialog to
  // redirect into.
  if (
    state
    && state.demo_mode
    && !["GET", "HEAD"].includes(method)
    && !DEMO_SAFE_WRITE_PATHS.has(path)
  ) {
    throw new Error("这是只读 Demo，无法生成或修改内容。");
  }
  const response = await fetch(studioPath(path), {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  const payload = await response.json().catch(() => ({error: response.statusText}));
  if (!response.ok || payload.ok === false) throw new Error(payload.error || payload.message || response.statusText);
  return normalizeStateUrls(payload);
}

function updateAcceptButton() {
  const section = state && state.sections && state.sections[activeSection];
  const paragraph = section && section.current_paragraph;
  const candidate = paragraph && paragraph.candidate;
  const accepted = paragraph && paragraph.accepted_text;
  const visibleText = $("candidate").value.trim();
  const manualRevision = Boolean(accepted) && visibleText !== proseBaselineText.trim();
  const canAccept = Boolean(visibleText) && Boolean(candidate || manualRevision);
  $("accept").disabled = !canAccept;
  $("accept").textContent = canAccept
    ? "Accept → LaTeX"
    : accepted
      ? "已写入 LaTeX"
      : "等待 candidate";
  $("accept").title = accepted && !canAccept
    ? "当前版本已写入 LaTeX；可直接修改正文，或填写 comment 让 GPT 生成新 candidate。"
    : "";
}

function setBusy(busy, label = "") {
  $("generate").disabled = busy;
  $("compile").disabled = busy;
  $("reset").disabled = busy;
  $("candidate").disabled = busy;
  $("comment").disabled = busy;
  $("model").disabled = busy;
  $("model-apply").disabled = busy;
  if (busy) {
    $("accept").disabled = true;
    const paragraph = state && state.sections && state.sections[activeSection]
      ? state.sections[activeSection].current_paragraph
      : null;
    if (paragraph && !$("candidate").value) {
      $("candidate").placeholder = "正在结合 reference paragraph、working abstract 和实验结果生成当前段落…";
    }
    $("message").textContent = label || "Working…";
  } else {
    updateAcceptButton();
    updateModelApplyButton();
  }
  document.querySelectorAll(".section-button").forEach((button) => {
    button.disabled = busy;
  });
  document.querySelectorAll(".paragraph-nav button").forEach((button) => {
    button.disabled = busy;
  });
  if (busy) {
    document.querySelectorAll(".figure-card, .figure-actions button").forEach((button) => {
      button.disabled = true;
    });
    $("figure-placement").disabled = true;
  } else if (["figures", "tables"].includes(activeView) && state) {
    document.querySelectorAll(".figure-card").forEach((button) => {
      button.disabled = false;
    });
    updateFigureButtonStates();
  }
}

function updateModelApplyButton() {
  const visibleModel = $("model").value.trim();
  $("model-apply").disabled = conversationResetBusy
    || proseRequestBusy
    || fullDraftRequestBusy
    || titleBusy
    || !visibleModel
    || visibleModel === String((state && state.model) || "gpt-5-nano");
}

function showMessage(message, error = false) {
  $("message").textContent = message || "";
  $("message").classList.toggle("error", error);
}

function updateTitleSaveButton() {
  const editor = (state && state.title_editor) || {};
  const visibleTitle = $("paper-title").value.replace(/\s+/g, " ").trim();
  const currentTitle = String(editor.current_title || "").replace(/\s+/g, " ").trim();
  const changed = Boolean(visibleTitle) && visibleTitle !== currentTitle;
  $("title-save").disabled = titleBusy || !changed;
  $("title-save").textContent = changed ? "确认写入 LaTeX" : "已写入 PDF";
  $("title-save").title = changed ? "确认后更新 LaTeX 并重新编译 PDF。" : "当前标题已经写入 PDF。";
}

function setTitleBusy(busy, message = "") {
  titleBusy = busy;
  $("title-generate").disabled = busy;
  $("paper-title").disabled = busy;
  $("title-gpt-prompt").disabled = busy;
  if (busy) {
    $("title-save").disabled = true;
  } else {
    updateTitleSaveButton();
  }
  if (message) {
    $("title-status").textContent = message;
    $("title-status").classList.remove("error");
  }
}

function renderTitleEditor(force = false) {
  const editor = state.title_editor || {};
  const titleInput = $("paper-title");
  const promptInput = $("title-gpt-prompt");
  $("title-current-summary").textContent = editor.current_title || "未找到标题";
  renderTitleDraftInput(titleInput, "title", editor.candidate || editor.current_title || "", force);
  renderTitleDraftInput(promptInput, "prompt", editor.prompt || "", force);
  $("title-status").textContent = editor.last_message || (
    editor.candidate ? "GPT candidate 尚未保存；可编辑后确认。" : "修改后需确认，才会写入 LaTeX。"
  );
  $("title-status").classList.remove("error");
  if (!titleBusy) $("title-generate").disabled = false;
  updateTitleSaveButton();
}

function renderSections() {
  const root = $("sections");
  root.innerHTML = "";
  Object.entries(state.sections).forEach(([key, section]) => {
    const button = document.createElement("button");
    button.className = "section-button" + (key === activeSection ? " active" : "");
    const dot = section.conversation_active ? "active" : "";
    button.innerHTML = `${section.title}<span class="dot ${dot}"></span>`;
    button.onclick = () => {
      activeSection = key;
      activeView = "writing";
      rememberActiveSection(key);
      try {
        localStorage.setItem(ACTIVE_VIEW_KEY, activeView);
      } catch (_error) {}
      render();
    };
    root.appendChild(button);
  });
}

function renderParagraphNavigation(section) {
  const root = $("paragraph-nav");
  root.innerHTML = "";
  (section.paragraph_navigation || []).forEach((paragraph) => {
    const button = document.createElement("button");
    button.textContent = paragraph.id;
    const artifacts = uniqueArtifacts(paragraph.artifacts || []);
    const visibleArtifacts = artifacts;
    if (visibleArtifacts.length) {
      const badge = document.createElement("span");
      badge.className = "nav-artifact";
      badge.textContent = `◆${visibleArtifacts.map((item) => item.id).join("/")}`;
      button.appendChild(badge);
    }
    button.title = `${paragraph.status}: ${paragraph.purpose}${artifacts.length ? ` · 关联 ${artifacts.map((item) => item.id).join(", ")}` : ""}`;
    button.className = `${paragraph.status}${paragraph.selected ? " selected" : ""}${visibleArtifacts.length ? " has-artifact" : ""}`;
    button.dataset.paragraphId = paragraph.id;
    button.disabled = false;
    button.onclick = async () => {
      if (paragraph.selected || paragraphRequestBusy) return;
      paragraphRequestBusy = true;
      const requestedSection = activeSection;
      try {
        setBusy(true, `正在切换到 ${paragraph.id}…`);
        const payload = await request("/api/select-paragraph", {
          method: "POST",
          body: JSON.stringify({
            section: requestedSection,
            paragraph_id: paragraph.id,
          }),
        });
        state = payload.state;
        if (activeSection === requestedSection) {
          render();
          showMessage(
            paragraph.status === "accepted"
              ? `已切换到 ${paragraph.id}；可基于已接受版本继续修改。`
              : `已切换到 ${paragraph.id}。`,
          );
        } else {
          renderSections();
        }
      } catch (error) {
        showMessage(error.message, true);
      } finally {
        paragraphRequestBusy = false;
        setBusy(false);
      }
    };
    root.appendChild(button);
  });
}

function capturePdfPosition(pages) {
  const pageElements = [...pages.querySelectorAll(".pdf-page")];
  if (!pageElements.length || !pages.clientHeight) return null;
  const center = pages.scrollTop + pages.clientHeight / 2;
  const page = pageElements.find((item) => (
    center >= item.offsetTop && center <= item.offsetTop + item.offsetHeight
  )) || pageElements.reduce((closest, item) => (
    Math.abs(item.offsetTop + item.offsetHeight / 2 - center)
      < Math.abs(closest.offsetTop + closest.offsetHeight / 2 - center)
      ? item
      : closest
  ));
  return {
    page: page.dataset.page,
    ratio: page.offsetHeight
      ? (center - page.offsetTop) / page.offsetHeight
      : 0,
  };
}

function restorePdfPosition(pages, position) {
  if (!position) return;
  requestAnimationFrame(() => {
    const page = pages.querySelector(`[data-page="${position.page}"]`);
    if (!page) return;
    const center = page.offsetTop + position.ratio * page.offsetHeight;
    pages.scrollTop = Math.max(0, center - pages.clientHeight / 2);
    updatePdfPageIndicator();
  });
}

function updatePdfPageIndicator() {
  const pages = $("pdf-pages");
  const indicator = $("pdf-page-indicator");
  const position = capturePdfPosition(pages);
  const total = Number(state && state.pdf && state.pdf.page_count) || 0;
  indicator.textContent = position && total
    ? `第 ${position.page} / ${total} 页`
    : "第 — / — 页";
  $("pdf-navigation").querySelectorAll(".pdf-thumbnail").forEach((thumbnail) => {
    thumbnail.classList.toggle("active", thumbnail.dataset.page === (position && position.page));
  });
}

function renderPdf() {
  const viewer = $("pdf-viewer");
  const pages = $("pdf-pages");
  const navigationRoot = $("pdf-navigation");
  const empty = $("pdf-empty");
  const toggle = $("pdf-navigation-toggle");
  const download = $("pdf-download");
  toggle.textContent = pdfNavigationVisible ? "隐藏导航栏" : "显示导航栏";
  toggle.setAttribute("aria-pressed", pdfNavigationVisible ? "true" : "false");
  if (state.pdf.exists) {
    download.hidden = false;
    download.href = studioPath(state.pdf.url || "/paper.pdf");
    download.download = `${String(state.project && state.project.id || "paper").replace(/[^A-Za-z0-9._-]+/g, "-")}.pdf`;
    viewer.style.display = "flex";
    viewer.classList.toggle("navigation-visible", pdfNavigationVisible);
    empty.style.display = "none";
    const signature = `${state.pdf.version}:${state.pdf.page_count}`;
    if (pages.dataset.signature !== signature) {
      const previousPosition = capturePdfPosition(pages);
      pages.replaceChildren();
      for (let pageNumber = 1; pageNumber <= state.pdf.page_count; pageNumber += 1) {
        const page = document.createElement("div");
        page.className = "pdf-page";
        page.dataset.page = String(pageNumber);
        page.style.aspectRatio = `${state.pdf.page_width_pt} / ${state.pdf.page_height_pt}`;
        page.title = "双击正文、图片或表格，返回对应编辑位置";
        const image = document.createElement("img");
        image.alt = `论文 PDF 第 ${pageNumber} 页`;
        image.draggable = false;
        image.src = studioPath(`/paper-page/${pageNumber}.svg?v=${state.pdf.version}`);
        page.appendChild(image);
        page.ondblclick = (event) => locatePdfEditTarget(event, page);
        pages.appendChild(page);
      }
      pages.dataset.signature = signature;
      restorePdfPosition(pages, previousPosition);
    }
    if (pdfNavigationVisible && navigationRoot.dataset.signature !== signature) {
      navigationRoot.replaceChildren();
      for (let pageNumber = 1; pageNumber <= state.pdf.page_count; pageNumber += 1) {
        const thumbnail = document.createElement("button");
        thumbnail.className = "pdf-thumbnail";
        thumbnail.type = "button";
        thumbnail.dataset.page = String(pageNumber);
        thumbnail.title = `转到第 ${pageNumber} 页`;
        const image = document.createElement("img");
        image.alt = `第 ${pageNumber} 页`;
        image.src = studioPath(`/paper-page/${pageNumber}.svg?v=${state.pdf.version}`);
        thumbnail.appendChild(image);
        thumbnail.onclick = () => {
          const target = pages.querySelector(`[data-page="${pageNumber}"]`);
          if (target) target.scrollIntoView({behavior: "smooth", block: "start"});
        };
        navigationRoot.appendChild(thumbnail);
      }
      navigationRoot.dataset.signature = signature;
    }
    pages.onscroll = updatePdfPageIndicator;
    requestAnimationFrame(updatePdfPageIndicator);
  } else {
    download.hidden = true;
    viewer.style.display = "none";
    empty.style.display = "flex";
    updatePdfPageIndicator();
  }
  const compile = state.compile || {};
  $("compile-status").textContent = compile.status || "not_run";
  $("compile-status").className = "status " + (compile.status === "ok" ? "ok" : compile.status === "failed" ? "warn" : "");
}

async function locatePdfEditTarget(event, pageElement) {
  const locateRequestId = ++pdfLocateRequestId;
  const rectangle = pageElement.getBoundingClientRect();
  if (!rectangle.width || !rectangle.height) return;
  const page = Number(pageElement.dataset.page);
  const x = (event.clientX - rectangle.left) / rectangle.width * state.pdf.page_width_pt;
  const y = (event.clientY - rectangle.top) / rectangle.height * state.pdf.page_height_pt;
  try {
    showMessage("正在定位 PDF 中的源内容…");
    const payload = await request("/api/pdf/locate", {
      method: "POST",
      body: JSON.stringify({page, x, y}),
    });
    if (locateRequestId !== pdfLocateRequestId) return;
    const target = payload.target;
    activeSection = target.section;
    activeView = target.view;
    rememberActiveSection(activeSection);
    try {
      localStorage.setItem(ACTIVE_VIEW_KEY, activeView);
    } catch (_error) {}
    if (target.view === "writing") {
      const selected = await request("/api/select-paragraph", {
        method: "POST",
        body: JSON.stringify({
          section: target.section,
          paragraph_id: target.paragraph_id,
        }),
      });
      if (locateRequestId !== pdfLocateRequestId) return;
      state = selected.state;
      render();
      showMessage(`已从 PDF 返回 ${target.paragraph_id} 的文字编辑位置。`);
      return;
    }
    activeFigure = target.artifact_id;
    try {
      localStorage.setItem(ACTIVE_FIGURE_KEY, activeFigure);
    } catch (_error) {}
    render();
    $("figure-message").textContent = `已从 PDF 返回 ${target.artifact_id} 的${target.view === "tables" ? "表格" : "图片"}编辑位置。`;
  } catch (error) {
    if (locateRequestId !== pdfLocateRequestId) return;
    showMessage(error.message, true);
  }
}

$("pdf-navigation-toggle").onclick = () => {
  pdfNavigationVisible = !pdfNavigationVisible;
  try {
    localStorage.setItem(PDF_NAVIGATION_KEY, String(pdfNavigationVisible));
  } catch (_error) {}
  renderPdf();
};

function sectionFigures() {
  const paragraph = state.sections[activeSection].current_paragraph;
  const relatedIds = new Set(
    (paragraph && paragraph.artifacts || [])
      .filter((artifact) => activeView === "tables" ? artifact.kind === "table" : artifact.kind === "figure")
      .map((artifact) => artifact.id),
  );
  const collection = activeView === "tables" ? (state.tables || []) : (state.figures || []);
  return collection.filter((artifact) =>
    (artifact.source_sections || []).includes(activeSection)
    || (artifact.related_paragraphs && artifact.related_paragraphs[activeSection])
    || relatedIds.has(artifact.id)
  );
}

function selectedFigure() {
  const figures = sectionFigures();
  return figures.find((figure) => figure.id === activeFigure) || figures[0];
}

function figureIsRunning(figure) {
  return ["prompt_generating", "image_generating", "agent_generating", "agent_editing"].includes(figure.status);
}

function updateMechanismFlow(figure) {
  if (!figure || figure.kind !== "mechanism") return;
  const promptReady = Boolean(String(figure.draw_prompt || "").trim());
  const imageReady = Boolean(figure.gpt_preview_url);
  const paperReady = Boolean(
    figure.paper_preview_url
    || ((figure.downloads || {}).pdf && (figure.downloads || {}).pptx)
  );
  const promptActive = figure.status === "prompt_generating" || !promptReady;
  const imageActive = figure.status === "image_generating"
    || (promptReady && !imageReady && figure.status !== "prompt_generating");
  const paperActive = ["agent_generating", "agent_editing"].includes(figure.status)
    || (imageReady && !paperReady && figure.status !== "image_generating");
  const stages = [
    {
      id: "prompt",
      ready: promptReady,
      active: promptActive,
      status: figure.status === "prompt_generating" ? "生成中" : (promptReady ? "已就绪" : "待生成"),
    },
    {
      id: "image",
      ready: imageReady,
      active: imageActive,
      status: figure.status === "image_generating" ? "绘制中" : (imageReady ? "已归档" : "等待 Prompt"),
    },
    {
      id: "paper",
      ready: paperReady,
      active: paperActive,
      status: ["agent_generating", "agent_editing"].includes(figure.status)
        ? "自动重建中"
        : (paperReady ? "已完成" : "随后自动重建"),
    },
  ];
  stages.forEach((stage) => {
    const node = $(`mechanism-flow-${stage.id}`);
    node.classList.toggle("is-complete", stage.ready);
    node.classList.toggle("is-active", stage.active);
    node.setAttribute("aria-current", stage.active ? "step" : "false");
    $(`mechanism-flow-${stage.id}-status`).textContent = stage.status;
  });
}

function updateFigureButtonStates() {
  const figure = selectedFigure();
  if (!figure) return;
  const running = figureIsRunning(figure) || figureRequestBusy;
  const table = figure.kind === "table";
  const generationReady = figure.generation_ready !== false;
  const insertionReady = figure.insertion_ready === undefined
    ? figure.ready
    : figure.insertion_ready;
  const captionDirty = $("figure-caption").dataset.dirty === "true";
  const submittedPrompt = $("draw-prompt").value.trim();
  const promptInstruction = $("prompt-instruction").value.trim();
  $("figure-prompt").disabled = state.demo_mode
    || !figure.ready || !generationReady || running || Boolean(submittedPrompt && !promptInstruction);
  $("figure-draw").disabled = !figure.ready || !generationReady || running || !submittedPrompt;
  const promptUnchanged = Boolean(
    figure.gpt_preview_url
    && submittedPrompt
    && submittedPrompt === String(figure.draw_prompt || "").trim()
  );
  $("figure-draw").textContent = figure.gpt_preview_url
    ? (promptUnchanged
      ? "Prompt 未变 → 显示原图"
      : "确认新 Prompt → 重新调用 GPT Image")
    : "确认 Prompt → GPT Image";
  $("figure-cancel").hidden = figure.status !== "image_generating";
  $("figure-cancel").disabled = figure.status !== "image_generating" || figureRequestBusy;
  const mechanismBuildFailed = Boolean(
    figure.kind === "mechanism"
    && figure.status === "failed"
    && figure.gpt_preview_url
    && !figure.paper_preview_url
  );
  $("figure-build").hidden = !mechanismBuildFailed;
  $("figure-build").disabled = !figure.ready || !generationReady || running || !figure.preview_url;
  $("figure-build").textContent = "重试可编辑 PPT/PDF 重建";
  $("figure-approve").disabled = (
    table
    || !insertionReady
    || !(figure.downloads || {}).pdf
    || !(figure.downloads || {}).pptx
    || (figure.status === "approved" && !captionDirty)
  );
  const panelsReady = (figure.panels || []).length > 0 && (figure.panels || []).every((panel) => panel.status === "built");
  const loadedCandidate = $("figure-preview-pdf").dataset.loaded;
  const expectedCandidate = figure.preview_url
    ? `${figure.preview_url}#toolbar=0&navpanes=0&view=FitH`
    : "";
  $("data-compose").disabled = table || !figure.ready || running || !panelsReady;
  $("single-data-generate").disabled = table || !figure.ready || running;
  $("data-compose").textContent = figure.composition_ready
    ? "重新解析 Prompt 并生成合成图"
    : "合成图";
  $("data-approve").disabled = (
    table
    || !insertionReady
    || !figure.composition_ready
    || !(figure.downloads || {}).pdf
    || loadedCandidate !== expectedCandidate
  );
  $("data-approve-after-placement").hidden = !(
    figure.kind === "data"
    && figure.composition_ready
    && loadedCandidate === expectedCandidate
  );
  const hasPlacement = (figure.placement_options || []).some((option) => option.accepted);
  $("figure-placement").disabled = running || !hasPlacement;
  $("figure-layout-mode").disabled = running || table || !hasPlacement;
  $("figure-approve").textContent = figure.status === "approved"
    ? (captionDirty ? "更新 Caption → PDF" : "已插入正文")
    : "确认并插入正文";
  $("data-approve").textContent = figure.status === "approved"
    ? (captionDirty ? "更新 Caption → PDF" : "重新插入")
    : "确认并插入正文";
  const visibleTableLatex = $("table-latex").value.trim();
  const tableLatexDirty = $("table-latex").dataset.dirty === "true";
  $("table-generate").disabled = !table || !figure.ready || running;
  $("table-agent-edit").disabled = !table || !figure.ready || running || !visibleTableLatex;
  $("table-save").disabled = !table || running || !visibleTableLatex || !tableLatexDirty;
  $("table-save").textContent = figure.status === "approved" && tableLatexDirty
    ? "保存修改（需重新确认）"
    : "保存修改";
  $("table-approve").disabled = (
    !table
    || !figure.ready
    || running
    || !visibleTableLatex
    || (figure.status === "approved" && !tableLatexDirty)
  );
  $("table-approve").textContent = figure.status === "approved"
    ? (tableLatexDirty ? "更新表格 → PDF" : "已插入正文")
    : "确认并插入正文";
  $("figure-caption").disabled = table || running;
  $("figure-caption-prompt").disabled = table || running;
  $("figure-caption-generate").disabled = table || running;
  $("figure-caption-save").disabled = table || running || !captionDirty;
  $("figure-caption-save").textContent = figure.status === "approved"
    ? "保存 Caption 并更新 PDF"
    : "保存 Caption";
  $("draw-prompt").disabled = running;
  $("prompt-instruction").disabled = running;
  $("single-data-prompt").disabled = running;
  $("data-layout-prompt").disabled = running;
  $("table-prompt").disabled = running;
  $("table-agent-prompt").disabled = running;
  $("table-latex").disabled = running;
  document.querySelectorAll(".data-panel textarea").forEach((control) => {
    control.disabled = running;
  });
  document.querySelectorAll(".data-panel button").forEach((control) => {
    control.disabled = running || !figure.ready;
  });
}

function renderSingleDataFigure(figure) {
  const panel = (figure.panels || [])[0];
  if (!panel) return;
  $("data-panels").replaceChildren();
  $("data-panels").dataset.figureId = figure.id;
  const input = $("single-data-prompt");
  renderFigureEditorInput(input, figure.id, `panel:${panel.id}`, panel.agent_prompt || "");
  const generate = $("single-data-generate");
  generate.textContent = panel.preview_url
    ? "本地 Agent 重新生成这张图"
    : "本地 Agent 生成这张图";
  generate.onclick = () => startFigureJob(
    "/api/figure/panel/generate",
    {
      figure_id: figure.id,
      panel_id: panel.id,
      agent_prompt: input.value,
      layout_prompt: "",
      layout_width: $("figure-layout-mode").value === "two-column"
        ? "two-column"
        : "single-column",
    },
    `正在生成 ${figure.id} 最终单图…`,
  );
}

function renderDataPanels(figure) {
  const root = $("data-panels");
  if (root.dataset.figureId !== figure.id) {
    root.replaceChildren();
    root.dataset.figureId = figure.id;
  }
  const expectedPanels = new Set((figure.panels || []).map((panel) => panel.id));
  root.querySelectorAll(".data-panel").forEach((card) => {
    if (!expectedPanels.has(card.dataset.panelId)) card.remove();
  });
  (figure.panels || []).forEach((panel) => {
    let card = [...root.querySelectorAll(".data-panel")].find(
      (item) => item.dataset.panelId === panel.id,
    );
    if (!card) {
      card = document.createElement("section");
      card.className = "data-panel";
      card.dataset.panelId = panel.id;
      card.innerHTML = `
        <div class="data-panel-head"><strong></strong><span class="status"></span></div>
        <div class="data-panel-preview"></div>
        <div class="figure-progress data-panel-progress" hidden>
          <div class="figure-progress-track"><span></span></div><strong></strong>
        </div>
        <label class="data-panel-prompt-label">这张子图的修改 Prompt</label>
        <textarea class="data-panel-prompt" rows="3" placeholder="例如：缩短标题，把图例移到右上角；只调整这一张图，不改变数据。"></textarea>
        <div class="data-panel-actions"><button class="primary data-panel-generate"></button></div>
        <pre class="message data-panel-message" hidden></pre>
      `;
      card.querySelector(".data-panel-prompt").addEventListener("input", (event) => {
        event.currentTarget.dataset.dirty = "true";
        const currentFigure = selectedFigure();
        if (currentFigure) {
          const currentPanel = (currentFigure.panels || []).find(
            (item) => item.id === card.dataset.panelId,
          );
          rememberFigureEditorDraft(
            currentFigure.id,
            `panel:${card.dataset.panelId}`,
            event.currentTarget.value,
            (currentPanel && currentPanel.agent_prompt) || "",
          );
        }
      });
      root.appendChild(card);
    }

    const singlePanel = (figure.panels || []).length === 1;
    const title = card.querySelector(".data-panel-head strong");
    title.textContent = singlePanel
      ? `${figure.id} · ${figure.title}`
      : `${figure.id}(${panel.id}) · ${panel.title}`;
    card.querySelector(".data-panel-prompt-label").textContent = singlePanel
      ? "这张图的修改 Prompt"
      : "这张子图的修改 Prompt";
    const status = card.querySelector(".data-panel-head .status");
    status.className = `status ${panel.status === "built" ? "ok" : ""}`;
    status.textContent = panel.status;

    const preview = card.querySelector(".data-panel-preview");
    if (panel.preview_url) {
      if (panel.preview_type === "pdf") {
        const target = `${panel.preview_url}#toolbar=0&navpanes=0&view=FitH`;
        let frame = preview.querySelector(".data-panel-pdf");
        if (!frame || frame.dataset.source !== target) {
          frame = document.createElement("iframe");
          frame.className = "data-panel-pdf";
          frame.src = target;
          frame.dataset.source = target;
          frame.title = singlePanel
            ? `${figure.id} vector PDF candidate`
            : `${figure.id}(${panel.id}) vector PDF candidate`;
          preview.replaceChildren(frame);
        }
      } else {
        let panelImage = preview.querySelector("img");
        if (!panelImage || panelImage.dataset.source !== panel.preview_url) {
          panelImage = document.createElement("img");
          panelImage.src = panel.preview_url;
          panelImage.dataset.source = panel.preview_url;
          panelImage.alt = `${figure.id}(${panel.id}) preview`;
          preview.replaceChildren(panelImage);
        }
      }
    } else {
      if (!preview.querySelector(".data-panel-empty")) {
        const panelEmpty = document.createElement("div");
        panelEmpty.className = "data-panel-empty";
        panelEmpty.textContent = singlePanel ? "尚未生成这张图" : "尚未生成这张独立子图";
        preview.replaceChildren(panelEmpty);
      }
    }

    const progress = card.querySelector(".data-panel-progress");
    progress.hidden = panel.status !== "agent_generating";
    progress.querySelector(".figure-progress-track span").style.width = `${Math.max(0, Math.min(100, panel.progress || 0))}%`;
    progress.querySelector("strong").textContent = panel.progress_message
      || (singlePanel ? "本地 Agent 正在处理这张图…" : "本地 Agent 正在处理这张子图…");

    const input = card.querySelector(".data-panel-prompt");
    renderFigureEditorInput(input, figure.id, `panel:${panel.id}`, panel.agent_prompt || "");
    const generate = card.querySelector(".data-panel-generate");
    generate.textContent = panel.preview_url ? "本地 Agent 重新生成这张" : "本地 Agent 生成这张";
    generate.onclick = () => startFigureJob(
      "/api/figure/panel/generate",
      {
        figure_id: figure.id,
        panel_id: panel.id,
        agent_prompt: input.value,
        layout_prompt: $("data-layout-prompt").value,
        layout_width: $("figure-layout-mode").value === "two-column"
          ? "two-column"
          : "single-column",
      },
      singlePanel
        ? `正在生成 ${figure.id} 最终单图…`
        : `正在单独生成 ${figure.id}(${panel.id})…`,
    );
    const panelMessage = card.querySelector(".data-panel-message");
    panelMessage.hidden = !panel.last_message;
    panelMessage.textContent = panel.last_message || "";
  });
}

function scheduleAutomaticDataPanel(figure) {
  if (
    activeView !== "figures"
    || figure.kind !== "data"
    || !figure.ready
    || figure.generation_ready === false
    || figureIsRunning(figure)
  ) return;
  const nextPanel = (figure.panels || []).find(
    (panel) => panel.status === "pending" && !panel.preview_url,
  );
  if (!nextPanel) return;
  const attemptKey = `${figure.id}:${nextPanel.id}`;
  if (autoDataPanelAttempted.has(attemptKey)) return;
  autoDataPanelAttempted.add(attemptKey);
  setTimeout(() => {
    const current = selectedFigure();
    if (
      !current
      || current.id !== figure.id
      || current.generation_ready === false
      || figureIsRunning(current)
    ) return;
    const currentNext = (current.panels || []).find(
      (panel) => panel.status === "pending" && !panel.preview_url,
    );
    if (!currentNext || currentNext.id !== nextPanel.id) return;
    const singlePanel = (current.panels || []).length === 1;
    const card = [...$("data-panels").querySelectorAll(".data-panel")].find(
      (item) => item.dataset.panelId === currentNext.id,
    );
    const agentPrompt = singlePanel
      ? $("single-data-prompt").value
      : (card && card.querySelector(".data-panel-prompt").value) || "";
    startFigureJob(
      "/api/figure/panel/generate",
      {
        figure_id: current.id,
        panel_id: currentNext.id,
        agent_prompt: agentPrompt,
        layout_prompt: singlePanel ? "" : $("data-layout-prompt").value,
        layout_width: $("figure-layout-mode").value === "two-column"
          ? "two-column"
          : "single-column",
      },
      singlePanel
        ? `正在自动生成 ${current.id} 最终单图 candidate…`
        : `正在自动生成 ${current.id}(${currentNext.id})；完成后继续下一张…`,
    );
  }, 50);
}

function scheduleAutomaticTableGenerate(figure) {
  // Reported directly: a researcher clicked into an empty table and nothing
  // happened -- generating one required finding "table-generate", which
  // sits inside a collapsed "高级" (Advanced) <details> disclosure. Data
  // figures already auto-generate the moment their panel is viewable (see
  // scheduleAutomaticDataPanel above); tables never had the equivalent, so
  // this mirrors that same pattern instead of requiring a manual click.
  if (
    activeView !== "tables"
    || figure.kind !== "table"
    || !figure.ready
    || figure.status !== "pending"
    || figureIsRunning(figure)
  ) return;
  if (autoTableGenerateAttempted.has(figure.id)) return;
  autoTableGenerateAttempted.add(figure.id);
  setTimeout(() => {
    const current = selectedFigure();
    if (
      !current
      || current.id !== figure.id
      || current.status !== "pending"
      || figureIsRunning(current)
    ) return;
    if (figureRequestBusy) {
      // Reported directly: switching straight from one pending table to
      // another (T1's auto-generate still in flight, then clicking into
      // T2) made T2 stay "pending" forever. runFigureAction shares one
      // global busy lock across every figure/table action and silently
      // no-ops while it's held -- but this function had already marked
      // T2 "attempted" before learning that, so it could never retry.
      // Un-mark it so the next render (state polling already runs
      // continuously) schedules a fresh attempt once the lock clears.
      autoTableGenerateAttempted.delete(figure.id);
      return;
    }
    runFigureAction(
      "/api/table/generate",
      {
        table_id: current.id,
        generation_prompt: $("table-prompt").value,
      },
      `正在自动生成 ${current.id} 表格初稿…`,
    );
  }, 50);
}

function renderLayoutPrompt(figure) {
  const input = $("data-layout-prompt");
  const singlePanel = (figure.panels || []).length === 1;
  renderFigureEditorInput(input, figure.id, "layout_prompt", figure.layout_prompt || "");
  const plan = figure.layout_plan || {};
  $("data-workflow-note").textContent = singlePanel
    ? "这是一张独立单图：点击下方按钮后直接生成最终 PDF candidate，不添加子图角标。"
    : "请分别生成并检查每张 PDF candidate。全部满意后，再手动点击“合成图”生成 PPTX 与矢量 PDF candidate。";
  $("data-layout-prompt-label").hidden = singlePanel;
  input.hidden = singlePanel;
  $("data-compose-actions").hidden = singlePanel;
  $("data-composition-editor").hidden = singlePanel;
  $("single-data-controls").hidden = !singlePanel;
  $("data-panels").hidden = singlePanel;
  $("data-layout-plan-wrap").hidden = singlePanel || !Object.keys(plan).length;
  $("data-layout-plan").textContent = Object.keys(plan).length
    ? JSON.stringify(plan, null, 2)
    : "";
}

function markFigurePdfLoaded(figureId, target) {
  const pdf = $("figure-preview-pdf");
  const current = selectedFigure();
  if (!current || current.id !== figureId || pdf.dataset.source !== target) return;
  pdf.dataset.loaded = target;
  if (current.kind === "data" && current.composition_ready) {
    $("data-approve-after-placement").hidden = false;
  }
  updateFigureButtonStates();
}

function verifyFigurePdfCandidate(figureId, previewUrl, target) {
  const pdf = $("figure-preview-pdf");
  if (pdf.dataset.verifying === target || pdf.dataset.loaded === target) return;
  pdf.dataset.verifying = target;
  fetch(previewUrl, {cache: "no-store"})
    .then(async (response) => {
      if (!response.ok) return;
      let prefix = new Uint8Array();
      if (response.body && response.body.getReader) {
        const reader = response.body.getReader();
        const chunk = await reader.read();
        prefix = chunk.value || prefix;
        await reader.cancel().catch(() => {});
      } else {
        prefix = new Uint8Array(await response.arrayBuffer());
      }
      const pdfHeader = String.fromCharCode(...prefix.slice(0, 5)) === "%PDF-";
      if (!pdfHeader) return;
      markFigurePdfLoaded(figureId, target);
    })
    .catch(() => {
      // The iframe may still emit load; leave insertion locked until either check succeeds.
    })
    .finally(() => {
      if (pdf.dataset.verifying === target) delete pdf.dataset.verifying;
    });
}

function renderFigures() {
  syncCaptionDraftProject();
  syncFigureEditorDraftProject();
  const figures = sectionFigures();
  if (!figures.some((figure) => figure.id === activeFigure) && figures.length) {
    activeFigure = figures[0].id;
    try {
      localStorage.setItem(ACTIVE_FIGURE_KEY, activeFigure);
    } catch (_error) {}
  }
  const cards = $("figure-cards");
  cards.innerHTML = "";
  const tableMode = activeView === "tables";
  $("section-kicker").textContent = tableMode ? "SECTION TABLES" : "SECTION FIGURES";
  $("section-title").textContent = `${state.sections[activeSection].title} · ${tableMode ? "表" : "图"}`;
  if (!figures.length) {
    cards.innerHTML = `<div class="data-note">当前自然段和 section 没有计划中的 ${tableMode ? "table" : "figure"}。</div>`;
    $("figure-detail").hidden = true;
    return;
  }
  $("figure-detail").hidden = false;
  figures.forEach((figure) => {
    const button = document.createElement("button");
    button.className = `figure-card${figure.id === activeFigure ? " selected" : ""}${figure.ready ? "" : " blocked"}`;
    button.innerHTML = `
      <span class="figure-card-id">${figure.id}</span>
      <span><strong>${figure.title}</strong><small>${figure.kind === "table" ? "结果表 · 可编辑 LaTeX" : figure.phase === 1 ? "机制图 · 先完成" : "数据图 · results/ 驱动"}</small></span>
      <span class="figure-card-state ${figure.status}">${figure.ready ? figure.status : "locked"}</span>
    `;
    button.onclick = () => {
      activeFigure = figure.id;
      try {
        localStorage.setItem(ACTIVE_FIGURE_KEY, activeFigure);
      } catch (_error) {}
      renderFigures();
    };
    cards.appendChild(button);
  });

  const figure = selectedFigure();
  if (!figure) return;
  const isTable = figure.kind === "table";
  $("figure-phase").textContent = `PHASE ${figure.phase} · ${figure.kind === "table" ? "EDITABLE TABLE" : figure.kind === "mechanism" ? "EDITABLE SCHEMATIC" : "DATA FIGURE"}`;
  $("figure-title").textContent = `${figure.id} · ${figure.title}`;
  $("figure-description").textContent = `${figure.description} · ${figure.width} · ${figure.label}`;
  const gate = $("figure-gate");
  const insertionBlocked = figure.insertion_ready === false;
  gate.textContent = !figure.ready
    ? figure.gate_reason
    : insertionBlocked
      ? figure.insertion_gate_reason
      : "";
  gate.classList.toggle("show", !figure.ready || insertionBlocked);
  const mechanismPrerequisite = $("mechanism-generation-prerequisite");
  const mechanismPrerequisiteBlocked = (
    figure.kind === "mechanism" && figure.generation_ready === false
  );
  mechanismPrerequisite.hidden = !mechanismPrerequisiteBlocked;
  $("mechanism-generation-prerequisite-text").textContent = mechanismPrerequisiteBlocked
    ? figure.generation_gate_reason
    : "";

  const progress = $("figure-progress");
  const running = figureIsRunning(figure);
  const singleData = figure.kind === "data" && (figure.panels || []).length === 1;
  progress.hidden = !running || (figure.kind === "data" && !singleData);
  $("figure-progress-bar").style.width = `${Math.max(0, Math.min(100, figure.progress || 0))}%`;
  const elapsed = running && Number.isFinite(figure.running_seconds)
    ? ` · 已等待 ${figure.running_seconds} 秒`
    : "";
  $("figure-progress-message").textContent = `${figure.progress_message || ""}${elapsed}`;

  const mechanismPreviewSwitch = $("mechanism-preview-switch");
  const mechanismPreviewToggle = $("mechanism-preview-toggle");
  const mechanismPreviewNote = $("mechanism-preview-note");
  const mechanismBuildStatus = $("mechanism-build-status");
  const hasMechanismVersions = Boolean(
    figure.kind === "mechanism"
    && figure.gpt_preview_url
    && figure.paper_preview_url
  );
  let mechanismPreviewMode = mechanismPreviewModes.get(figure.id) || "paper";
  if (!hasMechanismVersions) {
    mechanismPreviewModes.delete(figure.id);
    mechanismPreviewMode = "paper";
  }
  mechanismPreviewSwitch.hidden = !hasMechanismVersions;
  const mechanismBuildPending = (
    figure.kind === "mechanism"
    && Boolean(figure.gpt_preview_url)
    && !figure.paper_preview_url
  );
  mechanismBuildStatus.hidden = !mechanismBuildPending;
  mechanismBuildStatus.textContent = mechanismBuildPending
    ? (["agent_generating", "agent_editing"].includes(figure.status)
      ? "GPT 原图已完成；可编辑 PPT/PDF 正在后台重建。完成后会自动出现“GPT 原图 / PPT/PDF 版”切换。"
      : figure.status === "failed"
        ? `可编辑 PPT/PDF 重建失败：${figure.last_message || figure.progress_message || "请点击重试。"}`
        : "GPT 原图已完成，但可编辑 PPT/PDF 尚未完成；请点击重试重建。")
    : "";
  const textFreeGptPreview = Boolean(figure.gpt_preview_no_text);
  mechanismPreviewToggle.textContent = mechanismPreviewMode === "paper"
    ? (textFreeGptPreview ? "显示 GPT 构图底图（无文字）" : "显示 GPT 原图")
    : "显示可编辑 PPT/PDF 完整版";
  mechanismPreviewNote.textContent = textFreeGptPreview
    ? "GPT 图只提供构图参考；标题、标签和说明文字位于可编辑 PPT/PDF 完整版中。"
    : "GPT 原图用于视觉对照；论文插入和下载仍以可编辑 PPT/PDF 版为准。";
  const effectivePreviewUrl = hasMechanismVersions
    ? (mechanismPreviewMode === "gpt" ? figure.gpt_preview_url : figure.paper_preview_url)
    : figure.preview_url;
  const effectivePreviewType = hasMechanismVersions
    ? (mechanismPreviewMode === "gpt" ? "image" : "pdf")
    : figure.preview_type;

  const image = $("figure-preview-image");
  const pdf = $("figure-preview-pdf");
  const tablePreview = $("table-preview");
  image.style.display = "none";
  pdf.style.display = "none";
  tablePreview.hidden = true;
  if (isTable) {
    if (effectivePreviewUrl) {
      image.src = effectivePreviewUrl;
      image.alt = `${figure.id} LaTeX-compiled table preview`;
      image.style.display = "block";
    }
  } else if (effectivePreviewUrl && effectivePreviewType === "image") {
    image.src = effectivePreviewUrl;
    image.style.display = "block";
  } else if (effectivePreviewUrl) {
    const target = `${effectivePreviewUrl}#toolbar=0&navpanes=0&view=FitH`;
    if (pdf.dataset.source !== target) {
      pdf.dataset.loaded = "";
      $("data-approve-after-placement").hidden = true;
      pdf.onload = () => {
        verifyFigurePdfCandidate(figure.id, effectivePreviewUrl, target);
      };
      pdf.dataset.source = target;
      pdf.src = target;
      verifyFigurePdfCandidate(figure.id, effectivePreviewUrl, target);
    }
    pdf.style.display = "block";
  }

  const mechanism = figure.kind === "mechanism";
  const captionBox = $("figure-caption-box");
  captionBox.hidden = isTable;
  const captionInput = $("figure-caption");
  const changedCaptionFigure = captionInput.dataset.figureId !== figure.id;
  const savedCaption = figure.caption || "";
  const captionDraft = captionDrafts.get(figure.id);
  if (captionDraft === savedCaption) {
    forgetCaptionDraft(figure.id);
  }
  if (changedCaptionFigure) {
    captionInput.value = captionDraft !== undefined && captionDraft !== savedCaption
      ? captionDraft
      : savedCaption;
    captionInput.dataset.figureId = figure.id;
    captionInput.dataset.dirty = String(captionInput.value !== savedCaption);
  } else if (captionInput.dataset.dirty !== "true" && document.activeElement !== captionInput) {
    captionInput.value = savedCaption;
    captionInput.dataset.dirty = "false";
  }
  const captionPrompt = $("figure-caption-prompt");
  renderFigureEditorInput(captionPrompt, figure.id, "caption_prompt", "");
  const captionDirty = captionInput.dataset.dirty === "true";
  $("figure-caption-status").textContent = captionDirty
    ? (figure.status === "approved"
      ? "Caption 已修改，尚未更新到正文与 PDF"
      : "Caption 已修改，尚未保存")
    : (figure.status === "approved"
      ? "Caption 已写入正文与 PDF"
      : "当前正文将使用此 Caption");
  $("mechanism-controls").style.display = mechanism ? "grid" : "none";
  $("mechanism-approve-after-placement").style.display = mechanism ? "flex" : "none";
  $("data-controls").style.display = !mechanism && !isTable ? "block" : "none";
  $("table-agent-controls").style.display = isTable ? "block" : "none";
  $("table-controls").style.display = isTable ? "block" : "none";
  renderFigureEditorInput(
    $("table-prompt"),
    figure.id,
    "table_generation_prompt",
    figure.generation_prompt || "",
  );
  renderFigureEditorInput(
    $("table-agent-prompt"),
    figure.id,
    "table_agent_prompt",
    figure.agent_prompt || "",
  );
  if (!mechanism && !isTable) {
    renderLayoutPrompt(figure);
    if ((figure.panels || []).length === 1) {
      renderSingleDataFigure(figure);
    } else {
      renderDataPanels(figure);
    }
  }
  renderFigureEditorInput($("table-latex"), figure.id, "table_latex", figure.latex || "");
  renderFigureEditorInput($("draw-prompt"), figure.id, "draw_prompt", figure.draw_prompt || "");
  renderFigureEditorInput(
    $("prompt-instruction"),
    figure.id,
    "prompt_instruction",
    figure.prompt_instruction || "",
  );
  const placement = $("figure-placement");
  placement.innerHTML = "";
  (figure.placement_options || []).forEach((option) => {
    const item = document.createElement("option");
    item.value = option.id;
    item.textContent = `${option.id} 后${option.accepted ? "" : "（正文未完成）"}`;
    item.disabled = !option.accepted;
    placement.appendChild(item);
  });
  if (figure.placement_after) placement.value = figure.placement_after;
  $("figure-layout-control").hidden = isTable;
  $("figure-layout-mode").value = figure.layout_mode || "single-column";
  $("figure-prompt").textContent = figure.draw_prompt
    ? "按右侧指令更新 Prompt"
    : "GPT 生成设计 Prompt";
  updateMechanismFlow(figure);
  updateFigureButtonStates();

  const downloads = $("figure-downloads");
  downloads.innerHTML = "";
  Object.entries(figure.downloads || {}).forEach(([kind, url]) => {
    const link = document.createElement("a");
    link.href = url;
    link.textContent = `下载 ${kind.toUpperCase()}`;
    link.download = "";
    downloads.appendChild(link);
  });
  $("figure-message").textContent = figure.last_message || "";
  ensureFigurePolling();
  if (
    mechanism
    && figure.ready
    && figure.generation_ready !== false
    && figure.status === "pending"
    && !figure.draw_prompt
    && !autoFigurePromptAttempted.has(figure.id)
  ) {
    autoFigurePromptAttempted.add(figure.id);
    setTimeout(() => {
      const current = selectedFigure();
      if (
        activeView === "figures"
        && current
        && current.id === figure.id
        && current.generation_ready !== false
        && current.status === "pending"
      ) {
        startFigureJob(
          "/api/figure/prompt",
          {
            figure_id: figure.id,
            current_prompt: "",
            prompt_instruction: "",
          },
          "正在根据当前 section 正文自动生成设计 Prompt…",
        );
      }
    }, 50);
  }
  scheduleAutomaticDataPanel(figure);
  scheduleAutomaticTableGenerate(figure);
}

const DEMO_READ_ONLY_CONTROL_IDS = [
  "generate", "accept", "candidate", "comment", "reset", "reset-generated",
  "title-generate", "title-save", "paper-title", "title-gpt-prompt",
  "figure-prompt", "draw-prompt", "prompt-instruction", "figure-draw",
  "figure-cancel", "figure-build", "single-data-prompt", "single-data-generate",
  "data-layout-prompt", "data-approve", "figure-caption-prompt",
  "figure-caption-generate", "figure-placement", "figure-layout-mode",
  "figure-approve", "table-agent-prompt", "table-agent-edit", "table-prompt",
  "table-generate", "table-latex", "table-save", "table-approve",
];

function applyReadOnlyDemoRestrictions() {
  // The gateway already refuses every non-GET/HEAD request against a demo
  // session (server-side, unconditionally) -- this is UX only, so a demo
  // visitor sees a clean read-only viewer instead of controls that look
  // clickable and then dead-end in a network error.
  if (!state || !state.demo_mode) return;
  DEMO_READ_ONLY_CONTROL_IDS.forEach((id) => {
    const element = $(id);
    if (element) element.disabled = true;
  });
  document.querySelectorAll(".figure-card, .figure-actions button, .paragraph-nav button")
    .forEach((element) => { element.disabled = true; });
}

function render() {
  syncProseDraftProject();
  syncTitleDraftProject();
  syncCommentDraftProject();
  $("load-error").hidden = true;
  const project = state.project || {};
  const apiKeySetup = state.api_key_setup || {};
  const apiKeyReady = Boolean(state.api_key_configured);
  // Every online session (real or demo) shares one server-held DeepSeek
  // key; there is nothing for that researcher to pick, rotate, or type a
  // model name for, so both controls stay hidden there. A local desktop
  // install keeps them -- a solo researcher's own machine, their own key,
  // switching providers/models deliberately is unaffected.
  $("model-runtime-config").hidden = Boolean(state.online_project);
  $("runtime-key-open").hidden = Boolean(state.online_project);
  const modelInput = $("model");
  const modelOptions = state.llm_model_options || [];
  $("model-suggestions").replaceChildren(...modelOptions.map((option) => {
    const element = document.createElement("option");
    element.value = option.id;
    element.label = option.label;
    return element;
  }));
  renderTitleDraftInput(modelInput, "model", state.model || "gpt-5-nano");
  $("model-provider-note").textContent = `${apiKeySetup.provider_label || "当前 API"} 提供；可自行输入模型名称，建议项仅作参考。`;
  updateModelApplyButton();
  $("api-key-setup").hidden = apiKeyReady;
  $("api-key-setup-command").textContent = apiKeySetup.setup_command || 'export OPENAI_API_KEY="粘贴你的 API key"';
  $("api-key-setup-description").textContent = `${apiKeySetup.provider_label || "当前"} API 尚未配置。请在启动 Paper Studio 的本机终端设置；密钥不会进入网页。GPT Image 仍单独使用 OpenAI。`;
  $("api-key-restart-command").textContent = apiKeySetup.restart_command || "python3 -m research_avatar.paper_studio.server";
  document.querySelector(".workspace").classList.toggle("api-key-missing", !apiKeyReady);
  $("project-eyebrow").textContent = project.eyebrow || project.name || "PAPER PROJECT";
  $("studio-title").textContent = project.studio_title || "Paper Studio";
  $("project-subtitle").textContent = project.subtitle || "逐段对话、确认后写入 LaTeX";
  const projectExport = $("project-export");
  projectExport.hidden = !project.export_url;
  if (project.export_url) projectExport.href = studioPath(project.export_url);
  document.title = project.name ? `${project.name} · Paper Studio` : "Paper Studio";
  renderSections();
  const emptyMode = project.loaded === false;
  $("empty-project").hidden = !emptyMode;
  if (emptyMode) {
    $("writing-workspace").hidden = true;
    $("figures-workspace").hidden = true;
    $("section-kicker").textContent = "EMPTY STUDIO";
    $("section-title").textContent = "尚未载入论文";
    ["writing-view", "figures-view", "tables-view", "compile", "reset", "reset-generated", "model", "model-apply", "runtime-key-open"].forEach((id) => {
      $(id).disabled = true;
    });
    return;
  }
  ["writing-view", "figures-view", "tables-view", "compile", "reset", "reset-generated", "model", "runtime-key-open"].forEach((id) => {
    $(id).disabled = false;
  });
  updateModelApplyButton();
  const artifactMode = ["figures", "tables"].includes(activeView);
  $("writing-workspace").hidden = artifactMode;
  $("figures-workspace").hidden = !artifactMode;
  $("writing-view").classList.toggle("active", !artifactMode);
  $("figures-view").classList.toggle("active", activeView === "figures");
  $("tables-view").classList.toggle("active", activeView === "tables");
  if (artifactMode) {
    $("section-kicker").textContent = activeView === "tables" ? "TABLE WORKFLOW" : "FIGURE WORKFLOW";
    $("section-title").textContent = activeView === "tables" ? "Tables" : "Figures";
    renderFigures();
    applyReadOnlyDemoRestrictions();
    return;
  }
  $("section-kicker").textContent = "SECTION";
  const section = state.sections[activeSection];
  $("section-title").textContent = section.title;
  $("title-editor").hidden = activeSection !== "abstract";
  if (activeSection === "abstract") renderTitleEditor();
  renderParagraphNavigation(section);
  const paragraph = section.current_paragraph;
  const candidate = paragraph && paragraph.candidate;
  $("paragraph-id").textContent = paragraph ? paragraph.id : "完成";
  $("paragraph-progress").textContent = paragraph
    ? `${paragraph.position} / ${paragraph.total}`
    : `${section.paragraph_count} / ${section.paragraph_count}`;
  $("reference").textContent = paragraph ? paragraph.reference_text : "";
  $("candidate-label").textContent = paragraph
    ? candidate
      ? "当前候选段落"
      : paragraph.accepted_text
        ? "已接受版本（可继续修改）"
        : "当前候选段落"
    : "已接受并写入 LaTeX 的 section 内容";
  const proseEditor = $("candidate");
  const editorKey = `${activeSection}:${paragraph ? paragraph.id : "complete"}`;
  const serverText = candidate
    ? candidate.text
    : paragraph
      ? paragraph.accepted_text || ""
      : section.accepted_text || "";
  let proseDraft = proseDrafts.get(editorKey);
  if (proseDraft && proseDraft.value === serverText) {
    forgetProseDraft(editorKey);
    proseDraft = undefined;
  }
  if (
    proseBaselineKey !== editorKey
    || (proseEditor.dataset.dirty !== "true" && document.activeElement !== proseEditor)
  ) {
    proseEditor.value = proseDraft ? proseDraft.value : serverText;
    proseEditor.dataset.dirty = String(Boolean(proseDraft));
    proseBaselineKey = editorKey;
    proseBaselineText = proseDraft ? proseDraft.baseline : serverText;
  }
  $("candidate").placeholder = paragraph
    ? paragraph.accepted_text
      ? "这是当前写入 LaTeX 的版本；填写 comment 后可继续修改。"
      : "等待生成当前段落…"
    : "这个 section 已完成。";
  $("comment").value = commentDrafts.get(editorKey) || "";
  updateAcceptButton();
  $("generate").disabled = !paragraph;
  const gate = $("gate");
  gate.textContent = state.outline_confirmed
    ? ""
    : "Outline 尚未确认。可以浏览界面，但在确认并建立 LaTeX scaffold 前不能 Accept → LaTeX。";
  gate.classList.toggle("show", !state.outline_confirmed);
  renderFullDraft();
  renderPdf();
  const fullDraftRunning = Boolean(
    state.full_draft && state.full_draft.job && state.full_draft.job.status === "running"
  );
  if (
    !state.demo_mode
    && activeView === "writing"
    && !fullDraftRunning
    && paragraph
    && !candidate
    && !paragraph.accepted_text
  ) {
    const key = `${activeSection}:${paragraph.id}`;
    if (!autoAttempted.has(key)) {
      autoAttempted.add(key);
      setTimeout(() => generateCurrent(true), 50);
    }
  }
  applyReadOnlyDemoRestrictions();
}

function renderFullDraft() {
  const card = $("full-draft-card");
  const draft = state.full_draft || {};
  const job = draft.job || null;
  const running = Boolean(job && job.status === "running");
  const pending = Number(draft.pending_paragraphs || 0);
  const total = Number(draft.total_paragraphs || 0);
  card.classList.toggle("is-running", running);
  card.classList.toggle("is-failed", Boolean(job && job.status === "failed"));
  card.classList.toggle("is-completed", Boolean(job && job.status === "completed"));

  const summary = $("full-draft-summary");
  if (job && job.progress_message) {
    summary.textContent = job.progress_message;
  } else if (!state.outline_confirmed) {
    summary.textContent = "请先确认 outline；批量模式不会绕过论文结构确认。";
  } else if (!state.api_key_configured) {
    summary.textContent = "请先按页面顶部说明配置 LLM API Key。";
  } else if (!pending) {
    summary.textContent = `全部 ${total} 个段落已经写入 LaTeX，可继续逐段修改。`;
  } else {
    summary.textContent = `将按项目写作顺序补齐 ${pending} / ${total} 个未完成段落；已接受内容不会被覆盖。`;
  }

  const start = $("full-draft-start");
  const cancel = $("full-draft-cancel");
  start.disabled = fullDraftRequestBusy || running || !draft.available || pending === 0;
  start.textContent = job && ["failed", "cancelled"].includes(job.status)
    ? "继续补齐未完成正文"
    : pending === 0
      ? "全文初稿已生成"
      : "直接生成全文初稿";
  cancel.hidden = !running;
  cancel.disabled = fullDraftRequestBusy;

  const progressRow = $("full-draft-progress-row");
  progressRow.hidden = !job;
  $("full-draft-progress").value = Number((job && job.progress) || 0);
  $("full-draft-progress-text").textContent = job
    ? `${Number(job.completed || 0)} / ${Number(job.total || pending)} · ${job.progress_message || job.status}`
    : "";

  ["candidate", "comment", "generate", "accept", "paper-title", "title-gpt-prompt", "title-generate", "title-save", "model", "reset", "reset-generated"].forEach((id) => {
    const element = $(id);
    if (element && running) element.disabled = true;
  });
  document.querySelectorAll("#paragraph-nav button").forEach((button) => {
    button.disabled = running;
  });

  if (fullDraftPollTimer) {
    clearTimeout(fullDraftPollTimer);
    fullDraftPollTimer = null;
  }
  if (running) {
    fullDraftPollTimer = setTimeout(pollFullDraft, 900);
  }
}

async function pollFullDraft() {
  fullDraftPollTimer = null;
  try {
    state = normalizeStateUrls(await request("/api/state"));
    render();
  } catch (error) {
    showMessage(error.message, true);
  }
}

async function refresh() {
  state = normalizeStateUrls(await request("/api/state"));
  if (state.project && state.project.loaded === false) {
    render();
    return;
  }
  if (!state.sections[activeSection]) {
    activeSection = state.sections.abstract ? "abstract" : Object.keys(state.sections)[0];
    rememberActiveSection(activeSection);
  }
  render();
}

async function generateCurrent(automatic = false) {
  if (proseRequestBusy) return;
  proseRequestBusy = true;
  const requestedSection = activeSection;
  const requestedParagraph = state.sections[requestedSection].current_paragraph;
  if (!requestedParagraph) {
    proseRequestBusy = false;
    return;
  }
  try {
    setBusy(true, automatic
      ? "正在结合 reference paragraph、working abstract 和实验结果生成当前段落…"
      : "正在根据 comment 修改当前段落…");
    const payload = await request("/api/generate", {
      method: "POST",
      body: JSON.stringify({
        section: requestedSection,
        paragraph_id: requestedParagraph.id,
        model: $("model").value.trim(),
        current_text: $("candidate").value,
        comment: $("comment").value,
      }),
    });
    state = payload.state;
    if (activeSection === requestedSection) {
      forgetProseDraft(`${requestedSection}:${requestedParagraph.id}`);
      forgetCommentDraft(`${requestedSection}:${requestedParagraph.id}`);
      $("candidate").dataset.dirty = "false";
      render();
      const added = payload.candidate.citations_added || [];
      showMessage(added.length
        ? `当前段落已生成，并联网核验后新增 citation：${added.join(", ")}。`
        : "当前段落已生成。你只需要写 comment 修改，或 Accept → LaTeX。");
    } else {
      renderSections();
      showMessage(`${state.sections[requestedSection].title} 的当前段落已生成并保存。`);
    }
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    proseRequestBusy = false;
    setBusy(false);
  }
}

$("generate").onclick = () => generateCurrent(false);

$("candidate").addEventListener("input", (event) => {
  event.currentTarget.dataset.dirty = "true";
  const paragraph = state.sections[activeSection].current_paragraph;
  if (paragraph) {
    rememberProseDraft(
      `${activeSection}:${paragraph.id}`,
      event.currentTarget.value,
      proseBaselineText,
    );
  }
  if (paragraph && paragraph.accepted_text && !paragraph.candidate) {
    $("candidate-label").textContent = "已接受版本的手动修改（尚未写入）";
  }
  updateAcceptButton();
});

$("comment").addEventListener("input", (event) => {
  const paragraph = state.sections[activeSection].current_paragraph;
  if (paragraph) rememberCommentDraft(`${activeSection}:${paragraph.id}`, event.currentTarget.value);
});

async function applyWritingModel() {
  if (proseRequestBusy || fullDraftRequestBusy || titleBusy || conversationResetBusy) {
    return;
  }
  const requestedModel = $("model").value.trim();
  if (!requestedModel) {
    showMessage("请先输入写作模型名称。", true);
    updateModelApplyButton();
    return;
  }
  if (requestedModel === state.model) return;
  if (!confirm(`切换到 ${requestedModel}？这会重置所有 LLM 对话链，但不会修改已写入的正文、图表或 PDF。`)) {
    return;
  }
  conversationResetBusy = true;
  try {
    setBusy(true, `正在切换写作模型为 ${requestedModel}…`);
    const payload = await request("/api/llm-model", {
      method: "POST",
      body: JSON.stringify({model: requestedModel}),
    });
    state = payload.state;
    forgetTitleDraft("model");
    render();
    showMessage(`写作模型已切换为 ${state.model}；LLM 对话链已重置，已写入内容保持不变。`);
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    conversationResetBusy = false;
    setBusy(false);
  }
}

$("model").addEventListener("input", (event) => {
  rememberTitleDraft("model", event.currentTarget.value, state.model || "gpt-5-nano");
  event.currentTarget.dataset.dirty = String(event.currentTarget.value !== (state.model || "gpt-5-nano"));
  updateModelApplyButton();
});

$("model").addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  applyWritingModel();
});

$("model-apply").addEventListener("click", applyWritingModel);

$("paper-title").addEventListener("input", (event) => {
  event.currentTarget.dataset.dirty = "true";
  const editor = state.title_editor || {};
  rememberTitleDraft("title", event.currentTarget.value, editor.candidate || editor.current_title || "");
  $("title-status").textContent = "标题有未保存修改。";
  updateTitleSaveButton();
});

$("title-gpt-prompt").addEventListener("input", (event) => {
  event.currentTarget.dataset.dirty = "true";
  rememberTitleDraft("prompt", event.currentTarget.value, (state.title_editor || {}).prompt || "");
});

$("title-generate").onclick = async () => {
  if (titleBusy) return;
  const prompt = $("title-gpt-prompt").value.trim();
  if (!prompt) {
    $("title-status").textContent = "请先填写 Title GPT Prompt。";
    $("title-status").classList.add("error");
    return;
  }
  try {
    setTitleBusy(true, "正在生成标题候选；不会自动保存…");
    const payload = await request("/api/title/generate", {
      method: "POST",
      body: JSON.stringify({
        prompt,
        current_title: $("paper-title").value.trim(),
        model: $("model").value.trim(),
      }),
    });
    state = payload.state;
    forgetTitleDraft("title");
    forgetTitleDraft("prompt");
    $("paper-title").dataset.dirty = "false";
    $("title-gpt-prompt").dataset.dirty = "false";
    renderTitleEditor(true);
  } catch (error) {
    $("title-status").textContent = error.message;
    $("title-status").classList.add("error");
  } finally {
    setTitleBusy(false);
  }
};

$("title-save").onclick = async () => {
  if (titleBusy) return;
  const title = $("paper-title").value.trim();
  try {
    setTitleBusy(true, "正在写入 LaTeX 并编译 PDF…");
    const payload = await request("/api/title/save", {
      method: "POST",
      body: JSON.stringify({title}),
    });
    state = payload.state;
    forgetTitleDraft("title");
    $("paper-title").dataset.dirty = "false";
    renderTitleEditor(true);
    renderPdf();
  } catch (error) {
    $("title-status").textContent = error.message;
    $("title-status").classList.add("error");
  } finally {
    setTitleBusy(false);
  }
};

async function acceptCurrent() {
  if (acceptRequestBusy) return;
  acceptRequestBusy = true;
  setBusy(true, "正在核对最新段落状态…");
  const requestedSection = activeSection;
  let acceptedParagraphId = "";
  let acceptanceCompleted = false;
  try {
    let paragraph = state.sections[requestedSection].current_paragraph;
    let candidate = paragraph && paragraph.candidate;
    const visibleParagraphId = paragraph && paragraph.id;
    const visibleCandidateText = $("candidate").value.trim();
    const visibleBaseText = proseBaselineText.trim();
    const latestState = normalizeStateUrls(await request("/api/state"));
    const latestParagraph = latestState.sections[requestedSection].current_paragraph;
    const latestCandidate = latestParagraph && latestParagraph.candidate;
    if (
      visibleParagraphId
      && latestParagraph
      && latestParagraph.id !== visibleParagraphId
    ) {
      state = latestState;
      $("candidate").dataset.dirty = "false";
      render();
      showMessage(`当前编辑位置已更新到 ${latestParagraph.id}，请确认后再 Accept。`, true);
      return;
    }
    if (
      visibleParagraphId
      && latestParagraph
      && latestParagraph.id === visibleParagraphId
      && candidate
      && latestCandidate
      && candidate.id !== latestCandidate.id
      && visibleCandidateText !== String(latestCandidate.text || "").trim()
    ) {
      state = latestState;
      forgetProseDraft(`${requestedSection}:${visibleParagraphId}`);
      $("candidate").dataset.dirty = "false";
      render();
      showMessage("候选已在另一轮生成中更新；已自动载入最新版，请确认内容后再次 Accept。", true);
      return;
    }
    state = latestState;
    paragraph = latestParagraph;
    candidate = latestCandidate;
    const manualRevision = Boolean(
      paragraph
      && paragraph.accepted_text
      && visibleCandidateText
      && visibleCandidateText !== String(paragraph.accepted_text).trim()
    );
    if (!candidate && !manualRevision) {
      render();
      showMessage(
        latestParagraph && visibleParagraphId && latestParagraph.id !== visibleParagraphId
          ? `当前编辑位置已更新到 ${latestParagraph.id}，请确认后再 Accept。`
          : "当前段落没有可接受的 candidate；请先生成候选。",
        true,
      );
      return;
    }
    const revisingAccepted = Boolean(paragraph.accepted_text);
    acceptedParagraphId = paragraph.id;
    setBusy(true, "正在校验引用；缺失时会联网检索、更新 BibTeX，再写入 LaTeX 并编译…");
    const payload = await request("/api/accept", {
      method: "POST",
      body: JSON.stringify({
        section: requestedSection,
        paragraph_id: paragraph.id,
        candidate_id: candidate ? candidate.id : "",
        candidate_text: visibleCandidateText,
        base_text: visibleBaseText,
      }),
    });
    acceptanceCompleted = true;
    state = payload.state;
    forgetProseDraft(`${requestedSection}:${acceptedParagraphId}`);
    forgetCommentDraft(`${requestedSection}:${acceptedParagraphId}`);
    $("candidate").dataset.dirty = "false";
    if (activeSection === requestedSection) {
      const nextParagraph = state.sections[requestedSection].current_paragraph;
      render();
      showMessage(
        revisingAccepted
          ? `${acceptedParagraphId} 的新版本已替换写入 LaTeX，并完成 PDF 编译。`
          : state.sections[requestedSection].complete
          ? `${acceptedParagraphId} 已接受并完成 LaTeX 编译；当前 section 已完成。`
          : nextParagraph
          ? `${acceptedParagraphId} 已接受并完成 LaTeX 编译；正在后台准备 ${nextParagraph.id} 候选。`
          : `${acceptedParagraphId} 已接受并完成 LaTeX 编译。`,
      );
      if (
        !revisingAccepted
        && nextParagraph
        && !nextParagraph.candidate
        && !nextParagraph.accepted_text
      ) {
        const key = `${requestedSection}:${nextParagraph.id}`;
        autoAttempted.add(key);
        setBusy(
          true,
          `${acceptedParagraphId} 已写入并编译；正在生成 ${nextParagraph.id}…`,
        );
        const nextPayload = await request("/api/generate", {
          method: "POST",
          body: JSON.stringify({
            section: requestedSection,
            paragraph_id: nextParagraph.id,
            model: $("model").value.trim(),
            current_text: "",
            comment: "",
          }),
        });
        state = nextPayload.state;
      }
      render();
      const current = state.sections[requestedSection].current_paragraph;
      showMessage(
        revisingAccepted
          ? `${acceptedParagraphId} 的新版本已替换写入 LaTeX，并完成 PDF 编译。`
          : state.sections[requestedSection].complete
          ? `${acceptedParagraphId} 已接受并完成 LaTeX 编译；当前 section 已完成。`
          : current
          ? `${acceptedParagraphId} 已接受并完成 LaTeX 编译；${current.id} 候选已刷新。`
          : `${acceptedParagraphId} 已接受并完成 LaTeX 编译。`,
      );
    } else {
      renderSections();
      showMessage(`${state.sections[requestedSection].title} 已接受并完成 LaTeX 编译。`);
    }
  } catch (error) {
    if (acceptanceCompleted) {
      render();
      showMessage(
        `${acceptedParagraphId} 已写入 LaTeX 并编译，但下一段生成失败：${error.message}`,
        true,
      );
    } else {
      showMessage(error.message, true);
    }
  } finally {
    acceptRequestBusy = false;
    setBusy(false);
  }
}

$("accept").addEventListener("click", acceptCurrent);

$("compile").onclick = async () => {
  if (compileRequestBusy) return;
  compileRequestBusy = true;
  try {
    setBusy(true, "正在编译 LaTeX…");
    const payload = await request("/api/compile", {method: "POST", body: "{}"});
    state = payload.state;
    showMessage("PDF 编译成功。");
    renderPdf();
  } catch (error) {
    showMessage(error.message, true);
    try {
      await refresh();
    } catch (refreshError) {
      showMessage(`${error.message}\n状态刷新也失败：${refreshError.message}`, true);
    }
  } finally {
    compileRequestBusy = false;
    setBusy(false);
  }
};

$("reset").onclick = async () => {
  if (conversationResetBusy) return;
  const requestedModel = $("model").value.trim();
  if (!requestedModel) {
    showMessage("模型名称不能为空。", true);
    return;
  }
  if (!confirm(`将模型设为 ${requestedModel}，并重置当前 section 的 API 对话链？已接受的 LaTeX 不会删除。`)) return;
  conversationResetBusy = true;
  try {
    setBusy(true, "正在重置当前 section 的 API 对话链…");
    const payload = await request("/api/reset-conversation", {
      method: "POST",
      body: JSON.stringify({section: activeSection, model: requestedModel}),
    });
    state = payload.state;
    showMessage(`模型已设为 ${state.model}；当前 section 的 conversation 已重置。`);
    render();
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    conversationResetBusy = false;
    setBusy(false);
  }
};

async function submitGeneratedReset(typed) {
  if (generatedResetBusy) return;
  const requestedModel = $("model").value.trim();
  const projectId = state && state.project && state.project.id;
  if (typed.trim() !== projectId) {
    $("reset-project-copy-status").textContent = "项目 ID 不匹配；未删除任何生成内容。";
    $("reset-project-copy-status").classList.add("error");
    $("reset-project-confirm").focus();
    $("reset-project-confirm").select();
    return;
  }
  generatedResetBusy = true;
  $("reset-generated-dialog").close();
  try {
    setBusy(true, "正在清空生成内容并编译空壳 PDF…");
    const payload = await request("/api/reset-generated-paper", {
      method: "POST",
      body: JSON.stringify({project_id: typed.trim(), model: requestedModel}),
    });
    state = payload.state;
    clearBrowserDraftsForProject(projectId);
    activeSection = state.sections.abstract ? "abstract" : Object.keys(state.sections)[0];
    activeView = "writing";
    autoAttempted.clear();
    autoFigurePromptAttempted.clear();
    autoDataPanelAttempted.clear();
    autoTableGenerateAttempted.clear();
    render();
    showMessage(payload.message);
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    generatedResetBusy = false;
    setBusy(false);
  }
}

$("reset-generated").onclick = () => {
  const projectId = state && state.project && state.project.id;
  if (!projectId) {
    showMessage("当前没有可清空的论文项目。", true);
    return;
  }
  $("reset-project-id").value = projectId;
  $("reset-project-confirm").value = "";
  $("reset-project-copy-status").textContent = "";
  $("reset-project-copy-status").classList.remove("error");
  $("reset-generated-dialog").showModal();
  $("reset-project-id").focus();
  $("reset-project-id").select();
};

$("reset-project-copy").onclick = async () => {
  const input = $("reset-project-id");
  let copied = false;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(input.value);
      copied = true;
    }
  } catch (_error) {
    copied = false;
  }
  if (!copied) {
    input.focus();
    input.select();
    try {
      copied = document.execCommand("copy");
    } catch (_error) {
      copied = false;
    }
  }
  input.focus();
  input.select();
  $("reset-project-copy-status").classList.toggle("error", !copied);
  $("reset-project-copy-status").textContent = copied
    ? "项目 ID 已复制。"
    : "自动复制失败；ID 已选中，请按 Ctrl/Cmd+C。";
};

function closeGeneratedResetDialog() {
  $("reset-generated-dialog").close();
}

$("reset-generated-close").onclick = closeGeneratedResetDialog;
$("reset-generated-cancel").onclick = closeGeneratedResetDialog;
$("reset-generated-confirm").onclick = () => {
  submitGeneratedReset($("reset-project-confirm").value);
};
$("reset-project-confirm").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    submitGeneratedReset($("reset-project-confirm").value);
  }
});

function switchView(view) {
  if (!state || !state.sections) return;
  activeView = view;
  if (["figures", "tables"].includes(view)) {
    const paragraph = state.sections[activeSection].current_paragraph;
    const desiredKind = view === "tables" ? "table" : "figure";
    const related = (paragraph && paragraph.artifacts || []).find(
      (artifact) => artifact.kind === desiredKind,
    );
    let available = sectionFigures();
    if (!available.length) {
      const collection = view === "tables" ? (state.tables || []) : (state.figures || []);
      // Public figure records use concrete kinds such as mechanism/data rather
      // than the paragraph-binding kind "figure". Pick the first record from
      // the already view-specific collection when the active section has none.
      const fallback = collection[0] || null;
      const fallbackSection = fallback && (
        (fallback.source_sections || [])[0]
        || Object.keys(fallback.related_paragraphs || {})[0]
      );
      if (fallbackSection && state.sections[fallbackSection]) {
        activeSection = fallbackSection;
        rememberActiveSection(activeSection);
        available = sectionFigures();
      }
    }
    const selected = related
      ? available.find((artifact) => artifact.id === related.id)
      : null;
    const first = selected || available[0];
    if (first) activeFigure = first.id;
  }
  try {
    localStorage.setItem(ACTIVE_VIEW_KEY, view);
  } catch (_error) {}
  render();
}

$("writing-view").onclick = () => switchView("writing");
$("full-draft-start").onclick = async () => {
  if (fullDraftRequestBusy) return;
  fullDraftRequestBusy = true;
  $("full-draft-start").disabled = true;
  try {
    const payload = await request("/api/full-draft/start", {
      method: "POST",
      body: JSON.stringify({model: $("model").value.trim()}),
    });
    state = payload.state;
    render();
    showMessage("全文初稿任务已启动；可以切换页面查看进度，完成后仍可逐段修改。");
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    fullDraftRequestBusy = false;
    renderFullDraft();
  }
};
$("full-draft-cancel").onclick = async () => {
  if (fullDraftRequestBusy) return;
  fullDraftRequestBusy = true;
  $("full-draft-cancel").disabled = true;
  try {
    const payload = await request("/api/full-draft/cancel", {
      method: "POST",
      body: "{}",
    });
    state = payload.state;
    render();
    showMessage("已请求停止；已完成段落保留，之后可继续补齐未完成正文。");
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    fullDraftRequestBusy = false;
    renderFullDraft();
  }
};
$("figures-view").onclick = () => switchView("figures");
$("tables-view").onclick = () => switchView("tables");

async function runFigureAction(path, body, busyMessage) {
  if (figureRequestBusy) return null;
  figureRequestBusy = true;
  const requestedArtifactId = body.figure_id || body.table_id || "";
  updateFigureButtonStates();
  try {
    $("figure-message").classList.remove("error");
    $("figure-gate").classList.remove("show");
    setBusy(true, busyMessage);
    $("figure-message").textContent = busyMessage;
    const payload = await request(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
    state = payload.state;
    render();
    if (selectedFigure() && selectedFigure().id === requestedArtifactId) {
      $("figure-message").classList.remove("error");
      $("figure-message").textContent = payload.message || "完成。";
    }
    return payload;
  } catch (error) {
    if (selectedFigure() && selectedFigure().id === requestedArtifactId) {
      $("figure-message").textContent = error.message;
      $("figure-message").classList.add("error");
      $("figure-gate").textContent = error.message;
      $("figure-gate").classList.add("show");
    }
    return null;
  } finally {
    figureRequestBusy = false;
    setBusy(false);
  }
}

async function startFigureJob(path, body, startingMessage) {
  if (figureRequestBusy) return;
  figureRequestBusy = true;
  const requestedArtifactId = body.figure_id || body.table_id || "";
  updateFigureButtonStates();
  try {
    $("figure-message").classList.remove("error");
    $("figure-message").textContent = startingMessage;
    const payload = await request(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
    state = payload.state;
    render();
    ensureFigurePolling();
  } catch (error) {
    if (selectedFigure() && selectedFigure().id === requestedArtifactId) {
      $("figure-message").textContent = error.message;
      $("figure-message").classList.add("error");
    }
  } finally {
    figureRequestBusy = false;
    updateFigureButtonStates();
  }
}

async function pollFigureJobs() {
  figurePollTimer = null;
  try {
    state = normalizeStateUrls(await request("/api/state"));
    render();
  } catch (error) {
    if (["figures", "tables"].includes(activeView)) {
      $("figure-message").textContent = error.message;
      $("figure-message").classList.add("error");
    }
  } finally {
    ensureFigurePolling();
  }
}

function ensureFigurePolling() {
  const running = [...(state.figures || []), ...(state.tables || [])].some(figureIsRunning);
  if (running && !figurePollTimer) {
    figurePollTimer = setTimeout(pollFigureJobs, 1000);
  } else if (!running && figurePollTimer) {
    clearTimeout(figurePollTimer);
    figurePollTimer = null;
  }
}

$("figure-prompt").onclick = () => startFigureJob(
  "/api/figure/prompt",
  {
    figure_id: activeFigure,
    current_prompt: $("draw-prompt").value,
    prompt_instruction: $("prompt-instruction").value,
  },
  "正在启动 GPT 设计 Prompt 任务…",
);

$("figure-draw").onclick = () => startFigureJob(
  "/api/figure/draw",
  {figure_id: activeFigure, draw_prompt: $("draw-prompt").value},
  "正在检查 Prompt 是否变化…",
);

$("draw-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure) {
    rememberFigureEditorDraft(figure.id, "draw_prompt", event.currentTarget.value, figure.draw_prompt || "");
  }
  updateFigureButtonStates();
});

$("prompt-instruction").addEventListener("input", (event) => {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure) {
    rememberFigureEditorDraft(
      figure.id,
      "prompt_instruction",
      event.currentTarget.value,
      figure.prompt_instruction || "",
    );
  }
  updateFigureButtonStates();
});

$("figure-cancel").onclick = async () => {
  if (figureRequestBusy) return;
  figureRequestBusy = true;
  const button = $("figure-cancel");
  updateFigureButtonStates();
  $("figure-message").classList.remove("error");
  $("figure-message").textContent = "正在停止本次 GPT Image 调用…";
  try {
    const result = await request("/api/figure/cancel", {
      method: "POST",
      body: JSON.stringify({figure_id: activeFigure}),
    });
    state = result.state;
    render();
  } catch (error) {
    $("figure-message").textContent = error.message;
    $("figure-message").classList.add("error");
  } finally {
    figureRequestBusy = false;
    updateFigureButtonStates();
    ensureFigurePolling();
  }
};

$("figure-build").onclick = () => startFigureJob(
  "/api/figure/build",
  {figure_id: activeFigure},
  "正在启动本地 Agent，按草图重建原生 PowerPoint shapes…",
);

$("mechanism-preview-toggle").onclick = () => {
  const figure = selectedFigure();
  if (!figure || !figure.gpt_preview_url || !figure.paper_preview_url) return;
  const current = mechanismPreviewModes.get(figure.id) || "paper";
  mechanismPreviewModes.set(figure.id, current === "paper" ? "gpt" : "paper");
  renderFigures();
};

function updateFigurePlacement() {
  const figure = selectedFigure();
  return runFigureAction(
    figure && figure.kind === "table"
      ? "/api/table/placement"
      : "/api/figure/placement",
    figure && figure.kind === "table"
      ? {
          table_id: activeFigure,
          placement_after: $("figure-placement").value,
        }
      : {
          figure_id: activeFigure,
          placement_after: $("figure-placement").value,
          layout_mode: $("figure-layout-mode").value,
        },
    figure && figure.kind === "table"
      ? "正在移动表格并重新编译 PDF…"
      : "正在更新插图位置与排版方式…",
  );
}

$("figure-placement").onchange = updateFigurePlacement;
$("figure-layout-mode").onchange = updateFigurePlacement;

$("figure-caption").addEventListener("input", (event) => {
  const figure = selectedFigure();
  const dirty = Boolean(figure && event.currentTarget.value !== (figure.caption || ""));
  event.currentTarget.dataset.dirty = String(dirty);
  if (figure && dirty) rememberCaptionDraft(figure.id, event.currentTarget.value);
  else if (figure) forgetCaptionDraft(figure.id);
  $("figure-caption-status").textContent = dirty
    ? (figure && figure.status === "approved"
      ? "Caption 已修改，尚未更新到正文与 PDF"
      : "Caption 已修改，尚未保存")
    : (figure && figure.status === "approved"
      ? "Caption 已写入正文与 PDF"
      : "当前正文将使用此 Caption");
  updateFigureButtonStates();
});

$("figure-caption-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure) {
    rememberFigureEditorDraft(figure.id, "caption_prompt", event.currentTarget.value, "");
  }
});

$("figure-caption-generate").onclick = async () => {
  if (figureRequestBusy) return;
  figureRequestBusy = true;
  const requestedFigureId = activeFigure;
  const button = $("figure-caption-generate");
  const captionInput = $("figure-caption");
  const originalLabel = button.textContent;
  try {
    updateFigureButtonStates();
    button.textContent = "GPT 正在生成 Caption…";
    $("figure-caption-status").textContent = "正在生成 Caption candidate…";
    const payload = await request("/api/figure/caption/generate", {
      method: "POST",
      body: JSON.stringify({
        figure_id: requestedFigureId,
        current_caption: captionInput.value,
        prompt_instruction: $("figure-caption-prompt").value,
      }),
    });
    const generatedCaption = payload.caption || "";
    const requestedFigure = (state.figures || []).find((item) => item.id === requestedFigureId);
    const dirty = Boolean(requestedFigure && generatedCaption !== (requestedFigure.caption || ""));
    if (dirty) rememberCaptionDraft(requestedFigureId, generatedCaption);
    else forgetCaptionDraft(requestedFigureId);
    forgetFigureEditorDraft(requestedFigureId, "caption_prompt");
    const figure = selectedFigure();
    if (!figure || figure.id !== requestedFigureId) return;
    captionInput.value = generatedCaption;
    $("figure-caption-prompt").value = "";
    $("figure-caption-prompt").dataset.dirty = "false";
    captionInput.dataset.dirty = String(dirty);
    $("figure-caption-status").textContent = dirty
      ? "GPT candidate 尚未保存"
      : "GPT candidate 与当前 Caption 相同";
    updateFigureButtonStates();
  } catch (error) {
    $("figure-caption-status").textContent = error.message;
    showMessage(error.message, true);
  } finally {
    figureRequestBusy = false;
    button.textContent = originalLabel;
    updateFigureButtonStates();
  }
};

async function saveFigureCaption() {
  if (figureRequestBusy) return false;
  figureRequestBusy = true;
  const requestedFigureId = activeFigure;
  const input = $("figure-caption");
  const requestedCaption = input.value;
  try {
    updateFigureButtonStates();
    const payload = await request("/api/figure/caption", {
      method: "POST",
      body: JSON.stringify({figure_id: requestedFigureId, caption: requestedCaption}),
    });
    state = payload.state;
    forgetCaptionDraft(requestedFigureId);
    if (input.dataset.figureId === requestedFigureId && input.value === requestedCaption) {
      input.dataset.dirty = "false";
    }
    render();
    if (selectedFigure() && selectedFigure().id === requestedFigureId) {
      $("figure-message").textContent = payload.message || "Caption 已保存。";
      $("figure-message").classList.remove("error");
    }
    return true;
  } catch (error) {
    if (selectedFigure() && selectedFigure().id === requestedFigureId) {
      $("figure-caption-status").textContent = `Caption 保存失败：${error.message}`;
      $("figure-message").textContent = error.message;
      $("figure-message").classList.add("error");
    }
    return false;
  } finally {
    figureRequestBusy = false;
    updateFigureButtonStates();
  }
}

$("figure-caption-save").onclick = saveFigureCaption;

async function approveFigureOrSaveCaption() {
  const figure = selectedFigure();
  const requestedFigureId = figure && figure.id;
  const dirty = $("figure-caption").dataset.dirty === "true";
  if (dirty) {
    const saved = await saveFigureCaption();
    if (!saved || (figure && figure.status === "approved")) return;
  }
  return runFigureAction(
    "/api/figure/approve",
    {figure_id: requestedFigureId},
    "正在插入正文、补充 Figure 引用并重新编译 PDF…",
  );
}

$("figure-approve").onclick = approveFigureOrSaveCaption;

$("data-compose").onclick = () => runFigureAction(
  "/api/figure/compose",
  {
    figure_id: activeFigure,
    layout_prompt: $("data-layout-prompt").value,
    layout_width: $("figure-layout-mode").value === "two-column"
      ? "two-column"
      : "single-column",
  },
  "本地 Agent 正在解释组合 Prompt；随后将在 PPT 中排版并导出、裁剪 PDF…",
);

function openRuntimeKeyDialog() {
  const dialog = $("runtime-key-dialog");
  $("runtime-key-message").textContent = "";
  $("runtime-key-provider").value = state.llm_provider || "openai";
  if (!dialog.open) dialog.showModal();
  setTimeout(() => $("runtime-key-input").focus(), 0);
}

function closeRuntimeKeyDialog() {
  $("runtime-key-input").value = "";
  $("runtime-key-dialog").close();
}

$("runtime-key-open").onclick = openRuntimeKeyDialog;
$("runtime-key-close").onclick = closeRuntimeKeyDialog;
$("runtime-key-cancel").onclick = closeRuntimeKeyDialog;
$("runtime-key-dialog").addEventListener("click", (event) => {
  if (event.target === $("runtime-key-dialog")) closeRuntimeKeyDialog();
});
$("runtime-key-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = $("runtime-key-submit");
  const status = $("runtime-key-message");
  submit.disabled = true;
  status.textContent = "正在安全更新…";
  try {
    const payload = await request("/api/runtime-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: $("runtime-key-provider").value,
        api_key: $("runtime-key-input").value,
      }),
    });
    $("runtime-key-input").value = "";
    state = payload.state;
    render();
    $("runtime-key-dialog").close();
  } catch (error) {
    $("runtime-key-input").value = "";
    status.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});
$("data-layout-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure) {
    rememberFigureEditorDraft(
      figure.id,
      "layout_prompt",
      event.currentTarget.value,
      figure.layout_prompt || "",
    );
  }
});

$("single-data-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure && (figure.panels || []).length) {
    const panel = figure.panels[0];
    rememberFigureEditorDraft(
      figure.id,
      `panel:${panel.id}`,
      event.currentTarget.value,
      panel.agent_prompt || "",
    );
  }
});

function rememberTableEditorDraft(event, field, canonicalValue) {
  const figure = selectedFigure();
  event.currentTarget.dataset.dirty = "true";
  if (figure) {
    rememberFigureEditorDraft(figure.id, field, event.currentTarget.value, canonicalValue);
  }
}

$("table-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  rememberTableEditorDraft(event, "table_generation_prompt", (figure && figure.generation_prompt) || "");
});

$("table-agent-prompt").addEventListener("input", (event) => {
  const figure = selectedFigure();
  rememberTableEditorDraft(event, "table_agent_prompt", (figure && figure.agent_prompt) || "");
});

$("table-latex").addEventListener("input", (event) => {
  const figure = selectedFigure();
  rememberTableEditorDraft(event, "table_latex", (figure && figure.latex) || "");
  updateFigureButtonStates();
});

$("data-approve").onclick = approveFigureOrSaveCaption;

$("table-generate").onclick = () => runFigureAction(
  "/api/table/generate",
  {
    table_id: activeFigure,
    generation_prompt: $("table-prompt").value,
  },
  "正在启动本地 Agent 从可追溯结果生成表格初稿…",
);

$("table-agent-edit").onclick = () => startFigureJob(
  "/api/table/agent-edit",
  {
    table_id: activeFigure,
    latex: $("table-latex").value,
    agent_prompt: $("table-agent-prompt").value,
  },
  "正在启动本机 Codex agent 修改表格…",
);

$("table-save").onclick = () => runFigureAction(
  "/api/table/save",
  {table_id: activeFigure, latex: $("table-latex").value},
  "正在保存表格修改…",
);

$("table-approve").onclick = () => runFigureAction(
  "/api/table/approve",
  {table_id: activeFigure, latex: $("table-latex").value},
  "正在插入正文并重新编译 PDF…",
);

refresh().catch((error) => {
  $("section-title").textContent = "加载失败";
  $("load-error-message").textContent = error.message;
  $("load-error").hidden = false;
});
