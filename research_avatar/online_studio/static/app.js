const languageSelect = document.querySelector('#language-select');
const initialLanguage = new URLSearchParams(window.location.search).get('lang')
  || window.localStorage.getItem('research-avatar-language')
  || 'zh';
let uiLanguage = initialLanguage === 'en' ? 'en' : 'zh';
let authenticatedUser = null;

function localized(zh, en) {
  return uiLanguage === 'en' ? en : zh;
}

const onlineMessageTranslations = new Map([
  ['Email or password is incorrect.', 'Incorrect email or password.'],
  ['This email address is already registered; please log in directly.', 'This email is already registered. Sign in instead.'],
  ['Please enter a valid email address.', 'Enter a valid email address.'],
  ['Password must be 6–1024 characters.', 'The password must contain 6–1024 characters.'],
  ['Validating uploaded file…', 'Validating uploaded files…'],
  ['Parsing the current work description and structure reference paper…', 'Parsing the project brief and structural reference paper…'],
  ['Extracting and organizing the structure reference paper PDFs with DeepSeek.', 'DeepSeek is reading and structuring the reference-paper PDF…'],
  ['Analyzing the research type and chart requirements of the target project.', 'Analyzing the project type and planned artifacts…'],
  ['Establishing writing boundaries for the experimental section only…', 'Defining the planning-only boundary for experiments…'],
  ['Analyzing the reference paper and matching the writing structure paragraph by paragraph for the target paper.', 'Analyzing the reference paper and mapping its writing structure paragraph by paragraph…'],
  ['Paragraph by paragraph mapping is complete; generating Paper Studio project.', 'Paragraph mapping is complete; generating the Paper Studio project…'],
  ['Project files generated; starting Paper Studio service.', 'Project files are ready; starting Paper Studio…'],
  ['Starting Paper Studio service…', 'Starting Paper Studio…'],
  ['Paper Studio Ready, opening now…', 'Paper Studio is ready; opening it…'],
  ['Paper Studio Writing process startup failed; please check server dependencies.', 'Paper Studio failed to start. Check the server dependencies.'],
  ['Paper Studio Writing process startup timed out.', 'Paper Studio startup timed out.'],
  ['Current online writing session is full; please try again later.', 'All online writing slots are busy. Try again later.'],
]);

function translateOnlineMessage(value) {
  const source = String(value || '');
  if (uiLanguage !== 'en') return source;
  const exact = onlineMessageTranslations.get(source);
  if (exact) return exact;
  const labels = {
    'Structure reference paper': 'The structural reference paper',
    'Current work description': 'The project brief',
  };
  return source
    .replace(/^Please upload the current work specification document.$/, 'Upload one project-brief document.')
    .replace(/^Please upload a complete structure reference paper.$/, 'Upload one complete structural reference paper.')
    .replace(/^Please upload(.+).$/, (_, label) => `Upload ${labels[label] || label}.`)
    .replace(/^(.+)Must use uniquely named DOC DOCX TXT PDF Markdown JSON or HTML files.$/, (_, label) => `${labels[label] || label} must be a uniquely named DOC, DOCX, TXT, PDF, Markdown, JSON, or HTML file.`)
    .replace(/^(.+)Up to one upload at a time. (\d+) Files.$/, (_, label, count) => `Upload no more than ${count} files for ${labels[label] || label}.`)
    .replace(/^(.+)Invalid upload format.$/, (_, label) => `The upload format for ${labels[label] || label} is invalid.`)
    .replace(/^Unsupported document format:(.+).$/, 'Unsupported document format: $1.')
    .replace(/^(.+) Not valid upload content.$/, '$1 is not valid upload content.')
    .replace(/^(.+) Must be non-empty and not exceed 8 MB.$/, '$1 must be nonempty and no larger than 8 MB.')
    .replace(/^(.+) No text available for writing.$/, '$1 contains no usable writing text.')
    .replace(/^(.+) Not enough extractable text; current does not support pure scanned PDF.$/, '$1 does not contain enough extractable text; scanned-only PDFs are not supported.')
    .replace(/^Server lacks PDF text extraction tool pdftotext.$/, 'The server is missing the pdftotext dependency.')
    .replace(/^extract (.+) Timed out loading the page text.$/, 'Timed out while extracting page text from $1.')
    .replace(/^LLM read (.+) When API connection fails:(.+)$/, 'The LLM API failed while reading $1: $2')
    .replace(/^LLM read (.+) Invalid JSON was returned.$/, 'The LLM returned invalid JSON while reading $1.')
    .replace(/^The writing structure service returned unreadable data; please retry.$/, 'The writing-structure service returned unreadable data. Try again.')
    .replace(/^Server side has not configured the shared DeepSeek API key; please contact the administrator.$/, 'The shared DeepSeek API key is not configured. Contact the administrator.');
}

