const $ = (id) => document.getElementById(id);
const embeddedInResearchStudio = new URLSearchParams(window.location.search).get("embedded") === "research-studio";
const studioUiLanguage = "en";
const studioT = (_unused, english) => english;
if (embeddedInResearchStudio) document.documentElement.classList.add("research-studio-embedded");
function translateStudioUi() { document.documentElement.lang = "en"; }
translateStudioUi();
const STUDIO_BASE_PATH = ["/demo-studio", "/paper-studio"].find(
  prefix => window.location.pathname === prefix
    || window.location.pathname.startsWith(prefix + "/"),
) || "";

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
  return "writing";
})();
let activeSection = (() => {
  const requested = new URLSearchParams(window.location.search).get("section");
  if (requested) return requested;
  return "abstract";
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
let modelApplyBusy = false;
let figureRequestBusy = false;
let generatedResetBusy = false;
let fullDraftRequestBusy = false;
let queuedFullDraftStart = false;
let queuedSectionDraftStart = "";
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
      if (typeof value === "string") {
        // Legacy drafts predate generation-version tracking. Treat them as
        // older than any server-generated caption.
        captionDrafts.set(figureId, {value, generatedAt: ""});
      } else if (value && typeof value.value === "string") {
        captionDrafts.set(figureId, {
          value: value.value,
          generatedAt: String(value.generatedAt || ""),
        });
      }
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
  const figure = state && (state.figures || []).find((item) => item.id === figureId);
  captionDrafts.set(figureId, {
    value: caption,
    generatedAt: String((figure && figure.caption_generated_at) || ""),
  });
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
const DEMO_SAFE_WRITE_PATHS = new Set(["/api/pdf/locate", "/api/select-paragraph"]);

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
    throw new Error("This is a read only demo; cannot generate or modify content.");
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
  const planningOnly = Boolean(section && section.writing_mode === "plan_only");
  const paragraph = section && section.current_paragraph;
  const candidate = paragraph && paragraph.candidate;
  const accepted = paragraph && paragraph.accepted_text;
  const visibleText = $("candidate").value.trim();
  const manualRevision = visibleText !== proseBaselineText.trim();
  const canAccept = !planningOnly && Boolean(visibleText) && Boolean(candidate || manualRevision);
  $("accept").disabled = !canAccept;
  $("accept").textContent = canAccept
    ? "Accept → LaTeX"
    : accepted
      ? "LaTeX has been written."
      : "Waiting for candidate.";
  $("accept").title = accepted && !canAccept
    ? "The current version is written in LaTeX; you can modify the main text directly or fill in a comment to have GPT generate a new candidate."
    : "";
}

function setBusy(busy, label = "") {
  const planningOnly = Boolean(
    state && state.sections && state.sections[activeSection]
    && state.sections[activeSection].writing_mode === "plan_only"
  );
  $("generate").disabled = busy || planningOnly;
  $("compile").disabled = busy;
  $("candidate").disabled = busy || planningOnly;
  $("comment").disabled = busy || planningOnly;
  $("model").disabled = busy;
  $("model-apply").disabled = busy;
  if (busy) {
    $("accept").disabled = true;
    const paragraph = state && state.sections && state.sections[activeSection]
      ? state.sections[activeSection].current_paragraph
      : null;
    if (paragraph && !$("candidate").value) {
      $("candidate").placeholder = "Currently combining approved paragraph structure working abstract and experimental results to generate the current paragraph.";
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
  $("model-apply").disabled = modelApplyBusy
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
  $("title-save").textContent = changed ? "Confirm writing to LaTeX" : "Written to PDF";
  $("title-save").title = changed ? "Update LaTeX after confirmation and recompile the PDF." : "The current title has been written into the PDF.";
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
  $("title-current-summary").textContent = editor.current_title || "Title not found.";
  renderTitleDraftInput(titleInput, "title", editor.candidate || editor.current_title || "", force);
  renderTitleDraftInput(promptInput, "prompt", editor.prompt || "", force);
  $("title-status").textContent = editor.last_message || (
    editor.candidate ? "GPT candidate Not saved yet; can be edited and confirmed." : "Must confirm after modification before writing to LaTeX."
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
    button.title = `${paragraph.status}: ${paragraph.purpose}${artifacts.length ? ` · association ${artifacts.map((item) => item.id).join(", ")}` : ""}`;
    button.className = `${paragraph.status}${paragraph.selected ? " selected" : ""}${visibleArtifacts.length ? " has-artifact" : ""}`;
    button.dataset.paragraphId = paragraph.id;
    button.disabled = false;
    button.onclick = async () => {
      if (paragraph.selected || paragraphRequestBusy) return;
      paragraphRequestBusy = true;
      const requestedSection = activeSection;
      try {
        setBusy(true, `Switching to. ${paragraph.id}…`);
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
              ? `Switched to ${paragraph.id}; Can continue editing based on the accepted version.`
              : `Switched to ${paragraph.id}.`,
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

function renderReferenceContext(section) {
  const card = $("reference-context-card");
  const context = section.reference_context || {};
  const excerpts = Array.isArray(context.excerpts) ? context.excerpts : [];
  const constraints = Array.isArray(context.writing_constraints) ? context.writing_constraints : [];
  const abstracted = context.mode === "abstracted";
  if (!context.source_heading || !context.logic_summary_zh || (!excerpts.length && !constraints.length)) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  $("reference-context-title").textContent = abstracted
    ? "Refined reference structure"
    : "The corresponding formulation in the reference papers.";
  $("reference-context-summary").textContent = context.logic_summary_zh;
  const toggle = $("reference-excerpts-toggle");
  toggle.hidden = abstracted;
  $("reference-excerpts-title").textContent = abstracted ? "" : "View referenced original text.";
  const root = $("reference-context-excerpts");
  root.replaceChildren(...excerpts.map((excerpt) => {
    const container = document.createElement("div");
    container.className = "reference-excerpt";
    const quote = document.createElement("blockquote");
    quote.textContent = excerpt.text || "";
    container.append(quote);
    return container;
  }));
}

function renderStructureBlueprint(section) {
  const root = $("structure-blueprint");
  root.innerHTML = "";
  (section.structure_blueprint || []).forEach((paragraph) => {
    const row = document.createElement("div");
    row.className = `structure-row${section.current_paragraph && section.current_paragraph.id === paragraph.id ? " active" : ""}`;
    const id = document.createElement("span");
    id.textContent = paragraph.id;
    const content = document.createElement("span");
    content.textContent = paragraph.purpose;
    row.append(id, content);
    root.appendChild(row);
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
  const budget = state && state.pdf && state.pdf.page_budget;
  const budgetText = budget && budget.limit && budget.content_pages
    ? ` · Body ${budget.content_pages}/${budget.limit}`
    : "";
  indicator.textContent = position && total
    ? `Page ${position.page} / ${total}${budgetText}`
    : "Page — / —";
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
  toggle.textContent = pdfNavigationVisible ? "Hide navigation bar." : "Show navigation bar.";
  toggle.setAttribute("aria-pressed", pdfNavigationVisible ? "true" : "false");
  if (state.pdf.exists) {
    download.hidden = false;
    download.href = studioPath(state.pdf.url || "/paper.pdf");
    download.download = `${String(state.project && state.project.id || "paper").replace(/[^A-Za-z0-9._-]+/g, "-")}.pdf`;
    viewer.hidden = false;
    viewer.classList.toggle("navigation-visible", pdfNavigationVisible);
    empty.hidden = true;
    const signature = `${state.pdf.version}:${state.pdf.page_count}`;
    if (pages.dataset.signature !== signature) {
      const previousPosition = capturePdfPosition(pages);
      pages.replaceChildren();
      for (let pageNumber = 1; pageNumber <= state.pdf.page_count; pageNumber += 1) {
        const page = document.createElement("div");
        page.className = "pdf-page";
        page.dataset.page = String(pageNumber);
        page.title = "Double-click the body text, image, or table to jump to the corresponding editing position.";
        const image = document.createElement("img");
        image.alt = `Paper PDF page ${pageNumber} page`;
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
        thumbnail.title = `Go to the ${pageNumber} page`;
        const image = document.createElement("img");
        image.alt = `the ${pageNumber} page`;
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
    viewer.hidden = true;
    empty.hidden = false;
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
    showMessage("Locating source content in PDF…");
    const payload = await request("/api/pdf/locate", {
      method: "POST",
      body: JSON.stringify({page, x, y}),
    });
    if (locateRequestId !== pdfLocateRequestId) return;
    const target = payload.target;
    activeSection = target.section;
    activeView = target.view;
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
      showMessage(`Returned from PDF ${target.paragraph_id} The text editing position.`);
      return;
    }
    activeFigure = target.artifact_id;
    try {
      localStorage.setItem(ACTIVE_FIGURE_KEY, activeFigure);
    } catch (_error) {}
    render();
    $("figure-message").textContent = `Returned from PDF ${target.artifact_id} of${target.view === "tables" ? "table" : "Image"}Edit position.`;
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
  const imageReady = Boolean(
    figure.paper_preview_url
    || ["agent_generating", "built", "approved"].includes(figure.status)
  );
  const paperReady = Boolean(
    figure.paper_preview_url
    || ((figure.downloads || {}).pdf && (figure.downloads || {}).pptx)
  );
  const promptActive = figure.status === "prompt_generating" || !promptReady;
  const imageActive = ["image_generating", "agent_generating"].includes(figure.status)
    || (promptReady && !imageReady && figure.status !== "prompt_generating");
  const paperActive = ["agent_generating", "agent_editing"].includes(figure.status)
    || (imageReady && !paperReady && figure.status !== "image_generating");
  const stages = [
    {
      id: "prompt",
      ready: promptReady,
      active: promptActive,
      status: figure.status === "prompt_generating" ? "Generating" : (promptReady ? "Ready" : "To be generated"),
    },
    {
      id: "image",
      ready: imageReady,
      active: imageActive,
      status: ["image_generating", "agent_generating"].includes(figure.status)
        ? "Drawing in progress" : (imageReady ? "Completed" : "Waiting for Prompt"),
    },
    {
      id: "paper",
      ready: paperReady,
      active: paperActive,
      status: ["agent_generating", "agent_editing"].includes(figure.status)
        ? "Auto-rebuilding."
        : (paperReady ? "Completed" : "Then automatically rebuild."),
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
  const captionNeedsBackfill = Boolean(figure.caption_needs_backfill);
  const submittedPrompt = $("draw-prompt").value.trim();
  const promptInstruction = $("prompt-instruction").value.trim();
  $("figure-prompt").disabled = state.demo_mode
    || !figure.ready || !generationReady || running || Boolean(submittedPrompt && !promptInstruction);
  $("figure-draw").disabled = !figure.ready || !generationReady || running || !submittedPrompt;
  $("figure-draw").textContent = figure.paper_preview_url
    ? "Confirm new Prompt → Codex Redraw"
    : "Confirm prompt → Codex plotting";
  $("figure-cancel").hidden = figure.status !== "image_generating";
  $("figure-cancel").disabled = figure.status !== "image_generating" || figureRequestBusy;
  const mechanismBuildFailed = Boolean(
    figure.kind === "mechanism"
    && figure.status === "failed"
    && figure.draw_prompt
    && !figure.paper_preview_url
  );
  $("figure-build").hidden = !mechanismBuildFailed;
  $("figure-build").disabled = !figure.ready || !generationReady || running || !figure.preview_url;
  $("figure-build").textContent = "Retry editable PPT/PDF reconstruction.";
  $("figure-approve").disabled = (
    table
    || !insertionReady
    || !(figure.downloads || {}).pdf
    || !(figure.downloads || {}).pptx
    || (figure.status === "approved" && !captionDirty && !captionNeedsBackfill)
  );
  const panelsReady = (figure.panels || []).length > 0 && (figure.panels || []).every((panel) => panel.status === "built");
  const loadedCandidate = $("figure-preview-pdf").dataset.loaded;
  const expectedCandidate = figure.preview_url
    ? `${figure.preview_url}#toolbar=0&navpanes=0&view=FitH`
    : "";
  $("data-compose").disabled = table || !figure.ready || running || !panelsReady;
  $("single-data-generate").disabled = table || !figure.ready || running;
  $("data-compose").textContent = figure.composition_ready
    ? "Reparse the Prompt and generate a composite image."
    : "Composite figure";
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
  $("figure-layout-mode").disabled = running || !hasPlacement;
  $("figure-approve").textContent = figure.status === "approved"
    ? (captionDirty
      ? "Update Caption → PDF"
      : captionNeedsBackfill
        ? "Generate additional caption. → PDF"
        : "Body text has been inserted.")
    : "Confirm and insert the body text";
  $("data-approve").textContent = figure.status === "approved"
    ? (captionDirty
      ? "Update Caption → PDF"
      : captionNeedsBackfill
        ? "Generate additional caption. → PDF"
        : "Reinsert")
    : "Confirm and insert the body text";
  const visibleTableLatex = $("table-latex").value.trim();
  const tableLatexDirty = $("table-latex").dataset.dirty === "true";
  $("table-generate").disabled = !table || !figure.ready || running;
  $("table-agent-edit").disabled = !table || !figure.ready || running || !visibleTableLatex;
  $("table-save").disabled = !table || running || !visibleTableLatex || !tableLatexDirty;
  $("table-save").textContent = figure.status === "approved" && tableLatexDirty
    ? "Save changes (requires reconfirmation)."
    : "Save changes";
  $("table-approve").disabled = (
    !table
    || !figure.ready
    || running
    || !visibleTableLatex
    || (figure.status === "approved" && !tableLatexDirty)
  );
  $("table-approve").textContent = figure.status === "approved"
    ? (tableLatexDirty ? "Update table → PDF" : "Body text has been inserted.")
    : "Confirm and insert the body text";
  $("figure-caption").disabled = table || running;
  $("figure-caption-prompt").disabled = table || running;
  $("figure-caption-generate").disabled = table || running;
  $("figure-caption-save").disabled = table || running || !captionDirty;
  $("figure-caption-save").textContent = figure.status === "approved"
    ? "Save caption and update PDF."
    : "Save caption";
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
  const generatorName = state.online_project ? "Python" : "Local Agent";
  generate.textContent = panel.preview_url
    ? `${generatorName} Regenerate this figure`
    : `${generatorName} Generate this figure.`;
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
    `Generating ${figure.id} Final single figure…`,
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
          <progress class="figure-progress-track" max="100" value="0"></progress><strong></strong>
        </div>
        <label class="data-panel-prompt-label">Modification prompt for this subfigure.</label>
        <textarea class="data-panel-prompt" rows="3" placeholder="For example shorten the title and move the legend to the upper right corner; only adjust this figure and do not change the data."></textarea>
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
      ? "Modification prompt for this figure."
      : "Modification prompt for this subfigure.";
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
        panelEmpty.textContent = singlePanel ? "This figure has not yet been generated." : "This independent subfigure has not yet been generated";
        preview.replaceChildren(panelEmpty);
      }
    }

    const progress = card.querySelector(".data-panel-progress");
    progress.hidden = panel.status !== "agent_generating";
    progress.querySelector(".figure-progress-track").value = Math.max(0, Math.min(100, panel.progress || 0));
    progress.querySelector("strong").textContent = panel.progress_message
      || (singlePanel ? "Local Agent is processing this figure…" : "Local Agent is processing this sub-figure.");

    const input = card.querySelector(".data-panel-prompt");
    renderFigureEditorInput(input, figure.id, `panel:${panel.id}`, panel.agent_prompt || "");
    const generate = card.querySelector(".data-panel-generate");
    generate.textContent = panel.preview_url ? "Local Agent regenerates this." : "Local agent generated this.";
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
        ? `Generating ${figure.id} Final single figure…`
        : `Generating separately ${figure.id}(${panel.id})…`,
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
    if (figureRequestBusy) {
      // Switching figures immediately after an approval can race with the
      // previous request's finally block. Do not consume this figure's only
      // automatic attempt while the shared request lock is still held.
      autoDataPanelAttempted.delete(attemptKey);
      setTimeout(() => scheduleAutomaticDataPanel(current), 100);
      return;
    }
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
        ? `Auto-generating. ${current.id} Final single figure candidate…`
        : `Auto-generating. ${current.id}(${currentNext.id}); Continue to the next figure after completion…`,
    );
  }, 50);
}

function scheduleAutomaticTableGenerate(figure) {
  // Reported directly: a researcher clicked into an empty table and nothing
  // happened -- generating one required finding "table-generate", which
  // sits inside the collapsed Advanced <details> disclosure. Data
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
      `Auto-generating. ${current.id} Table draft…`,
    );
  }, 50);
}

function renderLayoutPrompt(figure) {
  const input = $("data-layout-prompt");
  const singlePanel = (figure.panels || []).length === 1;
  renderFigureEditorInput(input, figure.id, "layout_prompt", figure.layout_prompt || "");
  const plan = figure.layout_plan || {};
  $("data-workflow-note").textContent = singlePanel
    ? "This is a standalone single figure: click the button below to directly generate the final PDF candidate without subfigure corner marks."
    : "Please generate and review each PDF candidate separately. When all are satisfactory, manually click Synthesize Figure to generate PPTX and vector PDF candidates.";
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
  $("section-title").textContent = `${state.sections[activeSection].title} · ${tableMode ? "table" : "figure"}`;
  if (!figures.length) {
    cards.innerHTML = `<div class="data-note">The current paragraph and section do not have the planned structure. ${tableMode ? "table" : "figure"}.</div>`;
    $("figure-detail").hidden = true;
    return;
  }
  $("figure-detail").hidden = false;
  figures.forEach((figure) => {
    const button = document.createElement("button");
    button.className = `figure-card${figure.id === activeFigure ? " selected" : ""}${figure.ready ? "" : " blocked"}`;
    button.innerHTML = `
      <span class="figure-card-id">${figure.id}</span>
      <span><strong>${figure.title}</strong><small>${figure.placeholder_only ? "Online service does not provide charting functionality." : figure.kind === "table" ? "Results table · Editable LaTeX." : figure.kind === "source" ? "Source figure · Reference paper evidence." : figure.kind === "mechanism" ? "Mechanism diagram · finish first" : "Data figure · results/ driver."}</small></span>
      <span class="figure-card-state ${figure.placeholder_only ? "placeholder" : figure.status}">${figure.placeholder_only ? "placeholder" : figure.ready ? figure.status : "locked"}</span>
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
  const sourceFigure = figure.kind === "source";
  const placeholderOnly = Boolean(figure.placeholder_only);
  $("figure-phase").textContent = placeholderOnly
    ? "PHASE PLACEHOLDER"
    : `PHASE ${figure.phase || "SOURCE"} · ${figure.kind === "table" ? "EDITABLE TABLE" : sourceFigure ? "VERIFIED SOURCE FIGURE" : figure.kind === "mechanism" ? "EDITABLE SCHEMATIC" : "DATA FIGURE"}`;
  $("figure-title").textContent = `${figure.id} · ${figure.title}`;
  $("figure-description").textContent = `${figure.description} · ${figure.width} · ${figure.label}`;
  document.querySelector("#figure-detail .figure-detail-head").hidden = placeholderOnly;
  $("figure-phase").hidden = placeholderOnly;
  $("figure-title").hidden = placeholderOnly;
  $("figure-description").hidden = placeholderOnly;
  const gate = $("figure-gate");
  const insertionBlocked = figure.insertion_ready === false;
  gate.textContent = !figure.ready
    ? figure.gate_reason
    : insertionBlocked
      ? figure.insertion_gate_reason
      : "";
  gate.hidden = placeholderOnly;
  gate.classList.toggle("show", !placeholderOnly && (!figure.ready || insertionBlocked));
  const onlinePlaceholder = $("online-figure-placeholder");
  onlinePlaceholder.hidden = !placeholderOnly;
  $("online-figure-placeholder-message").textContent = placeholderOnly
    ? figure.placeholder_message
    : "";
  const mechanismPrerequisite = $("mechanism-generation-prerequisite");
  const mechanismPrerequisiteBlocked = (
    figure.kind === "mechanism" && figure.generation_ready === false
  );
  mechanismPrerequisite.hidden = placeholderOnly || !mechanismPrerequisiteBlocked;
  $("mechanism-generation-prerequisite-text").textContent = mechanismPrerequisiteBlocked
    ? figure.generation_gate_reason
    : "";

  const progress = $("figure-progress");
  const running = figureIsRunning(figure);
  const singleData = figure.kind === "data" && (figure.panels || []).length === 1;
  progress.hidden = !running || (figure.kind === "data" && !singleData);
  $("figure-progress-bar").value = Math.max(0, Math.min(100, figure.progress || 0));
  const elapsed = running && Number.isFinite(figure.running_seconds)
    ? ` · Waiting ${figure.running_seconds} seconds`
    : "";
  $("figure-progress-message").textContent = `${figure.progress_message || ""}${elapsed}`;

  const mechanismPreviewSwitch = $("mechanism-preview-switch");
  const mechanismPreviewToggle = $("mechanism-preview-toggle");
  const mechanismPreviewNote = $("mechanism-preview-note");
  const mechanismBuildStatus = $("mechanism-build-status");
  const paperVersionInserted = Boolean(
    figure.status === "approved"
    && figure.paper_preview_url
  );
  const hasMechanismVersions = false;
  let mechanismPreviewMode = mechanismPreviewModes.get(figure.id) || "paper";
  if (!hasMechanismVersions || paperVersionInserted) {
    mechanismPreviewModes.delete(figure.id);
    mechanismPreviewMode = "paper";
  }
  mechanismPreviewSwitch.hidden = !hasMechanismVersions;
  const mechanismBuildPending = (
    figure.kind === "mechanism"
    && ["image_generating", "agent_generating"].includes(figure.status)
    && !figure.paper_preview_url
  );
  mechanismBuildStatus.hidden = !mechanismBuildPending;
  mechanismBuildStatus.textContent = mechanismBuildPending
    ? (["agent_generating", "agent_editing"].includes(figure.status)
      ? "Codex Generating editable PPT PDF in the background."
      : figure.status === "failed"
        ? `Editable PPT/PDF reconstruction failed.${figure.last_message || figure.progress_message || "Please click Retry."}`
        : "Editable PPT/PDF is not yet complete; please re-run Codex drawing.")
    : "";
  const textFreeDraftPreview = Boolean(figure.draft_preview_no_text);
  mechanismPreviewToggle.textContent = mechanismPreviewMode === "paper"
    ? (textFreeDraftPreview ? "Show layout draft (no text)." : "Show composition draft")
    : "Show editable PPT/PDF full version.";
  mechanismPreviewNote.textContent = paperVersionInserted
    ? "The current preview and the main PDF use the same image file."
    : textFreeDraftPreview
      ? "The draft is a layout reference; labels and caption text reside in the editable PPT/PDF version."
      : "The draft is for visual review; insertion and download use the editable PPT/PDF version.";
  const effectivePreviewUrl = placeholderOnly
    ? null
    : (figure.paper_preview_url || figure.preview_url);
  const effectivePreviewType = figure.paper_preview_url ? "pdf" : figure.preview_type;

  const image = $("figure-preview-image");
  const pdf = $("figure-preview-pdf");
  const tablePreview = $("table-preview");
  image.hidden = true;
  pdf.hidden = true;
  tablePreview.hidden = true;
  if (isTable) {
    if (effectivePreviewUrl) {
      image.src = effectivePreviewUrl;
      image.alt = `${figure.id} LaTeX-compiled table preview`;
      image.hidden = false;
    }
  } else if (effectivePreviewUrl && effectivePreviewType === "image") {
    image.src = effectivePreviewUrl;
    image.hidden = false;
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
    pdf.hidden = false;
  }

  const mechanism = figure.kind === "mechanism" && !placeholderOnly;
  const captionBox = $("figure-caption-box");
  captionBox.hidden = isTable || placeholderOnly;
  const captionInput = $("figure-caption");
  const changedCaptionFigure = captionInput.dataset.figureId !== figure.id;
  const savedCaption = figure.caption || "";
  const generatedAt = String(figure.caption_generated_at || "");
  const captionDraftRecord = captionDrafts.get(figure.id);
  const automaticCaptionChanged = Boolean(
    captionDraftRecord
    && figure.caption_source === "paragraph_accept"
    && String(captionDraftRecord.generatedAt || "") !== generatedAt
  );
  if (automaticCaptionChanged) {
    // A newly accepted citing paragraph owns the canonical caption. Discard an
    // older browser draft so it cannot hide the caption that was just generated.
    forgetCaptionDraft(figure.id);
  }
  const refreshedCaptionDraftRecord = captionDrafts.get(figure.id);
  const captionDraft = refreshedCaptionDraftRecord
    ? refreshedCaptionDraftRecord.value
    : undefined;
  if (captionDraft === savedCaption) {
    forgetCaptionDraft(figure.id);
  }
  if (changedCaptionFigure || automaticCaptionChanged) {
    captionInput.value = captionDraft !== undefined && captionDraft !== savedCaption
      ? captionDraft
      : savedCaption;
    captionInput.dataset.figureId = figure.id;
    captionInput.dataset.dirty = String(captionInput.value !== savedCaption);
  } else if (captionInput.dataset.dirty !== "true" && document.activeElement !== captionInput) {
    captionInput.value = savedCaption;
    captionInput.dataset.dirty = "false";
  }
  captionInput.dataset.captionGeneratedAt = generatedAt;
  const captionPrompt = $("figure-caption-prompt");
  renderFigureEditorInput(captionPrompt, figure.id, "caption_prompt", "");
  const captionDirty = captionInput.dataset.dirty === "true";
  const automaticCaptionStatus = figure.caption_last_error
    ? `Automatic caption generation failed:${figure.caption_last_error}`
    : (figure.caption_source === "paragraph_accept"
      ? `Caption Has been accepted ${figure.caption_generated_from_paragraph || "Citation paragraph"} Auto-generating.`
      : "");
  $("figure-caption-status").textContent = captionDirty
    ? (figure.status === "approved"
      ? "Caption Modified, not yet updated in the main text and PDF."
      : "Caption Modified, not yet saved")
    : automaticCaptionStatus
      ? automaticCaptionStatus
    : (figure.status === "approved"
      ? "Caption Written into main text and PDF"
      : "The current main text will use this caption.");
  $("mechanism-controls").hidden = !mechanism;
  $("mechanism-approve-after-placement").hidden = !mechanism;
  $("data-controls").hidden = placeholderOnly || mechanism || isTable || sourceFigure;
  $("table-agent-controls").hidden = !isTable || Boolean(state.online_project);
  $("table-controls").hidden = !isTable || placeholderOnly;
  $("table-workflow-note").textContent = state.online_project
    ? "The image above is produced by the actual LaTeX compilation; it can generate a structured draft and allow direct LaTeX editing."
    : "The top image is compiled by the current LaTeX; initial draft and experiment result related edits are performed by the local Agent.";
  $("table-generate").textContent = state.online_project ? "Generate initial table draft" : "Local agent generated the first draft.";
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
  if (!mechanism && !isTable && !sourceFigure) {
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
    item.textContent = `${option.id} after${option.accepted ? "" : "(Main text not completed)"}`;
    item.disabled = !option.accepted;
    placement.appendChild(item);
  });
  if (figure.placement_after) placement.value = figure.placement_after;
  $("figure-placement-row").hidden = placeholderOnly;
  $("figure-layout-control").hidden = placeholderOnly;
  $("figure-layout-mode").value = figure.layout_mode || "single-column";
  $("figure-prompt").textContent = figure.draw_prompt
    ? "Update Prompt per the right side instructions."
    : "GPT Generate drawing prompt.";
  updateMechanismFlow(figure);
  updateFigureButtonStates();

  const downloads = $("figure-downloads");
  downloads.innerHTML = "";
  Object.entries(figure.downloads || {}).forEach(([kind, url]) => {
    const link = document.createElement("a");
    link.href = url;
    link.textContent = `download ${kind.toUpperCase()}`;
    link.download = "";
    downloads.appendChild(link);
  });
  downloads.hidden = placeholderOnly;
  $("figure-message").textContent = placeholderOnly ? "" : (figure.last_message || "");
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
          "Automatically generating drawing prompts from the current section text.",
        );
      }
    }, 50);
  }
  scheduleAutomaticDataPanel(figure);
  scheduleAutomaticTableGenerate(figure);
}

const DEMO_READ_ONLY_CONTROL_IDS = [
  "generate", "accept", "candidate", "comment", "reset-generated",
  "compile", "model", "model-apply", "runtime-key-open",
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
  document.querySelectorAll("input, textarea, select, [contenteditable='true']")
    .forEach((element) => {
      element.disabled = true;
      element.setAttribute("contenteditable", "false");
      element.setAttribute("aria-readonly", "true");
    });
  DEMO_READ_ONLY_CONTROL_IDS.forEach((id) => {
    const element = $(id);
    if (element) element.disabled = true;
  });
  document.querySelectorAll(".figure-card, .figure-actions button")
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
  $("artifact-workflow-summary").textContent = state.online_project
    ? "Online keep only the main text, editable tables, and Python data plots; other figures are inserted into the paper as placeholders with captions and labels."
    : "Mechanism diagrams designed separately; data plots and tables are generated from results/ and inserted into the corresponding paragraph after confirmation.";
  const modelInput = $("model");
  const modelOptions = state.llm_model_options || [];
  $("model-suggestions").replaceChildren(...modelOptions.map((option) => {
    const element = document.createElement("option");
    element.value = option.id;
    element.label = option.label;
    return element;
  }));
  renderTitleDraftInput(modelInput, "model", state.model || "gpt-5-nano");
  updateModelApplyButton();
  $("api-key-setup").hidden = apiKeyReady;
  $("api-key-setup-command").textContent = apiKeySetup.setup_command || 'export OPENAI_API_KEY="Paste your API key."';
  $("api-key-setup-description").textContent = `${apiKeySetup.provider_label || "current"} API is not configured. Set it in the local terminal that launches Paper Studio; keys are never exposed to the web page. Mechanism figures are drawn locally as editable native shapes by Codex and do not require an image API.`;
  $("api-key-restart-command").textContent = apiKeySetup.restart_command || "python3 -m research_avatar.paper_studio.server";
  document.querySelector(".workspace").classList.toggle("api-key-missing", !apiKeyReady);
  $("studio-title").textContent = project.studio_title || "Paper Studio";
  $("runtime-project-id").textContent = project.id || "—";
  $("runtime-report-version").textContent = project.report_version || "—";
  $("runtime-reports-updated").textContent = project.reports_updated_at
    ? new Date(project.reports_updated_at * 1000).toLocaleString()
    : "—";
  $("runtime-connection").textContent = "Connected";
  $("runtime-connection").className = "connected";
  const referencePaper = project.reference_paper || {};
  const referenceEl = $("project-reference-paper");
  if (referencePaper.title) {
    const meta = referencePaper.venue || "";
    referenceEl.replaceChildren();
    referenceEl.append(studioT("Reference paper:", "Reference paper: "));
    if (referencePaper.url) {
      const link = document.createElement("a");
      link.href = referencePaper.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = referencePaper.title;
      referenceEl.append(link);
    } else {
      referenceEl.append(referencePaper.title);
    }
    if (meta) referenceEl.append(studioT(`(${meta})`, ` (${meta})`));
    referenceEl.hidden = false;
  } else {
    referenceEl.hidden = true;
  }
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
    $("section-title").textContent = "Paper not yet loaded.";
    ["writing-view", "figures-view", "tables-view", "compile", "reset-generated", "model", "model-apply", "runtime-key-open"].forEach((id) => {
      $(id).disabled = true;
    });
    return;
  }
  ["writing-view", "figures-view", "tables-view", "compile", "reset-generated", "model", "runtime-key-open"].forEach((id) => {
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
  const planningOnly = section.writing_mode === "plan_only";
  $("section-title").textContent = section.title;
  $("title-editor").hidden = activeSection !== "abstract";
  if (activeSection === "abstract") renderTitleEditor();
  renderParagraphNavigation(section);
  renderReferenceContext(section);
  renderStructureBlueprint(section);
  const paragraph = section.current_paragraph;
  const candidate = paragraph && paragraph.candidate;
  $("paragraph-id").textContent = paragraph ? paragraph.id : "complete";
  $("paragraph-progress").textContent = paragraph
    ? `${paragraph.position} / ${paragraph.total}`
    : `${section.paragraph_count} / ${section.paragraph_count}`;
  $("candidate-label").textContent = paragraph
    ? candidate
      ? "Current candidate paragraph."
      : paragraph.accepted_text
        ? "Accepted version (may still be modified)."
        : "Current candidate paragraph."
    : "Section content has been accepted and written in LaTeX.";
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
  $("candidate").placeholder = planningOnly
    ? "No experimental results uploaded: this section only keeps paragraph aims and planned experiments, and does not generate body text."
    : paragraph
    ? paragraph.accepted_text
      ? "This is the current LaTeX version; after filling the comment you can continue to modify."
      : "Waiting to generate the current paragraph…"
    : "This section is completed.";
  $("comment").value = commentDrafts.get(editorKey) || "";
  updateAcceptButton();
  $("candidate").disabled = planningOnly;
  $("comment").disabled = planningOnly;
  $("generate").disabled = !paragraph || planningOnly;
  const gate = $("gate");
  gate.textContent = planningOnly
    ? "Experiment results not uploaded: starting from Experiments only display the main idea of each section, writing task, and pending experiments, without invoking LLM to generate the main text."
    : state.outline_confirmed
    ? ""
    : "Outline Not confirmed yet. You may browse the interface, but you cannot Accept until you confirm and establish the LaTeX scaffold. → LaTeX.";
  gate.classList.toggle("show", planningOnly || !state.outline_confirmed);
  renderFullDraft();
  renderPdf();
  const fullDraftRunning = Boolean(
    state.full_draft && state.full_draft.job && state.full_draft.job.status === "running"
  );
  const sectionDraftJob = state.section_draft && state.section_draft.job;
  const sectionDraftRunning = Boolean(
    sectionDraftJob && sectionDraftJob.status === "running"
  );
  const sectionDraftArtifactsPending = Boolean(
    sectionDraftJob && sectionDraftJob.status === "artifacts_pending"
  );
  if (sectionDraftRunning && !fullDraftPollTimer) {
    fullDraftPollTimer = setTimeout(pollFullDraft, 900);
  }
  const sectionPending = (section.paragraph_navigation || []).filter(
    (item) => item.status !== "accepted"
  ).length;
  const sectionDraftStart = $("section-draft-start");
  sectionDraftStart.disabled = Boolean(
    planningOnly
    || fullDraftRunning
    || sectionDraftRunning
    || sectionDraftArtifactsPending
    || fullDraftRequestBusy
    || Boolean(queuedSectionDraftStart)
    || !state.outline_confirmed
    || !state.api_key_configured
    || sectionPending === 0
  );
  const activeSectionArtifactJob = Boolean(
    sectionDraftArtifactsPending
    && sectionDraftJob.section === activeSection
  );
  const activeSectionRunningJob = Boolean(
    sectionDraftRunning && sectionDraftJob.section === activeSection
  );
  const sectionProgressVisible = Boolean(
    sectionDraftJob
    && sectionDraftJob.section === activeSection
    && ["running", "artifacts_pending"].includes(sectionDraftJob.status)
  );
  const sectionProgressRow = $("section-draft-progress-row");
  sectionProgressRow.hidden = !sectionProgressVisible;
  $("section-draft-progress").value = Number(sectionDraftJob?.progress || 0);
  $("section-draft-progress-text").textContent = sectionProgressVisible
    ? `Completed ${Number(sectionDraftJob.completed || 0)} / ${Number(sectionDraftJob.total || sectionPending)} Section · ${sectionDraftJob.progress_message || "Generating current Section…"}`
    : "";
  sectionDraftStart.textContent = activeSectionRunningJob
    ? `${sectionDraftJob.progress_message || "Generating current Section…"}`
    : activeSectionArtifactJob
    ? `Completing this Section chart (${(sectionDraftJob.pending_artifacts || []).join(", ")})`
    : queuedSectionDraftStart === activeSection
    ? "After the current paragraph completes, this Section will be generated automatically."
    : sectionPending
      ? `One click generate current Section (${sectionPending} Paragraph to be completed).`
      : "The current section is complete.";
  applyReadOnlyDemoRestrictions();
}

function renderFullDraft() {
  const card = $("full-draft-card");
  const draft = state.full_draft || {};
  const job = draft.job || null;
  const running = Boolean(job && job.status === "running");
  const artifactsPending = Boolean(job && job.status === "artifacts_pending");
  const pending = Number(draft.pending_paragraphs || 0);
  const pendingArtifacts = Array.isArray(draft.pending_artifacts)
    ? draft.pending_artifacts
    : [];
  const pendingTitle = Boolean(draft.pending_title);
  const hasRemainingWork = pending > 0 || pendingArtifacts.length > 0 || pendingTitle;
  const total = Number(draft.total_paragraphs || 0);
  card.classList.toggle("is-running", running);
  card.classList.toggle("is-failed", Boolean(job && job.status === "failed"));
  card.classList.toggle("is-completed", Boolean(job && job.status === "completed"));
  card.classList.toggle("has-pending-artifacts", Boolean(job && job.status === "artifacts_pending"));

  const summary = $("full-draft-summary");
  if (job && job.progress_message) {
    summary.textContent = job.progress_message;
  } else if (!state.outline_confirmed) {
    summary.textContent = studioT("Please first confirm the outline; batch mode will not bypass paper structure confirmation.", "Confirm the outline first; batch drafting does not bypass structure approval.");
  } else if (!state.api_key_configured) {
    summary.textContent = studioT("Please configure LLM API Key as described at top of page.", "Configure the LLM API key using the instructions at the top of the page.");
  } else if (!pending && pendingArtifacts.length) {
    summary.textContent = `Complete the remaining real figures and tables: ${pendingArtifacts.join(", ")}.`;
  } else if (!pending && pendingTitle) {
    summary.textContent = "The manuscript is complete; generate and insert its final title.";
  } else if (!pending) {
    summary.textContent = studioT(`all ${total} Several paragraphs have been written in LaTeX; you can continue editing them paragraph by paragraph.`, `All ${total} paragraphs have been written to LaTeX and remain editable.`);
  } else {
    summary.textContent = state.online_project
      ? studioT(`Will be filled in according to project writing order. ${pending} / ${total} Some unfinished paragraphs; planned charts are kept as placeholders with captions and labels, accepted content will not be overwritten.`, `Draft ${pending} of ${total} unfinished paragraphs in project order. Planned figures and tables remain placeholders with captions and labels; accepted content will not be overwritten.`)
      : studioT(`Will be filled in according to project writing order. ${pending} / ${total} Some unfinished paragraphs and generate and insert all bound real charts; placeholders do not count as complete, accepted content will not be overwritten.`, `Draft ${pending} of ${total} unfinished paragraphs in project order, then generate and insert every bound real figure and table; placeholders do not count as complete, and accepted content will not be overwritten.`);
  }

  const start = $("full-draft-start");
  const cancel = $("full-draft-cancel");
  start.disabled = fullDraftRequestBusy || queuedFullDraftStart || running || artifactsPending || !draft.available || !hasRemainingWork;
  start.textContent = job && ["failed", "cancelled"].includes(job.status) && pending > 0
    ? "Continue completing the unfinished main text"
    : pending === 0 && pendingArtifacts.length
      ? "Continue generating figures and tables"
    : pending === 0 && pendingTitle
      ? "Generate final paper title"
    : pending === 0
      ? studioT("The full draft has been generated.", "Full first draft generated")
      : studioT("Directly generate the full draft.", "Generate full first draft");
  cancel.hidden = !running;
  cancel.disabled = fullDraftRequestBusy;

  const progressRow = $("full-draft-progress-row");
  progressRow.hidden = !job;
  $("full-draft-progress").value = Number((job && job.progress) || 0);
  $("full-draft-progress-text").textContent = job
    ? `${Number(job.completed || 0)} / ${Number(job.total || pending)} · ${job.progress_message || job.status}`
    : "";

  ["candidate", "comment", "generate", "section-draft-start", "accept", "paper-title", "title-gpt-prompt", "title-generate", "title-save", "model", "reset-generated"].forEach((id) => {
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
      ? "Currently combining approved paragraph structure working abstract and experimental results to generate the current paragraph."
      : "Modifying the current paragraph based on the comment.");
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
      if (automatic && $("candidate").dataset.dirty === "true") {
        renderSections();
        updateAcceptButton();
        showMessage("Backend candidate has been generated; the text you are editing remains, and Accept will use the content from the editing box.");
        return;
      }
      forgetProseDraft(`${requestedSection}:${requestedParagraph.id}`);
      forgetCommentDraft(`${requestedSection}:${requestedParagraph.id}`);
      $("candidate").dataset.dirty = "false";
      render();
      showMessage("Current paragraph has been generated; you may write comment edits or Accept. → LaTeX.");
    } else {
      renderSections();
      showMessage(`${state.sections[requestedSection].title} The current paragraph has been generated and saved.`);
    }
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    proseRequestBusy = false;
    setBusy(false);
    if (queuedSectionDraftStart) {
      const section = queuedSectionDraftStart;
      queuedSectionDraftStart = "";
      void startSectionDraftFromBrowser(section);
    } else if (queuedFullDraftStart) {
      queuedFullDraftStart = false;
      void startFullDraftFromBrowser();
    }
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
    $("candidate-label").textContent = "Manual edits of accepted version (not yet written).";
  }
  updateAcceptButton();
});

$("comment").addEventListener("input", (event) => {
  const paragraph = state.sections[activeSection].current_paragraph;
  if (paragraph) rememberCommentDraft(`${activeSection}:${paragraph.id}`, event.currentTarget.value);
});

async function applyWritingModel() {
  if (proseRequestBusy || fullDraftRequestBusy || titleBusy || modelApplyBusy) {
    return;
  }
  const requestedModel = $("model").value.trim();
  if (!requestedModel) {
    showMessage("Please enter the writing model name first.", true);
    updateModelApplyButton();
    return;
  }
  if (requestedModel === state.model) return;
  if (!confirm(`Switch to ${requestedModel}?This will reset all LLM chat history, but will not modify the already written body, figures, or PDF.`)) {
    return;
  }
  modelApplyBusy = true;
  try {
    setBusy(true, `Switching writing model to ${requestedModel}…`);
    const payload = await request("/api/llm-model", {
      method: "POST",
      body: JSON.stringify({model: requestedModel}),
    });
    state = payload.state;
    forgetTitleDraft("model");
    render();
    showMessage(`Writing model has been switched to ${state.model}; LLM Dialogue chain has been reset; written content remains unchanged.`);
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    modelApplyBusy = false;
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
  $("title-status").textContent = "Title has unsaved changes.";
  updateTitleSaveButton();
});

$("title-gpt-prompt").addEventListener("input", (event) => {
  event.currentTarget.dataset.dirty = "true";
  rememberTitleDraft("prompt", event.currentTarget.value, (state.title_editor || {}).prompt || "");
});

$("title-generate").onclick = async () => {
  if (titleBusy) return;
  const prompt = $("title-gpt-prompt").value.trim();
  try {
    setTitleBusy(true, "Generating title candidates; will not auto save…");
    const payload = await request("/api/title/generate", {
      method: "POST",
      body: JSON.stringify({
        prompt: prompt || "Generate one concise, specific academic title that reflects the paper's actual problem and contribution. Do not add unsupported claims.",
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
    setTitleBusy(true, "Writing LaTeX and compiling PDF.");
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
  setBusy(true, "Verifying latest paragraph status…");
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
      showMessage(`Current editing position updated to ${latestParagraph.id}, Please confirm before Accept.`, true);
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
      showMessage("The candidate has been updated in another round of generation; the latest version is auto-loaded; please review and Accept again.", true);
      return;
    }
    state = latestState;
    paragraph = latestParagraph;
    candidate = latestCandidate;
    const manualRevision = Boolean(
      paragraph
      && visibleCandidateText
      && visibleCandidateText !== visibleBaseText
    );
    if (!candidate && !manualRevision) {
      render();
      showMessage(
        latestParagraph && visibleParagraphId && latestParagraph.id !== visibleParagraphId
          ? `Current editing position updated to ${latestParagraph.id}, Please confirm before Accept.`
          : "The current paragraph has no acceptable body text.",
        true,
      );
      return;
    }
    const revisingAccepted = Boolean(paragraph.accepted_text);
    acceptedParagraphId = paragraph.id;
    setBusy(true, "Verifying citations; if missing will fetch online update BibTeX then write into LaTeX and compile.");
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
          ? `${acceptedParagraphId} The new version has replaced content in LaTeX and completed PDF compilation.`
          : state.sections[requestedSection].complete
          ? `${acceptedParagraphId} LaTeX compilation has been accepted and completed; the current section is finished.`
          : nextParagraph
          ? `${acceptedParagraphId} LaTeX compilation has been accepted and completed; preparing in the background. ${nextParagraph.id} Candidate.`
          : `${acceptedParagraphId} LaTeX compilation completed.`,
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
          `${acceptedParagraphId} Written and compiled; generating. ${nextParagraph.id}…`,
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
          ? `${acceptedParagraphId} The new version has replaced content in LaTeX and completed PDF compilation.`
          : state.sections[requestedSection].complete
          ? `${acceptedParagraphId} LaTeX compilation has been accepted and completed; the current section is finished.`
          : current
          ? `${acceptedParagraphId} LaTeX compilation completed;${current.id} Candidate refreshed.`
          : `${acceptedParagraphId} LaTeX compilation completed.`,
      );
    } else {
      renderSections();
      showMessage(`${state.sections[requestedSection].title} LaTeX compilation completed.`);
    }
  } catch (error) {
    if (acceptanceCompleted) {
      render();
      showMessage(
        `${acceptedParagraphId} LaTeX has been written and compiled, but generation of the next paragraph failed.${error.message}`,
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
    setBusy(true, "Compiling LaTeX…");
    const payload = await request("/api/compile", {method: "POST", body: "{}"});
    state = payload.state;
    showMessage("PDF Compilation succeeded.");
    renderPdf();
  } catch (error) {
    showMessage(error.message, true);
    try {
      await refresh();
    } catch (refreshError) {
      showMessage(`${error.message}\nStatus refresh also failed:${refreshError.message}`, true);
    }
  } finally {
    compileRequestBusy = false;
    setBusy(false);
  }
};

async function submitGeneratedReset(typed) {
  if (generatedResetBusy) return;
  const requestedModel = $("model").value.trim();
  const projectId = state && state.project && state.project.id;
  if (typed.trim() !== projectId) {
    $("reset-project-copy-status").textContent = "Project ID mismatch; no generated content was deleted.";
    $("reset-project-copy-status").classList.add("error");
    $("reset-project-confirm").focus();
    $("reset-project-confirm").select();
    return;
  }
  generatedResetBusy = true;
  $("reset-generated-dialog").close();
  try {
    setBusy(true, "Clearing generated content and compiling an empty shell PDF.");
    // Cancel old vector-page loads before the server removes generated page
    // caches and recompiles the empty shell. Otherwise an already queued
    // page-4 request can race the new one-page PDF and surface a noisy 400.
    $("pdf-pages").replaceChildren();
    $("pdf-pages").dataset.signature = "";
    $("pdf-navigation").replaceChildren();
    $("pdf-navigation").dataset.signature = "";
    $("pdf-viewer").hidden = true;
    $("pdf-download").hidden = true;
    updatePdfPageIndicator();
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
    showMessage("There is no paper project to clear currently.", true);
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
    ? "Project ID has been copied."
    : "Auto copy failed; the ID has been selected, please press Ctrl/Cmd+C.";
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
        available = sectionFigures();
      }
    }
    const selected = related
      ? available.find((artifact) => artifact.id === related.id)
      : null;
    const first = selected || available[0];
    if (first) activeFigure = first.id;
  }
  render();
}

$("writing-view").onclick = () => switchView("writing");
async function startFullDraftFromBrowser() {
  if (fullDraftRequestBusy || queuedFullDraftStart) return;
  if (proseRequestBusy) {
    queuedFullDraftStart = true;
    renderFullDraft();
    showMessage("After the current paragraph generation completes, automatically start the full manuscript draft task…");
    return;
  }
  fullDraftRequestBusy = true;
  $("full-draft-start").disabled = true;
  try {
    const payload = await request("/api/full-draft/start", {
      method: "POST",
      body: JSON.stringify({model: $("model").value.trim()}),
    });
    state = payload.state;
    render();
    showMessage("The full draft task has started; you can switch pages to view progress, and you can continue to modify section by section after completion.");
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    fullDraftRequestBusy = false;
    renderFullDraft();
  }
}
$("full-draft-start").onclick = () => startFullDraftFromBrowser();
async function startSectionDraftFromBrowser(section = activeSection) {
  if (fullDraftRequestBusy || queuedSectionDraftStart) return;
  const requestedSection = section;
  if (proseRequestBusy) {
    queuedSectionDraftStart = requestedSection;
    render();
    showMessage(`${state.sections[requestedSection].title} Queued; once the current paragraph generation is complete, the entire section generation will automatically start.`);
    return;
  }
  fullDraftRequestBusy = true;
  $("section-draft-start").disabled = true;
  try {
    const payload = await request("/api/section-draft/start", {
      method: "POST",
      body: JSON.stringify({
        model: $("model").value.trim(),
        section: requestedSection,
      }),
    });
    state = payload.state;
    render();
    showMessage(`${state.sections[requestedSection].title} The entire section generation task has started; LaTeX will be written and compiled automatically in paragraph order.`);
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    fullDraftRequestBusy = false;
    render();
  }
}
$("section-draft-start").onclick = () => startSectionDraftFromBrowser();
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
    showMessage("Stop requested; completed paragraphs are retained, and unfinished body text can be completed later.");
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
      $("figure-message").textContent = payload.message || "Done.";
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
    const current = selectedFigure();
    if (current && activeView === "figures" && current.kind === "data") {
      setTimeout(() => scheduleAutomaticDataPanel(current), 0);
    } else if (current && activeView === "tables" && current.kind === "table") {
      setTimeout(() => scheduleAutomaticTableGenerate(current), 0);
    }
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
    const current = selectedFigure();
    if (current && activeView === "figures" && current.kind === "data") {
      setTimeout(() => scheduleAutomaticDataPanel(current), 0);
    } else if (current && activeView === "tables" && current.kind === "table") {
      setTimeout(() => scheduleAutomaticTableGenerate(current), 0);
    }
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
  "Starting GPT drawing prompt task…",
);

$("figure-draw").onclick = () => startFigureJob(
  "/api/figure/draw",
  {figure_id: activeFigure, draw_prompt: $("draw-prompt").value},
  "Checking if the Prompt has changed…",
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
  $("figure-message").textContent = "Stopping this Codex drawing task…";
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
  "Starting local Agent and reconstructing original PowerPoint shapes according to the sketch.",
);

$("mechanism-preview-toggle").onclick = () => {
  const figure = selectedFigure();
  if (
    !figure
    || figure.status === "approved"
    || !figure.gpt_preview_url
    || !figure.paper_preview_url
  ) return;
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
          layout_mode: $("figure-layout-mode").value,
        }
      : {
          figure_id: activeFigure,
          placement_after: $("figure-placement").value,
          layout_mode: $("figure-layout-mode").value,
        },
    figure && figure.kind === "table"
      ? "Updating table position and single column or double column layout, and recompiling PDF…"
      : "Updating figure locations and layout settings…",
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
      ? "Caption Modified, not yet updated in the main text and PDF."
      : "Caption Modified, not yet saved")
    : (figure && figure.status === "approved"
      ? "Caption Written into main text and PDF"
      : "The current main text will use this caption.");
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
    button.textContent = "GPT Generating Caption…";
    $("figure-caption-status").textContent = "Generating Caption candidate.";
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
      ? "GPT candidate Not saved yet"
      : "GPT candidate Same as the current caption.";
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
      $("figure-message").textContent = payload.message || "Caption Saved.";
      $("figure-message").classList.remove("error");
    }
    return true;
  } catch (error) {
    if (selectedFigure() && selectedFigure().id === requestedFigureId) {
      $("figure-caption-status").textContent = `Caption Save failed:${error.message}`;
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
    "Inserting the body text, adding Figure references, and recompiling the PDF.",
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
  "Starting local Agent and reconstructing original PowerPoint shapes according to the sketch.",
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
  status.textContent = "Security update in progress…";
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
  "Starting local Agent to generate the initial draft table from traceable results…",
);

$("table-agent-edit").onclick = () => startFigureJob(
  "/api/table/agent-edit",
  {
    table_id: activeFigure,
    latex: $("table-latex").value,
    agent_prompt: $("table-agent-prompt").value,
  },
  "Starting local Codex agent to modify the table.",
);

$("table-save").onclick = () => runFigureAction(
  "/api/table/save",
  {table_id: activeFigure, latex: $("table-latex").value},
  "Saving table edits…",
);

$("table-approve").onclick = () => runFigureAction(
  "/api/table/approve",
  {table_id: activeFigure, latex: $("table-latex").value},
  "Inserting main text and recompiling PDF…",
);

refresh().catch((error) => {
  $("section-title").textContent = "Loading failed";
  $("runtime-connection").textContent = "Disconnected";
  $("runtime-connection").className = "disconnected";
  $("load-error-message").textContent = error.message;
  $("load-error").hidden = false;
  [
    "model", "model-apply", "reset-generated", "writing-view",
    "figures-view", "tables-view", "compile", "section-draft-start",
    "full-draft-start", "full-draft-cancel", "runtime-key-open",
  ].forEach((id) => {
    const control = $(id);
    if (control) control.disabled = true;
  });
  $("writing-workspace").hidden = true;
  $("figures-workspace").hidden = true;
});
