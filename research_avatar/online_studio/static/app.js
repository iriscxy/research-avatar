const form = document.querySelector('#setup-form');
const message = document.querySelector('#message');
const submit = document.querySelector('#submit');
const provider = form.elements.provider;
const model = form.elements.model;
const authCard = document.querySelector('#auth-card');
const authForm = document.querySelector('#auth-form');
const authMessage = document.querySelector('#auth-message');
const workspaceShell = document.querySelector('#workspace-shell');

provider.addEventListener('change', () => {
  model.value = provider.value === 'deepseek' ? 'deepseek-v4-flash' : 'gpt-5-nano';
});

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
    for (const file of form.elements.files.files) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = '';
      const chunk = 0x8000;
      for (let index = 0; index < bytes.length; index += chunk) {
        binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
      }
      files.push({ name: file.name, data: btoa(binary) });
    }
    const payload = {
      project_name: form.elements.project_name.value,
      title: form.elements.title.value,
      provider: provider.value,
      model: model.value,
      api_key: form.elements.api_key.value,
      access_token: form.elements.access_token.value,
      outline_confirmed: form.elements.outline_confirmed.checked,
      sections: form.elements.outline.value.split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const separator = line.indexOf('|');
          if (separator < 0) throw new Error('Outline 每行都必须包含 “|”。');
          return {
            title: line.slice(0, separator).trim(),
            purpose: line.slice(separator + 1).trim(),
          };
        }),
      files,
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