function applyInterfaceLanguage() {
  document.documentElement.lang = uiLanguage === 'en' ? 'en' : 'zh-CN';
  languageSelect.value = uiLanguage;
  document.querySelectorAll('[data-zh][data-en]').forEach((node) => {
    node.textContent = node.dataset[uiLanguage];
  });
  document.querySelectorAll('[data-placeholder-zh][data-placeholder-en]').forEach((node) => {
    node.placeholder = node.dataset[`placeholder${uiLanguage === 'en' ? 'En' : 'Zh'}`];
  });
  if (authenticatedUser) {
    document.querySelector('#account-label').textContent =
      authenticatedUser.email + ' · ' + (authenticatedUser.provider === 'google' ? 'Google' : localized('Email account', 'Email account'));
  }
}

function setInterfaceLanguage(language) {
  uiLanguage = language === 'en' ? 'en' : 'zh';
  window.localStorage.setItem('research-avatar-language', uiLanguage);
  applyInterfaceLanguage();
  const demoFrame = document.querySelector('#demo-frame');
  if (demoFrame.src !== 'about:blank') demoFrame.src = `/demo/?lang=${uiLanguage}&embedded=1&authenticated=${Date.now()}`;
  if (studioIsOpen) studioFrame.src = `/studio?lang=${uiLanguage}`;
}

languageSelect.addEventListener('change', () => {
  setInterfaceLanguage(languageSelect.value);
});

window.addEventListener('message', (event) => {
  if (event.origin !== window.location.origin) return;
  if (event.data?.type !== 'research-avatar-language') return;
  const language = event.data.language === 'en' ? 'en' : 'zh';
  if (language === uiLanguage) return;
  setInterfaceLanguage(language);
});

const form = document.querySelector('#setup-form');
const message = document.querySelector('#message');
const submit = document.querySelector('#submit');
const authCard = document.querySelector('#auth-card');
const authForm = document.querySelector('#auth-form');
const authMessage = document.querySelector('#auth-message');
const workspaceShell = document.querySelector('#workspace-shell');
const sessionNotice = document.querySelector('#session-notice');
const studioFrame = document.querySelector('#studio-frame');
const useOnboarding = document.querySelector('#use-onboarding');
const sessionActions = document.querySelector('#session-actions');
let activeStudioSession = false;
let studioIsOpen = false;
let sessionMonitor = null;

function showSessionChoice() {
  if (!activeStudioSession) return;
  studioIsOpen = false;
  useOnboarding.classList.add('hidden');
  studioFrame.classList.add('hidden');
  studioFrame.src = 'about:blank';
  document.querySelector('#use-panel').classList.remove('studio-active');
  sessionActions.classList.remove('hidden');
  document.querySelector('#resume-studio').classList.remove('hidden');
}

function showUploadView() {
  activeStudioSession = false;
  studioIsOpen = false;
  document.querySelector('#use-panel').classList.remove('studio-active');
  studioFrame.classList.add('hidden');
  studioFrame.src = 'about:blank';
  sessionActions.classList.add('hidden');
  document.querySelector('#resume-studio').classList.remove('hidden');
  useOnboarding.classList.remove('hidden');
  form.reset();
  submit.disabled = false;
}

function showStudioInUseTab() {
  if (!activeStudioSession) return;
  studioIsOpen = true;
  useOnboarding.classList.add('hidden');
  sessionActions.classList.remove('hidden');
  document.querySelector('#resume-studio').classList.add('hidden');
  document.querySelector('#use-panel').classList.add('studio-active');
  studioFrame.classList.remove('hidden');
  const studioUrl = `/studio?lang=${uiLanguage}`;
  if (studioFrame.getAttribute('src') !== studioUrl) studioFrame.src = studioUrl;
}

