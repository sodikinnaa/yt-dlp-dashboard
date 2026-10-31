let currentAdmin = null;

document.addEventListener('DOMContentLoaded', () => {
    // Clear any previous token from localStorage
    localStorage.removeItem('active_api_key');
    initApp();
});

async function initApp() {
    setupEventListeners();
    await checkAdminAuth();
}

function setupEventListeners() {
    const inputUrl = document.getElementById('input-target-url');
    const inputApiKey = document.getElementById('input-api-key');
    const btnExecute = document.getElementById('btn-execute-request');

    document.querySelectorAll('.sample-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            inputUrl.value = btn.dataset.url;
            executeScrape();
        });
    });

    btnExecute.addEventListener('click', executeScrape);
    inputUrl.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') executeScrape();
    });

    // Modal Events
    const modal = document.getElementById('modal-container');
    const btnAdminAction = document.getElementById('btn-admin-action');
    const btnCloseModal = document.getElementById('btn-close-modal');

    btnAdminAction.addEventListener('click', () => {
        modal.classList.remove('hidden');
    });

    btnCloseModal.addEventListener('click', () => {
        modal.classList.add('hidden');
    });

    document.getElementById('form-login').addEventListener('submit', handleLogin);
    document.getElementById('btn-logout-admin').addEventListener('click', handleLogout);
    document.getElementById('form-create-key').addEventListener('submit', handleCreateKey);
}

async function executeScrape() {
    const inputUrl = document.getElementById('input-target-url');
    const inputApiKey = document.getElementById('input-api-key');
    const btnExecute = document.getElementById('btn-execute-request');
    const jsonViewer = document.getElementById('json-viewer');
    const statusLabel = document.getElementById('execution-status');
    const summaryCard = document.getElementById('result-summary-card');

    const url = inputUrl.value.trim();
    const apiKey = inputApiKey.value.trim();

    if (!apiKey) {
        alert('Please specify an X-API-Key. Sign into Admin to issue or copy a key.');
        return;
    }
    if (!url) {
        alert('Please enter a target post URL.');
        return;
    }

    btnExecute.disabled = true;
    btnExecute.innerHTML = `<span class="animate-spin inline-block mr-1">&#9696;</span> Fetching...`;
    statusLabel.innerHTML = `<span class="text-amber-400">Executing...</span>`;
    jsonViewer.innerText = '// Fetching metadata from platform...';
    summaryCard.classList.add('hidden');

    try {
        const start = performance.now();
        const res = await fetch('/api/extract', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': apiKey
            },
            body: JSON.stringify({ url })
        });
        const duration = Math.round(performance.now() - start);
        const data = await res.json();

        if (res.ok && data.status === 'success') {
            statusLabel.innerHTML = `<span class="text-emerald-400 font-medium">200 OK (${duration}ms)</span>`;
            jsonViewer.innerText = JSON.stringify(data, null, 2);

            // Populate preview card
            document.getElementById('card-title').innerText = data.title || 'Untitled';
            document.getElementById('card-author').innerText = `${data.author || 'Unknown'} &bull; ${data.platform.toUpperCase()}`;
            document.getElementById('card-views').innerText = formatNum(data.views);
            document.getElementById('card-likes').innerText = formatNum(data.likes);
            document.getElementById('card-comments').innerText = formatNum(data.comments);
            document.getElementById('card-engagement').innerText = `${data.engagement_rate}%`;

            const thumb = document.getElementById('card-thumb');
            if (data.thumbnail_url) {
                thumb.src = data.thumbnail_url;
                thumb.style.display = 'block';
            } else {
                thumb.style.display = 'none';
            }
            summaryCard.classList.remove('hidden');
        } else {
            statusLabel.innerHTML = `<span class="text-rose-400 font-medium">${res.status} Error (${duration}ms)</span>`;
            jsonViewer.innerText = JSON.stringify(data, null, 2);
        }
    } catch (e) {
        statusLabel.innerHTML = `<span class="text-rose-400 font-medium">Network Error</span>`;
        jsonViewer.innerText = `// Error: ${e.message}`;
    } finally {
        btnExecute.disabled = false;
        btnExecute.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5 fill-current"></i><span>Execute Request</span>`;
        if (window.lucide) lucide.createIcons();
    }
}

// ----------------- ADMIN CONTROLLER -----------------

async function checkAdminAuth() {
    try {
        const res = await fetch('/api/admin/me');
        if (res.ok) {
            const data = await res.json();
            currentAdmin = data.admin;
            renderAdminAuthenticated();
        } else {
            currentAdmin = null;
            renderAdminGuest();
        }
    } catch (e) {
        currentAdmin = null;
        renderAdminGuest();
    }
}

function renderAdminGuest() {
    document.getElementById('view-login').classList.remove('hidden');
    document.getElementById('view-manager').classList.add('hidden');
    document.getElementById('nav-auth-badge').classList.add('hidden');
    document.getElementById('btn-admin-text').innerText = 'Admin Sign In';
    document.getElementById('modal-title').innerText = 'Admin Sign In';
    document.getElementById('modal-subtitle').innerText = 'Authenticate to manage client API keys';
}

