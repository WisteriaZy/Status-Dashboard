// 公共认证和工具函数

// 注册 Service Worker
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js')
        .then(() => console.log('[SW] 注册成功'))
        .catch((err) => console.log('[SW] 注册失败', err));
}

// 检查认证状态
async function checkAuth() {
    try {
        const res = await fetch('/api/auth/status');
        const data = await res.json();
        return data.authenticated;
    } catch {
        return false;
    }
}

// 显示登录页
function showLoginPage() {
    document.getElementById('login-page').style.display = 'flex';
    document.getElementById('main-page').style.display = 'none';
    const codeInput = document.getElementById('totp-code');
    if (codeInput) codeInput.focus();
}

// 显示主页
function showMainPage() {
    document.getElementById('login-page').style.display = 'none';
    document.getElementById('main-page').style.display = 'block';
}

// 提交验证码
async function submitTotp() {
    const code = document.getElementById('totp-code').value.trim();
    const errorEl = document.getElementById('login-error');
    const btn = document.getElementById('login-btn');

    if (!/^\d{6}$/.test(code)) {
        errorEl.textContent = '请输入 6 位数字验证码';
        errorEl.classList.remove('hidden');
        return;
    }

    btn.disabled = true;
    btn.textContent = '验证中...';
    errorEl.classList.add('hidden');

    try {
        const res = await fetch('/api/auth/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code }),
        });

        if (res.ok) {
            showMainPage();
            if (typeof onAuthenticated === 'function') {
                onAuthenticated();
            }
        } else {
            const data = await res.json();
            errorEl.textContent = data.detail || '验证失败';
            errorEl.classList.remove('hidden');
        }
    } catch (e) {
        errorEl.textContent = '网络错误';
        errorEl.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.textContent = '验证';
    }
}

// 初始化应用
async function initApp() {
    const authenticated = await checkAuth();
    if (authenticated) {
        showMainPage();
        if (typeof onAuthenticated === 'function') {
            onAuthenticated();
        }
    } else {
        showLoginPage();
    }
}

// 处理 401 错误
function handleUnauthorized(res) {
    if (res.status === 401) {
        showLoginPage();
        return true;
    }
    return false;
}

// 绑定登录事件
document.addEventListener('DOMContentLoaded', () => {
    const codeInput = document.getElementById('totp-code');
    if (codeInput) {
        codeInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') submitTotp();
        });
    }
});