function showNavigationNotice(authenticated) {
  const url = new URL(window.location.href);
  const expired = url.searchParams.get('session_expired') === '1';
  const loginRequired = url.searchParams.get('login_required') === '1';
  if (expired && authenticated) {
    sessionNotice.textContent = localized('The last temporary writing session has ended. Please start a new writing session in the free plain text PaperWrite version.', 'Your previous temporary writing session has ended. Start a new session from Free text-only PaperWrite.');
    sessionNotice.classList.remove('hidden');
  } else if (loginRequired && !authenticated) {
    authMessage.className = 'error';
    authMessage.textContent = localized('Please log in first, then open Paper Studio.', 'Sign in before opening Paper Studio.');
  }
  if (expired || loginRequired) {
    url.searchParams.delete('session_expired');
    url.searchParams.delete('login_required');
    window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
  }
}

function selectProductPanel(panelId) {
  document.querySelectorAll('.product-panel').forEach((panel) => {
    panel.classList.toggle('hidden', panel.id !== panelId);
  });
  document.querySelectorAll('.product-tab').forEach((tab) => {
    const active = tab.dataset.panel === panelId;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', String(active));
  });
  if (panelId === 'use-panel' && activeStudioSession && !studioIsOpen) {
    showSessionChoice();
  }
}

document.querySelectorAll('.product-tab').forEach((tab) => {
  tab.addEventListener('click', () => selectProductPanel(tab.dataset.panel));
});

async function showAuthenticated(user) {
  // The landing page always shows Demo/the free text-only PaperWrite tab
  // first, even for a researcher with an active writing session -- it used to
  // auto-redirect straight into /studio here, which meant the site's own
  // root URL could never actually be used to reach the landing-page shell
  // once you had a session going. The resume-current-session link
  // inside the PaperWrite tab (#session-actions) is how you get back into an
  // active session now; it's an explicit choice, not automatic.
  authenticatedUser = user;
  document.body.classList.add('workspace-authenticated');
  authCard.classList.add('hidden');
  document.querySelector('#account-bar').classList.remove('hidden');
  workspaceShell.classList.remove('hidden');
  showNavigationNotice(true);
  const requestedPanel = new URLSearchParams(window.location.search).get('open') === 'use'
    ? 'use-panel'
    : 'demo-panel';
  selectProductPanel(requestedPanel);
  const demoFrame = document.querySelector('#demo-frame');
  demoFrame.src = `/demo/?lang=${uiLanguage}&embedded=1&authenticated=${Date.now()}`;
  applyInterfaceLanguage();
  sessionActions.classList.add('hidden');
  try {
    const response = await fetch('/api/online/session', { cache: 'no-store' });
    const state = await response.json();
    activeStudioSession = Boolean(state.active);
    if (activeStudioSession) {
      if (!document.querySelector('#use-panel').classList.contains('hidden')) {
        showSessionChoice();
      }
    }
  } catch (_) {
    // Leave the resume link hidden if the check fails.
  }
  if (sessionMonitor === null) {
    sessionMonitor = window.setInterval(async () => {
      if (!activeStudioSession) return;
      try {
        const response = await fetch('/api/online/session', { cache: 'no-store' });
        const state = await response.json();
        if (response.ok && !state.active) {
          showUploadView();
          sessionNotice.textContent = localized('The current writing session has been idle for four hours; temporary content has been automatically cleared. Please re-upload materials.', 'This writing session was inactive for four hours and its temporary content was cleared. Upload your materials again.');
          sessionNotice.classList.remove('hidden');
        }
      } catch (_) {
        // A transient network error must not discard the browser view.
      }
    }, 30000);
  }
}

async function initializeAuth() {
  try {
    const response = await fetch('/api/auth/session', { cache: 'no-store' });
    const state = await response.json();
    document.querySelector('#google-login').classList.toggle(
      'hidden',
      !state.google_configured,
    );
    if (state.authenticated) {
      await showAuthenticated(state.user);
      return;
    }
    showNavigationNotice(false);
    const params = new URLSearchParams(window.location.search);
    if (params.get('auth_error') === 'google') {
      authMessage.className = 'error';
      authMessage.textContent = localized('Google Login failed or expired. Please retry.', 'Google sign-in failed or expired. Try again.');
    }
  } catch (_) {
    authMessage.className = 'error';
    authMessage.textContent = localized('Cannot verify login status at the moment.', 'Unable to check sign-in status right now.');
  }
}

authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const action = event.submitter?.dataset.action || 'login';
  authMessage.className = '';
  authMessage.textContent = action === 'signup' ? localized('Creating account…', 'Creating account…') : localized('Logging in…', 'Signing in…');
  const buttons = authForm.querySelectorAll('button');
  buttons.forEach((button) => { button.disabled = true; });
  try {
    const response = await fetch('/api/auth/' + action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: authForm.elements.email.value,
        password: authForm.elements.password.value,
      }),
    });
    authForm.elements.password.value = '';
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(translateOnlineMessage(result.error) || localized('Login failed.', 'Sign-in failed.'));
    await showAuthenticated(result.user);
  } catch (error) {
    authMessage.className = 'error';
    authMessage.textContent = error.message;
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
});

document.querySelector('#logout').addEventListener('click', async () => {
  await fetch('/api/auth/logout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  });
  window.location.assign('/');
});

applyInterfaceLanguage();
initializeAuth();

async function encodeFile(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  const chunk = 0x8000;
  for (let index = 0; index < bytes.length; index += chunk) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
  }
  return { name: file.name, data: btoa(binary) };
}

async function startSession(payload) {
  const response = await fetch('/api/online/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  let result = await response.json();
  if (!response.ok || !result.ok) throw new Error(translateOnlineMessage(result.error) || localized('Failed to create session.', 'Failed to create the session.'));
  if (result.pending && result.job_id) {
    const jobId = result.job_id;
    const startedAt = Date.now();
    while (!result.ready) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const poll = await fetch(
        `/api/online/session/job?job_id=${encodeURIComponent(jobId)}`,
        { cache: 'no-store' },
      );
      result = await poll.json();
      if (!poll.ok || !result.ok) throw new Error(translateOnlineMessage(result.error) || localized('Initialization failed.', 'Initialization failed.'));
      const elapsed = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
      const rawProgressMessage = result.message || 'Initializing…';
      const progressMessage = translateOnlineMessage(rawProgressMessage);
      const estimate = rawProgressMessage.includes('DeepSeek Organize the structure reference paper PDF.')
        ? localized('(Estimated 2–3 min', ' (estimated 2–3 min)')
        : '';
      message.textContent = `${progressMessage} · ${Number(result.progress || 0)}% · ${localized(`Waiting ${elapsed} seconds`, `elapsed ${elapsed}s`)}${estimate}`;
      if (elapsed > 600) throw new Error(localized('Initialization exceeded 10 minutes; please retry.', 'Initialization exceeded 10 minutes. Try again.'));
    }
  }
  activeStudioSession = true;
  selectProductPanel('use-panel');
  showStudioInUseTab();
}

document.querySelector('#resume-studio').addEventListener('click', () => {
  activeStudioSession = true;
  showStudioInUseTab();
});

document.querySelector('#reset-studio').addEventListener('click', async (event) => {
  const button = event.currentTarget;
  const resetMessage = document.querySelector('#reset-message');
  button.disabled = true;
  resetMessage.textContent = localized('Clearing…', 'Clearing…');
  try {
    const response = await fetch('/api/online/session/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(translateOnlineMessage(result.error) || localized('Clearing failed.', 'Failed to clear the session.'));
    showUploadView();
    message.className = '';
    message.textContent = localized('Current writing content has been cleared; please re-upload materials.', 'The current writing content was cleared. Upload your materials again.');
  } catch (error) {
    resetMessage.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  message.className = '';
  message.textContent = localized('Reading data and starting writing workspace…', 'Reading materials and starting Paper Studio…');
  submit.disabled = true;
  try {
    const elements = form.elements;
    const projectBriefFile = elements.project_brief_file.files[0];
    const referencePaperFile = elements.reference_paper_file.files[0];
    if (!projectBriefFile) throw new Error(localized('Please upload the current work description.', 'Upload the project brief.'));
    if (!referencePaperFile) throw new Error(localized('Please upload a complete structure reference paper.', 'Upload one complete structural reference paper.'));
    await startSession({
      mode: 'materials',
      venue: elements.venue.value,
      project_brief_files: [await encodeFile(projectBriefFile)],
      reference_paper_files: [await encodeFile(referencePaperFile)],
    });
  } catch (error) {
    message.className = 'error';
    message.textContent = error.message;
    submit.disabled = false;
  }
});
