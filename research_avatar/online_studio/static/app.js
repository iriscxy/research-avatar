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
  ['邮箱或密码不正确。', 'Incorrect email or password.'],
  ['该邮箱已经注册，请直接登录。', 'This email is already registered. Sign in instead.'],
  ['请输入有效的邮箱地址。', 'Enter a valid email address.'],
  ['密码必须为 6–1024 个字符。', 'The password must contain 6–1024 characters.'],
  ['正在校验上传文件…', 'Validating uploaded files…'],
  ['正在解析当前工作说明和结构参考论文…', 'Parsing the project brief and structural reference paper…'],
  ['正在提取并由 DeepSeek 整理结构参考论文 PDF…', 'DeepSeek is reading and structuring the reference-paper PDF…'],
  ['正在分析目标项目的研究类型与图表需求…', 'Analyzing the project type and planned artifacts…'],
  ['正在建立实验部分仅规划的写作边界…', 'Defining the planning-only boundary for experiments…'],
  ['正在分析 ref paper，并为目标论文逐段匹配写作结构…', 'Analyzing the reference paper and mapping its writing structure paragraph by paragraph…'],
  ['逐段映射已完成，正在生成 Paper Studio 项目…', 'Paragraph mapping is complete; generating the Paper Studio project…'],
  ['项目文件已生成，正在启动 Paper Studio 服务…', 'Project files are ready; starting Paper Studio…'],
  ['正在启动 Paper Studio 服务…', 'Starting Paper Studio…'],
  ['Paper Studio 已就绪，正在打开…', 'Paper Studio is ready; opening it…'],
  ['Paper Studio 写作进程启动失败，请检查服务端依赖。', 'Paper Studio failed to start. Check the server dependencies.'],
  ['Paper Studio 写作进程启动超时。', 'Paper Studio startup timed out.'],
  ['当前在线写作会话已满，请稍后重试。', 'All online writing slots are busy. Try again later.'],
]);

function translateOnlineMessage(value) {
  const source = String(value || '');
  if (uiLanguage !== 'en') return source;
  const exact = onlineMessageTranslations.get(source);
  if (exact) return exact;
  const labels = {
    '结构参考论文': 'The structural reference paper',
    '当前工作说明': 'The project brief',
  };
  return source
    .replace(/^请上传一个当前工作说明文档。$/, 'Upload one project-brief document.')
    .replace(/^请上传一篇完整的结构参考论文。$/, 'Upload one complete structural reference paper.')
    .replace(/^请上传(.+)。$/, (_, label) => `Upload ${labels[label] || label}.`)
    .replace(/^(.+)必须使用名称唯一的 DOC、DOCX、TXT、PDF、Markdown、JSON 或 HTML 文件。$/, (_, label) => `${labels[label] || label} must be a uniquely named DOC, DOCX, TXT, PDF, Markdown, JSON, or HTML file.`)
    .replace(/^(.+)一次最多上传 (\d+) 个文件。$/, (_, label, count) => `Upload no more than ${count} files for ${labels[label] || label}.`)
    .replace(/^(.+)上传格式无效。$/, (_, label) => `The upload format for ${labels[label] || label} is invalid.`)
    .replace(/^不支持的文档格式：(.+)。$/, 'Unsupported document format: $1.')
    .replace(/^(.+) 不是有效的上传内容。$/, '$1 is not valid upload content.')
    .replace(/^(.+) 必须非空且不超过 8 MB。$/, '$1 must be nonempty and no larger than 8 MB.')
    .replace(/^(.+) 没有可用于写作的文本。$/, '$1 contains no usable writing text.')
    .replace(/^(.+) 没有足够的可提取文本；当前不支持纯扫描 PDF。$/, '$1 does not contain enough extractable text; scanned-only PDFs are not supported.')
    .replace(/^服务器缺少 PDF 文本提取工具 pdftotext。$/, 'The server is missing the pdftotext dependency.')
    .replace(/^提取 (.+) 的页面文本时超时。$/, 'Timed out while extracting page text from $1.')
    .replace(/^LLM 读取 (.+) 时 API 连接失败：(.+)$/, 'The LLM API failed while reading $1: $2')
    .replace(/^LLM 读取 (.+) 时返回了无效 JSON。$/, 'The LLM returned invalid JSON while reading $1.')
    .replace(/^写作结构服务返回了无法读取的数据，请重试。$/, 'The writing-structure service returned unreadable data. Try again.')
    .replace(/^服务端尚未配置共享 DeepSeek API key，请联系管理员。$/, 'The shared DeepSeek API key is not configured. Contact the administrator.');
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
      authenticatedUser.email + ' · ' + (authenticatedUser.provider === 'google' ? 'Google' : localized('邮箱账户', 'Email account'));
  }
}