function renderAdminAuthenticated() {
    document.getElementById('view-login').classList.add('hidden');
    document.getElementById('view-manager').classList.remove('hidden');
    
    const navBadge = document.getElementById('nav-auth-badge');
    navBadge.classList.remove('hidden');
    navBadge.classList.add('flex');
    document.getElementById('nav-admin-email').innerText = currentAdmin.username;

    document.getElementById('btn-admin-text').innerText = 'Key Manager';
    document.getElementById('modal-title').innerText = 'API Key Management';
    document.getElementById('modal-subtitle').innerText = 'Generate, inspect, and revoke developer keys';
    loadKeysList();
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('admin-email-input').value.trim();
    const password = document.getElementById('admin-pass-input').value.trim();
    const alertBox = document.getElementById('login-alert');

    try {
        const res = await fetch('/api/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok) {
            currentAdmin = data.admin;
            alertBox.classList.add('hidden');
            renderAdminAuthenticated();
        } else {
            alertBox.innerText = data.error || 'Invalid credentials';
            alertBox.classList.remove('hidden');
        }
    } catch (e) {
        alertBox.innerText = 'Failed to connect to authentication server';
        alertBox.classList.remove('hidden');
    }
}

async function handleLogout() {
    await fetch('/api/admin/logout', { method: 'POST' });
    currentAdmin = null;
    localStorage.removeItem('active_api_key');
    const inputApiKey = document.getElementById('input-api-key');
    if (inputApiKey) inputApiKey.value = '';
    renderAdminGuest();
}

async function loadKeysList() {
    try {
        const res = await fetch('/api/admin/keys');
        if (!res.ok) return;
        const data = await res.json();
        renderKeysTable(data.keys || []);
    } catch (e) {
        console.error(e);
    }
}

function renderKeysTable(keys) {
    document.getElementById('keys-count-text').innerText = `${keys.length} Keys`;
    const tbody = document.getElementById('keys-tbody');
    if (!keys.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center py-5 text-muted-foreground">No API keys created yet.</td></tr>`;
        return;
    }

    tbody.innerHTML = keys.map(k => `
        <tr class="hover:bg-zinc-950/40 transition">
            <td class="py-2 px-3 font-medium text-zinc-200">${escapeHtml(k.name)}</td>
            <td class="py-2 px-3 font-mono text-[11px] text-zinc-300">
                <span class="select-all">${k.key_value.slice(0, 16)}...</span>
                <button onclick="copyKey(this, '${k.key_value}')" class="ml-2 px-1.5 py-0.5 rounded text-[11px] font-sans border border-border bg-zinc-900 hover:bg-zinc-800 text-zinc-300 transition" title="Copy full API Key">
                    Copy
                </button>
            </td>
            <td class="py-2 px-3 text-center font-mono text-zinc-400">${k.request_count}</td>
            <td class="py-2 px-3 text-center">
                <span class="px-1.5 py-0.5 rounded text-[10px] font-medium ${
                    k.is_active ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-zinc-800 text-zinc-500'
                }">
                    ${k.is_active ? 'Active' : 'Revoked'}
                </span>
            </td>
            <td class="py-2 px-3 text-center space-x-2">
                <button onclick="toggleKey(${k.id})" class="text-[11px] text-muted-foreground hover:text-amber-400" title="Toggle active status">
                    &#9728;
                </button>
                <button onclick="deleteKey(${k.id})" class="text-[11px] text-muted-foreground hover:text-rose-400" title="Delete key">
                    &#10005;
                </button>
            </td>
        </tr>
    `).join('');
}

async function handleCreateKey(e) {
    e.preventDefault();
    const input = document.getElementById('new-key-label');
    const name = input.value.trim();
    if (!name) return;

    try {
        const res = await fetch('/api/admin/keys/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        if (res.ok) {
            input.value = '';
            loadKeysList();
        }
    } catch (e) {
        console.error(e);
    }
}

async function toggleKey(id) {
    try {
        await fetch('/api/admin/keys/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
        loadKeysList();
    } catch (e) {
        console.error(e);
    }
}

async function deleteKey(id) {
    if (!confirm('Revoke and delete this key permanently?')) return;
    try {
        await fetch('/api/admin/keys/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
        loadKeysList();
    } catch (e) {
        console.error(e);
    }
}

function copyKey(btnElement, text) {
    // 1. Modern Clipboard API if secure
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showCopyFeedback(btnElement);
        }).catch(() => {
            fallbackCopyText(btnElement, text);
        });
    } else {
        // 2. Reliable Fallback for plain HTTP / Non-Secure IP Context
        fallbackCopyText(btnElement, text);
    }
}

function fallbackCopyText(btnElement, text) {
    try {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.top = '0';
        textarea.style.left = '0';
        textarea.style.width = '2em';
        textarea.style.height = '2em';
        textarea.style.padding = '0';
        textarea.style.border = 'none';
        textarea.style.outline = 'none';
        textarea.style.boxShadow = 'none';
        textarea.style.background = 'transparent';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        const successful = document.execCommand('copy');
        document.body.removeChild(textarea);
        if (successful) {
            showCopyFeedback(btnElement);
        } else {
            prompt('Salin API Key manual:', text);
        }
    } catch (err) {
        prompt('Salin API Key manual:', text);
    }
}

function showCopyFeedback(btnElement) {
    if (!btnElement) return;
    const originalText = btnElement.innerText;
    btnElement.innerText = 'Copied!';
    btnElement.classList.add('text-emerald-400', 'border-emerald-500/40');
    setTimeout(() => {
        btnElement.innerText = originalText;
        btnElement.classList.remove('text-emerald-400', 'border-emerald-500/40');
    }, 1500);
}

function formatNum(n) {
    if (!n || isNaN(n)) return '0';
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return n.toLocaleString();
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/[&<>"']/g, function(m) {
        return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[m];
    });
}
