const form = document.querySelector('#setup-form');
const message = document.querySelector('#message');
const submit = document.querySelector('#submit');
const authCard = document.querySelector('#auth-card');
const authForm = document.querySelector('#auth-form');
const authMessage = document.querySelector('#auth-message');
const workspaceShell = document.querySelector('#workspace-shell');
const sessionNotice = document.querySelector('#session-notice');
const lightweightForm = document.querySelector('#lightweight-form');
const lightweightMessage = document.querySelector('#lightweight-message');
const lightweightSubmit = document.querySelector('#lightweight-submit');

function showNavigationNotice(authenticated) {
  const url = new URL(window.location.href);
  const expired = url.searchParams.get('session_expired') === '1';
  const loginRequired = url.searchParams.get('login_required') === '1';
  if (expired && authenticated) {
    sessionNotice.textContent = '上一次临时写作会话已结束。请在 Use it 重新开始一个写作会话。';
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
}

document.querySelectorAll('.product-tab').forEach((tab) => {
  tab.addEventListener('click', () => selectProductPanel(tab.dataset.panel));
});

async function showAuthenticated(user) {
  // The landing page always shows Demo/Use it first, even for a
  // researcher with an active "Use it" writing session -- it used to
  // auto-redirect straight into /studio here, which meant the site's own
  // root URL could never actually be used to reach the Demo/Use it shell
  // once you had a session going. The "继续当前写作会话" resume link
  // inside the Use it tab (#session-actions) is how you get back into an
  // active session now; it's an explicit choice, not automatic.
  document.body.classList.add('workspace-authenticated');
  authCard.classList.add('hidden');
  workspaceShell.classList.remove('hidden');
  showNavigationNotice(true);
  selectProductPanel('demo-panel');
  const demoFrame = document.querySelector('#demo-frame');
  demoFrame.src = '/demo/?authenticated=' + Date.now();
  document.querySelector('#account-label').textContent =
    user.email + ' · ' + (user.provider === 'google' ? 'Google' : '邮箱账户');
  const sessionActions = document.querySelector('#session-actions');
  sessionActions.classList.add('hidden');
  try {
    const response = await fetch('/api/online/session', { cache: 'no-store' });
    const state = await response.json();
    if (state.active) sessionActions.classList.remove('hidden');
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
    document.querySelector('#access-wrap').classList.toggle(
      'hidden',
      !state.access_token_required,
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
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || '创建会话失败。');
  window.location.assign(result.redirect);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  message.className = '';
  message.textContent = '正在读取资料并启动写作台…';
  submit.disabled = true;
  try {
    const archiveFile = form.elements.project_package.files[0];
    if (!archiveFile || !archiveFile.name.toLowerCase().endsWith('.zip')) {
      throw new Error('Research Avatar 项目包必须是 ZIP 文件。');
    }
    if (archiveFile.size > 32 * 1024 * 1024) {
      throw new Error('研究证据 ZIP 不能超过 32 MB。');
    }
    await startSession({
      mode: 'package',
      access_token: form.elements.access_token.value,
      evidence_archive: await encodeFile(archiveFile),
    });
    form.elements.access_token.value = '';
  } catch (error) {
    message.className = 'error';
    message.textContent = error.message;
    submit.disabled = false;
  }
});

lightweightForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  lightweightMessage.className = '';
  lightweightMessage.textContent = '正在读取材料并启动写作台…';
  lightweightSubmit.disabled = true;
  try {
    const elements = lightweightForm.elements;
    const scholarFile = elements.scholar_file.files[0];
    const referenceFiles = Array.from(elements.reference_files.files);
    const resultsFile = elements.results_file.files[0];
    let results = null;
    if (resultsFile) {
      const text = await resultsFile.text();
      try {
        results = JSON.parse(text);
      } catch (_) {
        throw new Error('实验结果数据不是有效 JSON。');
      }
    }
    await startSession({
      mode: 'lightweight',
      venue: elements.venue.value,
      title: elements.title.value,
      scholar_files: scholarFile ? [await encodeFile(scholarFile)] : [],
      reference_files: await Promise.all(referenceFiles.map(encodeFile)),
      results,
    });
  } catch (error) {
    lightweightMessage.className = 'error';
    lightweightMessage.textContent = error.message;
    lightweightSubmit.disabled = false;
  }
});
