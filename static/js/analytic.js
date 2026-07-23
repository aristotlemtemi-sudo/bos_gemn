/* ============================================
   BOS — Analytics Page Scripts
   ============================================ */

function renderAnalyticsList(containerId, data, maxVal) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!data || data.length === 0) {
        container.innerHTML = `<li style="text-align:center;color:var(--text-muted);padding:20px">No data available</li>`;
        return;
    }

    const max = maxVal || Math.max(...data.map(d => Math.abs(d.roi)));

    container.innerHTML = data.map(item => {
        const width = max > 0 ? (Math.abs(item.roi) / max * 100) : 0;
        const color = item.roi >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
        const barColor = item.roi >= 0
            ? 'linear-gradient(90deg,var(--accent-green),var(--accent-cyan))'
            : 'linear-gradient(90deg,var(--accent-red),var(--accent-orange))';

        return `<li>
            <span>${item.name}</span>
            <div style="display:flex;align-items:center;gap:10px">
                <span style="color:${color};font-weight:700">${item.roi > 0 ? '+' : ''}${item.roi}%</span>
                <div class="analytics-bar"><div class="analytics-bar-fill" style="width:${width}%;background:${barColor}"></div></div>
            </div>
        </li>`;
    }).join('');
}

async function loadAnalytics() {
    try {
        // By Sport
        const sportRes = await fetch('/api/analytics/by-sport');
        const sports = await sportRes.json();
        renderAnalyticsList('sportAnalytics', sports);

        // By Market
        const marketRes = await fetch('/api/analytics/by-market');
        const markets = await marketRes.json();
        renderAnalyticsList('marketAnalytics', markets);

        // By Bookmaker
        const bmRes = await fetch('/api/analytics/by-bookmaker');
        const bms = await bmRes.json();
        renderAnalyticsList('bookmakerAnalytics', bms);

        // By Odds Range
        const oddsRes = await fetch('/api/analytics/by-odds-range');
        const odds = await oddsRes.json();
        renderAnalyticsList('oddsAnalytics', odds);

        // By Strategy
        const stratRes = await fetch('/api/analytics/by-strategy');
        const strats = await stratRes.json();
        renderAnalyticsList('strategyAnalytics', strats);

        // Timeline chart
        loadTimelineChart();

    } catch (err) {
        console.error('Analytics load error:', err);
    }
}

async function loadTimelineChart() {
    try {
        const res = await fetch('/api/analytics/monthly');
        const data = await res.json();

        const ctx = document.getElementById('timelineChart');
        if (!ctx) return;

        new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Monthly Profit',
                    data: data.data,
                    backgroundColor: data.data.map(v => v >= 0 ? 'rgba(34,197,94,0.7)' : 'rgba(239,68,68,0.7)'),
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => 'TZS ' + formatNumber(ctx.raw)
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: '#64748b' }
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.03)' },
                        ticks: {
                            color: '#64748b',
                            callback: v => 'TZS ' + formatNumber(v)
                        }
                    }
                }
            }
        });
    } catch (err) {
        console.error('Timeline chart error:', err);
    }
}

document.addEventListener('DOMContentLoaded', loadAnalytics);