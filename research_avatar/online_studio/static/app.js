const form = document.querySelector('#setup-form');
const message = document.querySelector('#message');
const submit = document.querySelector('#submit');
const authCard = document.querySelector('#auth-card');
const authForm = document.querySelector('#auth-form');
const authMessage = document.querySelector('#auth-message');
const workspaceShell = document.querySelector('#workspace-shell');
const demoKeyDialog = document.querySelector('#demo-key-dialog');
const demoKeyForm = document.querySelector('#demo-key-form');
const demoKeyMessage = document.querySelector('#demo-key-message');
const demoKeySubmit = document.querySelector('#demo-key-submit');

function openDemoKeyDialog() {
  demoKeyMessage.className = '';
  demoKeyMessage.textContent = '';
  if (!demoKeyDialog.open) demoKeyDialog.showModal();
  demoKeyForm.elements.api_key.focus();
}

function openRequestedDemoKeyDialog() {
  const url = new URL(window.location.href);
  if (url.searchParams.get('demo_key_required') !== '1') return;
  openDemoKeyDialog();
  url.searchParams.delete('demo_key_required');
  url.searchParams.delete('demo_return');
  window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
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
  authCard.classList.add('hidden');
  workspaceShell.classList.remove('hidden');
  selectProductPanel('demo-panel');
  const demoFrame = document.querySelector('#demo-frame');
  demoFrame.src = '/demo/?authenticated=' + Date.now();
  document.querySelector('#account-label').textContent =
    user.email + ' · ' + (user.provider === 'google' ? 'Google' : '邮箱账户');
  try {
    const response = await fetch('/api/online/session', { cache: 'no-store' });
    const state = await response.json();
    document.querySelector('#session-actions').classList.toggle('hidden', !state.active);
  } catch (_) {
    document.querySelector('#session-actions').classList.add('hidden');
  }
  openRequestedDemoKeyDialog();
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

window.addEventListener('message', (event) => {
  const demoFrame = document.querySelector('#demo-frame');
  if (
    event.origin !== window.location.origin
    || event.source !== demoFrame.contentWindow
    || event.data?.type !== 'paper-studio-demo-api-key-required'
  ) return;
  openDemoKeyDialog();
});

document.querySelector('#demo-key-close').addEventListener('click', () => {
  demoKeyForm.elements.api_key.value = '';
  demoKeyDialog.close();
});

demoKeyForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  demoKeyMessage.className = '';
  demoKeyMessage.textContent = '正在创建你的可编辑 Demo 副本…';
  demoKeySubmit.disabled = true;
  try {
    const response = await fetch('/api/online/demo-session', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({api_key: demoKeyForm.elements.api_key.value}),
    });
    demoKeyForm.elements.api_key.value = '';
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || '创建 Demo 副本失败。');
    window.location.assign(result.redirect);
  } catch (error) {
    demoKeyMessage.className = 'error';
    demoKeyMessage.textContent = error.message;
    demoKeySubmit.disabled = false;
  }
});

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
    const encodeFile = async (file) => {
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = '';
      const chunk = 0x8000;
      for (let index = 0; index < bytes.length; index += chunk) {
        binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
      }
      return { name: file.name, data: btoa(binary) };
    };
    const evidenceArchive = await encodeFile(archiveFile);
    const payload = {
      provider: 'openai',
      api_key: form.elements.api_key.value,
      access_token: form.elements.access_token.value,
      evidence_archive: evidenceArchive,
    };
    const response = await fetch('/api/online/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    form.elements.api_key.value = '';
    form.elements.access_token.value = '';
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || '创建会话失败。');
    window.location.assign(result.redirect);
  } catch (error) {
    message.className = 'error';
    message.textContent = error.message;
    submit.disabled = false;
  }
});
