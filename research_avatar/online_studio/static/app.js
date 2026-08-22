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

function showStudioInUseTab() {
  if (!activeStudioSession) return;
  useOnboarding.classList.add('hidden');
  sessionActions.classList.add('hidden');
  document.querySelector('#use-panel').classList.add('studio-active');
  studioFrame.classList.remove('hidden');
  if (studioFrame.getAttribute('src') !== '/studio') studioFrame.src = '/studio';
}

function showNavigationNotice(authenticated) {
  const url = new URL(window.location.href);
  const expired = url.searchParams.get('session_expired') === '1';
  const loginRequired = url.searchParams.get('login_required') === '1';
  if (expired && authenticated) {
    sessionNotice.textContent = '上一次临时写作会话已结束。请在“免费纯文字 PaperWrite 版”重新开始一个写作会话。';
    sessionNotice.classList.remove('hidden');
  } else if (loginRequired && !authenticated) {
    authMessage.className = 'error';
    authMessage.textContent = '请先登录，再打开 Paper Studio。';
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
  if (panelId === 'use-panel') showStudioInUseTab();
}

document.querySelectorAll('.product-tab').forEach((tab) => {
  tab.addEventListener('click', () => selectProductPanel(tab.dataset.panel));
});

async function showAuthenticated(user) {
  // The landing page always shows Demo/the free text-only PaperWrite tab
  // first, even for a researcher with an active writing session -- it used to
  // auto-redirect straight into /studio here, which meant the site's own
  // root URL could never actually be used to reach the landing-page shell
  // once you had a session going. The "继续当前写作会话" resume link
  // inside the PaperWrite tab (#session-actions) is how you get back into an
  // active session now; it's an explicit choice, not automatic.
  document.body.classList.add('workspace-authenticated');
  authCard.classList.add('hidden');
  workspaceShell.classList.remove('hidden');
  showNavigationNotice(true);
  const requestedPanel = new URLSearchParams(window.location.search).get('open') === 'use'
    ? 'use-panel'
    : 'demo-panel';
  selectProductPanel(requestedPanel);
  const demoFrame = document.querySelector('#demo-frame');
  demoFrame.src = '/demo/?authenticated=' + Date.now();
  document.querySelector('#account-label').textContent =
    user.email + ' · ' + (user.provider === 'google' ? 'Google' : '邮箱账户');
  sessionActions.classList.add('hidden');
  try {
    const response = await fetch('/api/online/session', { cache: 'no-store' });
    const state = await response.json();
    activeStudioSession = Boolean(state.active);
    if (activeStudioSession) {
      sessionActions.classList.remove('hidden');
      if (!document.querySelector('#use-panel').classList.contains('hidden')) {
        showStudioInUseTab();
      }
    }
  } catch (_) {
    // Leave the resume link hidden if the check fails.
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
      authMessage.textContent = 'Google 登录失败或已过期，请重试。';
    }
  } catch (_) {
    authMessage.className = 'error';
    authMessage.textContent = '暂时无法检查登录状态。';
  }
}

authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const action = event.submitter?.dataset.action || 'login';
  authMessage.className = '';
  authMessage.textContent = action === 'signup' ? '正在创建账户…' : '正在登录…';
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
    if (!response.ok || !result.ok) throw new Error(result.error || '登录失败。');
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
  if (!response.ok || !result.ok) throw new Error(result.error || '创建会话失败。');
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
      if (!poll.ok || !result.ok) throw new Error(result.error || '初始化失败。');
      const elapsed = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
      const progressMessage = result.message || '正在初始化…';
      const estimate = progressMessage.includes('DeepSeek 整理结构参考论文 PDF')
        ? '（预计 2–3 min）'
        : '';
      message.textContent = `${progressMessage} · ${Number(result.progress || 0)}% · 已等待 ${elapsed} 秒${estimate}`;
      if (elapsed > 600) throw new Error('初始化超过 10 分钟，请重试。');
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

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  message.className = '';
  message.textContent = '正在读取资料并启动写作台…';
  submit.disabled = true;
  try {
    const elements = form.elements;
    const projectBriefFile = elements.project_brief_file.files[0];
    const referencePaperFile = elements.reference_paper_file.files[0];
    if (!projectBriefFile) throw new Error('请上传当前工作说明。');
    if (!referencePaperFile) throw new Error('请上传一篇完整的结构参考论文。');
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
