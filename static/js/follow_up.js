/* ============================================
   BOS — Follow Up Page
   Settled bet review: X marks on screenshots,
   losing-selection ticks on copied text, notes,
   and PDF export (one page per slip).
   ============================================ */

let followUps = [];
let drafts = {};
let visibleFollowUps = [];

function escapeHtml(str) {
    if (str === undefined || str === null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function fmtMoney(v) {
    if (v === undefined || v === null) return 'TZS 0';
    const n = typeof v === 'string' ? parseFloat(v) : v;
    if (isNaN(n)) return 'TZS 0';
    return new Intl.NumberFormat('en-TZ', { style: 'currency', currency: 'TZS', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);
}

function badgeClass(status) {
    return status === 'won' ? 'badge-won' :
           status === 'lost' ? 'badge-lost' :
           status === 'cashed' ? 'badge-cashed' :
           status === 'void' ? 'badge-void' : 'badge-pending';
}

// ==================== LOAD ====================
async function loadFollowUps() {
    try {
        const res = await fetch('/api/followup');
        followUps = await res.json();
        drafts = {};
        followUps.forEach(s => {
            drafts[s.id] = {
                screenshot_annotations: Array.isArray(s.screenshot_annotations) ? s.screenshot_annotations.map(a => ({ x: a.x, y: a.y, size: a.size || 4 })) : [],
                lost_matches: Array.isArray(s.lost_matches) ? s.lost_matches.map(l => ({ index: l.index, event: l.event, selection: l.selection, lost: !!l.lost })) : [],
                follow_up_notes: s.follow_up_notes || ''
            };
        });
        renderFollowUps();
    } catch (err) {
        document.getElementById('followUpContainer').innerHTML = `
            <div class="glass-card">
                <div style="padding:60px;text-align:center;color:var(--text-muted);">
                    <i class="fas fa-exclamation-circle" style="font-size:40px;display:block;margin-bottom:16px;"></i>
                    Failed to load follow-up data.
                </div>
            </div>`;
    }
}

// ==================== FILTER ====================
function filterFollowUps() {
    const search = (document.getElementById('fuSearch').value || '').toLowerCase();
    const status = document.getElementById('fuStatusFilter').value;

    visibleFollowUps = followUps.filter(s => {
        if (status !== 'all' && s.status !== status) return false;
        if (!search) return true;
        const matches = (s.matches || []).map(m => (m.event || '') + ' ' + (m.selection || '')).join(' ');
        const haystack = [s.slip_number, s.slip_name, s.bookmaker_name, matches].join(' ').toLowerCase();
        return haystack.includes(search);
    });

    renderCards();
}

// ==================== RENDER ====================
function renderFollowUps() {
    // Stats
    const total = followUps.length;
    const won = followUps.filter(s => s.status === 'won').length;
    const lost = followUps.filter(s => s.status === 'lost').length;
    const reviewed = followUps.filter(s => (drafts[s.id] && drafts[s.id].follow_up_notes) || (drafts[s.id] && drafts[s.id].lost_matches.some(l => l.lost)) || (drafts[s.id] && drafts[s.id].screenshot_annotations.length > 0)).length;

    document.getElementById('fuTotal').textContent = total;
    document.getElementById('fuWon').textContent = won;
    document.getElementById('fuLost').textContent = lost;
    document.getElementById('fuReviewed').textContent = reviewed;

    filterFollowUps();
}

function renderCards() {
    const container = document.getElementById('followUpContainer');
    if (visibleFollowUps.length === 0) {
        container.innerHTML = `
            <div class="glass-card">
                <div style="padding:60px;text-align:center;color:var(--text-muted);">
                    <i class="fas fa-clipboard-check" style="font-size:40px;display:block;margin-bottom:16px;"></i>
                    <h3 style="color:var(--text-secondary);margin-bottom:8px;">No settled bets found</h3>
                    <p>Settled slips that include a screenshot or copied text will appear here for follow up.</p>
                </div>
            </div>`;
        return;
    }
    container.innerHTML = visibleFollowUps.map(buildSlipCard).join('');
    visibleFollowUps.forEach(s => {
        const card = document.getElementById('fu-card-' + s.id);
        if (card) wireCard(card, s);
    });
}

function buildSlipCard(slip) {
    const draft = drafts[slip.id];
    const statusClass = badgeClass(slip.status);
    const profitClass = slip.profit_loss > 0 ? 'profit-positive' : slip.profit_loss < 0 ? 'profit-negative' : '';
    const profitText = slip.status === 'pending' ? '—' : (slip.profit_loss >= 0 ? '+' : '') + fmtMoney(slip.profit_loss);
    const date = new Date(slip.settled_at || slip.created_at);
    const dateStr = date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });

    const hasScreenshot = !!slip.screenshot_path;
    const hasMatches = (slip.matches || []).length > 0;
    const hasText = !!slip.raw_text;

    let screenshotSection = '';
    if (hasScreenshot) {
        screenshotSection = `
            <div class="fu-section-title"><i class="fas fa-camera"></i> Screenshot — click to place an X on the losing team</div>
            <p class="fu-hint">Click directly on the screenshot to drop a red <strong style="color:var(--accent-red)">X</strong>.
            Click an existing X to remove it. Marks are saved with the slip.</p>
            <div>
                <div class="fu-annotate" id="fu-annotate-${slip.id}" data-slip-id="${slip.id}">
                    <img src="${slip.screenshot_path}" alt="Screenshot" class="fu-img">
                    <div class="fu-marks" id="fu-marks-${slip.id}"></div>
                </div>
                <button type="button" class="btn btn-sm" style="margin-top:10px;padding:6px 12px;" onclick="clearAnnotations(${slip.id})">
                    <i class="fas fa-eraser"></i> Clear all X marks
                </button>
            </div>`;
    }

    let matchesSection = '';
    if (hasMatches) {
        const rows = slip.matches.map((m, i) => {
            const lost = (draft.lost_matches.find(l => l.index === i) || {}).lost;
            const mClass = lost ? 'fu-match-lost' : '';
            return `
            <tr>
                <td style="width:36px;color:var(--text-muted);font-size:12px;">${i + 1}</td>
                <td class="${mClass}"><strong>${escapeHtml(m.event || '—')}</strong></td>
                <td class="${mClass}" style="color:var(--text-secondary);">${escapeHtml(m.selection || '—')}</td>
                <td style="text-align:right;font-weight:700;color:var(--accent-cyan);white-space:nowrap;">${m.odds ? parseFloat(m.odds).toFixed(2) : '—'}</td>
                <td style="text-align:right;white-space:nowrap;">
                    <label class="fu-check">
                        <input type="checkbox" class="fu-lost-input" data-slip-id="${slip.id}" data-index="${i}"
                            ${lost ? 'checked' : ''} onchange="toggleLostMatch(${slip.id}, ${i}, this.checked)">
                        <span style="color:${lost ? 'var(--accent-red)' : 'var(--text-muted)'}">Lost</span>
                    </label>
                </td>
            </tr>`;
        }).join('');
        matchesSection = `
            <div class="fu-section-title"><i class="fas fa-list-ul"></i> Selections — tick the ones that caused the loss</div>
            <div style="overflow-x:auto;">
                <table class="fu-matches">
                    <thead><tr><th>#</th><th>Event</th><th>Selection</th><th style="text-align:right">Odds</th><th style="text-align:right">Result</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;
    }

    let textSection = '';
    if (!hasMatches && hasText) {
        textSection = `
            <div class="fu-section-title"><i class="fas fa-clipboard"></i> Copied Slip Text</div>
            <div style="padding:12px 14px;background:rgba(255,255,255,0.02);border:1px solid var(--glass-border);border-radius:8px;font-size:13px;line-height:1.6;white-space:pre-wrap;color:var(--text-secondary);">
                ${escapeHtml(slip.raw_text)}
            </div>`;
    }

    const sourceLabel = hasScreenshot && hasMatches ? 'Screenshot + Copy Text'
                       : hasScreenshot ? 'Screenshot'
                       : hasText ? 'Copy Text' : 'No attachment';

    return `
    <div class="fu-card" id="fu-card-${slip.id}">
        <div class="fu-header">
            <div class="fu-header-left">
                <span class="badge ${statusClass} fu-badge">${slip.status.toUpperCase()}</span>
                <div>
                    <div class="fu-title">${escapeHtml(slip.slip_name || 'Untitled Slip')}</div>
                    <div class="fu-sub">${escapeHtml(slip.slip_number || '')} · ${escapeHtml(sourceLabel)}</div>
                </div>
            </div>
            <div class="top-actions">
                <span class="fu-unsaved" id="fu-unsaved-${slip.id}"><i class="fas fa-exclamation-circle"></i> Unsaved changes</span>
                <span class="fu-saved" id="fu-saved-${slip.id}"><i class="fas fa-check-circle"></i> Saved</span>
                <button type="button" class="btn btn-primary btn-sm" onclick="saveFollowUp(${slip.id})">
                    <i class="fas fa-save"></i> Save
                </button>
            </div>
        </div>

        <div class="fu-meta">
            <div class="fu-meta-item"><div class="fu-meta-label">Bookmaker</div><div class="fu-meta-value">${escapeHtml(slip.bookmaker_name || '—')}</div></div>
            <div class="fu-meta-item"><div class="fu-meta-label">Stake</div><div class="fu-meta-value">${fmtMoney(slip.stake)}</div></div>
            <div class="fu-meta-item"><div class="fu-meta-label">Odds</div><div class="fu-meta-value" style="color:var(--accent-cyan)">${slip.odds ? slip.odds.toFixed(2) : '—'}</div></div>
            <div class="fu-meta-item"><div class="fu-meta-label">P/L</div><div class="fu-meta-value ${profitClass}">${profitText}</div></div>
            <div class="fu-meta-item"><div class="fu-meta-label">Settled</div><div class="fu-meta-value" style="font-size:12px;">${dateStr}</div></div>
        </div>

        ${screenshotSection}
        ${textSection}
        ${matchesSection}

        <div class="fu-section-title" style="margin-top:20px;"><i class="fas fa-comments"></i> Follow Up Notes</div>
        <textarea class="fu-notes" id="fu-notes-${slip.id}" placeholder="e.g. The loss was caused by Man Utd failing to win at home; bet lost on the Arsenal match..."
            oninput="onNotesChange(${slip.id}, this.value)">${escapeHtml(draft.follow_up_notes)}</textarea>

        <div class="fu-footer">
            <span class="fu-hint" style="margin:0;">Marked losing teams help you review what went wrong.</span>
            <button type="button" class="btn" onclick="saveFollowUp(${slip.id})"><i class="fas fa-save"></i> Save Follow Up</button>
        </div>
    </div>`;
}

// ==================== CARD WIRING (screenshot annotations) ====================
function wireCard(card, slip) {
    const annotate = document.getElementById('fu-annotate-' + slip.id);
    if (!annotate) return;
    const img = annotate.querySelector('.fu-img');
    const marksLayer = document.getElementById('fu-marks-' + slip.id);

    function placeMarks() {
        marksLayer.innerHTML = '';
        const anns = drafts[slip.id].screenshot_annotations;
        anns.forEach((ann, i) => {
            const mark = document.createElement('div');
            mark.className = 'fu-x';
            const sizePx = Math.max(16, (ann.size / 100) * (img.clientWidth || 400) * 0.9);
            mark.style.left = ann.x + '%';
            mark.style.top = ann.y + '%';
            mark.style.width = sizePx + 'px';
            mark.style.height = sizePx + 'px';
            mark.style.fontSize = (sizePx * 0.7) + 'px';
            mark.title = 'Click to remove X';
            mark.textContent = '✕';
            mark.onclick = (e) => {
                e.stopPropagation();
                drafts[slip.id].screenshot_annotations.splice(i, 1);
                placeMarks();
                markDirty(slip.id);
            };
            marksLayer.appendChild(mark);
        });
    }

    img.onclick = (e) => {
        const rect = img.getBoundingClientRect();
        if (rect.width === 0) return;
        const x = ((e.clientX - rect.left) / rect.width) * 100;
        const y = ((e.clientY - rect.top) / rect.height) * 100;
        drafts[slip.id].screenshot_annotations.push({ x: +x.toFixed(2), y: +y.toFixed(2), size: 4 });
        placeMarks();
        markDirty(slip.id);
    };

    img.onload = placeMarks;
    if (img.complete && img.naturalWidth > 0) placeMarks();
}

// ==================== INTERACTIONS ====================
function toggleLostMatch(slipId, index, checked) {
    const draft = drafts[slipId];
    let entry = draft.lost_matches.find(l => l.index === index);
    if (!entry) {
        entry = { index: index, event: '', selection: '', lost: false };
        draft.lost_matches.push(entry);
    }
    entry.lost = checked;
    const slip = followUps.find(s => s.id === slipId);
    if (slip && slip.matches && slip.matches[index]) {
        entry.event = slip.matches[index].event;
        entry.selection = slip.matches[index].selection;
    }
    // Re-render the row strikethrough styling
    const row = document.querySelector(`.fu-lost-input[data-slip-id="${slipId}"][data-index="${index}"]`);
    if (row) {
        const tr = row.closest('tr');
        const cells = tr.querySelectorAll('td:not(:last-child)');
        cells.forEach(c => c.classList.toggle('fu-match-lost', checked));
        const span = row.parentElement.querySelector('span');
        if (span) { span.textContent = checked ? 'Lost' : 'Lost'; span.style.color = checked ? 'var(--accent-red)' : 'var(--text-muted)'; }
    }
    markDirty(slipId);
}

function onNotesChange(slipId, value) {
    drafts[slipId].follow_up_notes = value;
    markDirty(slipId);
}

function clearAnnotations(slipId) {
    drafts[slipId].screenshot_annotations = [];
    const marksLayer = document.getElementById('fu-marks-' + slipId);
    if (marksLayer) marksLayer.innerHTML = '';
    markDirty(slipId);
}

function markDirty(slipId) {
    const unsaved = document.getElementById('fu-unsaved-' + slipId);
    const saved = document.getElementById('fu-saved-' + slipId);
    if (unsaved) unsaved.classList.add('show');
    if (saved) saved.classList.remove('show');
}

function markSaved(slipId) {
    const unsaved = document.getElementById('fu-unsaved-' + slipId);
    const saved = document.getElementById('fu-saved-' + slipId);
    if (unsaved) unsaved.classList.remove('show');
    if (saved) saved.classList.add('show');
    setTimeout(() => { if (saved) saved.classList.remove('show'); }, 2500);
}

// ==================== SAVE ====================
async function saveFollowUp(slipId) {
    const draft = drafts[slipId];
    if (!draft) return;
    try {
        const res = await fetch('/api/followup/' + slipId, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                screenshot_annotations: draft.screenshot_annotations,
                lost_matches: draft.lost_matches,
                follow_up_notes: draft.follow_up_notes
            })
        });
        if (res.ok) {
            showToast('Follow up saved', 'success');
            markSaved(slipId);
            renderFollowUps();
        } else {
            const data = await res.json().catch(() => ({}));
            showToast(data.error || 'Failed to save', 'error');
        }
    } catch (err) {
        showToast('Network error', 'error');
    }
}

async function saveAllDrafts() {
    const ids = Object.keys(drafts).map(Number);
    let ok = 0;
    for (const id of ids) {
        const draft = drafts[id];
        try {
            const res = await fetch('/api/followup/' + id, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    screenshot_annotations: draft.screenshot_annotations,
                    lost_matches: draft.lost_matches,
                    follow_up_notes: draft.follow_up_notes
                })
            });
            if (res.ok) ok++;
        } catch (err) { /* keep going */ }
    }
    showToast(`Saved ${ok} of ${ids.length} follow-ups`, ok === ids.length ? 'success' : 'warning');
    renderFollowUps();
}

function downloadFollowUpPDF() {
    showToast('Generating follow up PDF...', 'info');
    window.open('/api/followup/pdf', '_blank');
}

// ==================== INIT ====================
document.addEventListener('DOMContentLoaded', loadFollowUps);
