const form = document.querySelector('#setup-form');
const message = document.querySelector('#message');
const submit = document.querySelector('#submit');
const authCard = document.querySelector('#auth-card');
const authForm = document.querySelector('#auth-form');
const authMessage = document.querySelector('#auth-message');
const workspaceShell = document.querySelector('#workspace-shell');

async function showAuthenticated(user) {
  authCard.classList.add('hidden');
  workspaceShell.classList.remove('hidden');
  document.querySelector('#account-label').textContent =
    user.email + ' · ' + (user.provider === 'google' ? 'Google' : '邮箱账户');
  try {
    const response = await fetch('/api/online/session', { cache: 'no-store' });
    const state = await response.json();
    document.querySelector('#session-actions').classList.toggle('hidden', !state.active);
  } catch (_) {
    document.querySelector('#session-actions').classList.add('hidden');
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

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  message.className = '';
  message.textContent = '正在读取资料并启动写作台…';
  submit.disabled = true;
  const files = [];
  try {
    const expectedFiles = [
      [form.elements.profile_file.files[0], 'PROFILE.html'],
      [form.elements.plan_file.files[0], '03_EXPERIMENT_PLAN.html'],
      [form.elements.result_file.files[0], '05_EXP_RESULT.html'],
    ];
    for (const [file, expected] of expectedFiles) {
      if (!file || file.name.toLowerCase() !== expected.toLowerCase()) {
        throw new Error(`请选择项目中原名为 ${expected} 的文件。`);
      }
    }
    const selectedFiles = expectedFiles.map(([file]) => file);
    const archiveFile = form.elements.evidence_archive.files[0];
    if (!archiveFile || !archiveFile.name.toLowerCase().endsWith('.zip')) {
      throw new Error('研究证据包必须是 ZIP 文件。');
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
    for (const file of selectedFiles) {
      files.push(await encodeFile(file));
    }
    const evidenceArchive = await encodeFile(archiveFile);
    const payload = {
      provider: 'openai',
      api_key: form.elements.api_key.value,
      access_token: form.elements.access_token.value,
      files,
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
