/* ============================================
   BOS — Betting Oversight System
   Main JavaScript Utilities
   ============================================ */

const API_BASE = '';

// ==================== MODAL FUNCTIONS ====================

function openModal() {
    document.getElementById('addBetModal').classList.add('active');
}

function closeModal() {
    document.getElementById('addBetModal').classList.remove('active');
    const form = document.getElementById('betForm');
    if (form) form.reset();
    const preview = document.getElementById('screenshotPreview');
    if (preview) preview.style.display = 'none';
}

function switchModalTab(btn, formId) {
    const tabs = btn.parentElement.querySelectorAll('.tab');
    tabs.forEach(t => t.classList.remove('active'));
    btn.classList.add('active');

    const forms = ['manualForm', 'pasteForm', 'screenshotForm'];
    forms.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = (id === formId + 'Form') ? 'block' : 'none';
    });
}

function toggleCashout(select) {
    const group = document.getElementById('cashoutGroup');
    if (group) group.style.display = select.value === 'cashed' ? 'block' : 'none';
}

function handleFileSelect(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const img = document.getElementById('previewImg');
            const preview = document.getElementById('screenshotPreview');
            const fileName = input.files[0].name.toLowerCase();
            if (fileName.endsWith('.pdf')) {
                if (preview) {
                    preview.innerHTML = '<p style="color:var(--text-muted);font-size:13px;">PDF uploaded: ' + input.files[0].name + '</p>';
                    preview.style.display = 'block';
                }
            } else if (img && preview) {
                img.src = e.target.result;
                preview.style.display = 'block';
            }
        };
        reader.readAsDataURL(input.files[0]);
    }
}

function addMatchRow() {
    const container = document.getElementById('matchesContainer');
    if (!container) return;

    const rowCount = container.querySelectorAll('.match-row').length;
    const row = document.createElement('div');
    row.className = 'match-row';
    row.style.cssText = 'display:grid;grid-template-columns:2fr 1.5fr 1fr auto;gap:8px;margin-bottom:8px;';
    row.innerHTML = `
        <input type="text" name="match_event_${rowCount}" class="form-input match-event" placeholder="Event (e.g. Man Utd vs Liverpool)">
        <input type="text" name="match_selection_${rowCount}" class="form-input match-selection" placeholder="Selection (e.g. Over 2.5)">
        <input type="number" name="match_odds_${rowCount}" class="form-input match-odds" placeholder="Odds" step="0.01" min="1.01">
        <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.remove()" style="padding:4px 8px;">×</button>
    `;
    container.appendChild(row);
}

// ==================== BET CRUD ====================

async function saveBet() {
    const form = document.getElementById('betForm');
    if (!form) return;

    const formData = new FormData(form);

    const matchRows = document.querySelectorAll('.match-row');
    const matches = [];
    matchRows.forEach(row => {
        const eventInput = row.querySelector('.match-event');
        const selectionInput = row.querySelector('.match-selection');
        const oddsInput = row.querySelector('.match-odds');
        const eventText = eventInput ? eventInput.value.trim() : '';
        const selectionText = selectionInput ? selectionInput.value.trim() : '';
        const oddsValue = oddsInput ? parseFloat(oddsInput.value) : NaN;
        if (eventText || selectionText || !isNaN(oddsValue)) {
            matches.push({
                event: eventText,
                selection: selectionText,
                odds: !isNaN(oddsValue) ? oddsValue : 0
            });
        }
    });

    if (matches.length > 0) {
        formData.set('matches', JSON.stringify(matches));
    }

    // Set default match_datetime if empty
    if (!formData.get('match_datetime')) {
        formData.set('match_datetime', new Date().toISOString().slice(0, 16));
    }

    try {
        const res = await fetch('/api/slips', { method: 'POST', body: formData });
        const data = await res.json();
        if (res.ok) {
            showToast('Bet saved successfully!', 'success');
            closeModal();
            // Refresh page-specific data
            if (typeof loadDashboard === 'function') loadDashboard();
            if (typeof loadSlips === 'function') loadSlips();
            if (typeof loadBankroll === 'function') loadBankroll();
            if (typeof loadBookmakers === 'function') loadBookmakers();
        } else {
            showToast(data.error || 'Failed to save bet', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
}

async function updateSlipStatus(id, status) {
    try {
        const res = await fetch(`/api/slips/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });
        if (res.ok) {
            showToast(`Bet marked as ${status}`, 'success');
            if (typeof loadDashboard === 'function') loadDashboard();
            if (typeof loadSlips === 'function') loadSlips();
            if (typeof loadBankroll === 'function') loadBankroll();
            if (typeof loadBookmakers === 'function') loadBookmakers();
        }
    } catch (err) {
        showToast('Failed to update status', 'error');
    }
}

async function deleteSlip(id) {
    if (!confirm('Are you sure you want to delete this bet?')) return;
    try {
        const res = await fetch(`/api/slips/${id}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('Bet deleted', 'success');
            if (typeof loadSlips === 'function') loadSlips();
            if (typeof loadDashboard === 'function') loadDashboard();
        }
    } catch (err) {
        showToast('Failed to delete', 'error');
    }
}

// ==================== TOAST NOTIFICATIONS ====================

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    if (!toast) return;

    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.add('show');

    setTimeout(() => toast.classList.remove('show'), 3000);
}

// ==================== BOOKMAKER SELECT LOADING ====================

async function loadBookmakersSelect() {
    try {
        const res = await fetch('/api/bookmakers');
        const bms = await res.json();
        const select = document.getElementById('modalBookmakerSelect');
        if (select) {
            const options = bms.map(bm => `<option>${bm.name}</option>`).join('');
            select.innerHTML = options + '<option>Other</option>';
        }
    } catch (e) {
        console.error('Failed to load bookmakers select:', e);
    }
}

// ==================== CURRENCY FORMATTING ====================

function formatCurrency(amount, currency = 'TZS') {
    if (amount === undefined || amount === null) return 'TZS 0';
    const num = typeof amount === 'string' ? parseFloat(amount) : amount;
    if (isNaN(num)) return 'TZS 0';

    return new Intl.NumberFormat('en-TZ', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(num);
}

function formatNumber(num) {
    if (num === undefined || num === null) return '0';
    const n = typeof num === 'string' ? parseFloat(num) : num;
    if (isNaN(n)) return '0';
    return new Intl.NumberFormat('en-TZ').format(n);
}

// ==================== USER SETTINGS ====================

async function loadUserSettings() {
    try {
        const res = await fetch('/api/settings');
        const settings = await res.json();

        const userName = document.getElementById('userName');
        const userAvatar = document.getElementById('userAvatar');

        if (userName) userName.textContent = settings.display_name || 'John Doe';
        if (userAvatar) {
            const initials = (settings.display_name || 'JD')
                .split(' ')
                .map(n => n[0])
                .join('')
                .toUpperCase()
                .slice(0, 2);
            userAvatar.textContent = initials;
        }
    } catch (e) {
        console.error('Failed to load user settings:', e);
    }
}

// ==================== EVENT LISTENERS ====================

document.addEventListener('DOMContentLoaded', () => {
    loadBookmakersSelect();
    loadUserSettings();

    // Close modal on overlay click
    const modalOverlay = document.getElementById('addBetModal');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });
    }
});