function setInterfaceLanguage(language) {
  uiLanguage = language === 'en' ? 'en' : 'zh';
  window.localStorage.setItem('research-avatar-language', uiLanguage);
  applyInterfaceLanguage();
  const demoFrame = document.querySelector('#demo-frame');
  if (demoFrame.src !== 'about:blank') demoFrame.src = `/demo/?lang=${uiLanguage}&authenticated=${Date.now()}`;
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
    sessionNotice.textContent = localized('上一次临时写作会话已结束。请在“免费纯文字 PaperWrite 版”重新开始一个写作会话。', 'Your previous temporary writing session has ended. Start a new session from Free text-only PaperWrite.');
    sessionNotice.classList.remove('hidden');
  } else if (loginRequired && !authenticated) {
    authMessage.className = 'error';
    authMessage.textContent = localized('请先登录，再打开 Paper Studio。', 'Sign in before opening Paper Studio.');
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
  demoFrame.src = `/demo/?lang=${uiLanguage}&authenticated=${Date.now()}`;
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
          sessionNotice.textContent = localized('当前写作会话已连续 4 小时未使用，临时内容已自动清空。请重新上传材料。', 'This writing session was inactive for four hours and its temporary content was cleared. Upload your materials again.');
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
      authMessage.textContent = localized('Google 登录失败或已过期，请重试。', 'Google sign-in failed or expired. Try again.');
    }
  } catch (_) {
    authMessage.className = 'error';
    authMessage.textContent = localized('暂时无法检查登录状态。', 'Unable to check sign-in status right now.');
  }
}

authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const action = event.submitter?.dataset.action || 'login';
  authMessage.className = '';
  authMessage.textContent = action === 'signup' ? localized('正在创建账户…', 'Creating account…') : localized('正在登录…', 'Signing in…');
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
    if (!response.ok || !result.ok) throw new Error(translateOnlineMessage(result.error) || localized('登录失败。', 'Sign-in failed.'));
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
  if (!response.ok || !result.ok) throw new Error(translateOnlineMessage(result.error) || localized('创建会话失败。', 'Failed to create the session.'));
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
      if (!poll.ok || !result.ok) throw new Error(translateOnlineMessage(result.error) || localized('初始化失败。', 'Initialization failed.'));
      const elapsed = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
      const rawProgressMessage = result.message || '正在初始化…';
      const progressMessage = translateOnlineMessage(rawProgressMessage);
      const estimate = rawProgressMessage.includes('DeepSeek 整理结构参考论文 PDF')
        ? localized('（预计 2–3 min）', ' (estimated 2–3 min)')
        : '';
      message.textContent = `${progressMessage} · ${Number(result.progress || 0)}% · ${localized(`已等待 ${elapsed} 秒`, `elapsed ${elapsed}s`)}${estimate}`;
      if (elapsed > 600) throw new Error(localized('初始化超过 10 分钟，请重试。', 'Initialization exceeded 10 minutes. Try again.'));
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
  resetMessage.textContent = localized('正在清空…', 'Clearing…');
  try {
    const response = await fetch('/api/online/session/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(translateOnlineMessage(result.error) || localized('清空失败。', 'Failed to clear the session.'));
    showUploadView();
    message.className = '';
    message.textContent = localized('当前写作内容已清空，请重新上传材料。', 'The current writing content was cleared. Upload your materials again.');
  } catch (error) {
    resetMessage.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  message.className = '';
  message.textContent = localized('正在读取资料并启动写作台…', 'Reading materials and starting Paper Studio…');
  submit.disabled = true;
  try {
    const elements = form.elements;
    const projectBriefFile = elements.project_brief_file.files[0];
    const referencePaperFile = elements.reference_paper_file.files[0];
    if (!projectBriefFile) throw new Error(localized('请上传当前工作说明。', 'Upload the project brief.'));
    if (!referencePaperFile) throw new Error(localized('请上传一篇完整的结构参考论文。', 'Upload one complete structural reference paper.'));
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
