/* ============================================
   BOS — Dashboard Page Scripts
   ============================================ */

let profitChart = null;
let currentPeriod = 7;

async function loadDashboard() {
    try {
        const statsRes = await fetch('/api/dashboard/stats');
        const stats = await statsRes.json();

        // Bankroll
        const bankrollEl = document.getElementById('bankrollValue');
        if (bankrollEl) bankrollEl.textContent = formatCurrency(stats.total_bankroll);

        const bankrollChange = document.getElementById('bankrollChange');
        if (bankrollChange) bankrollChange.innerHTML = `<i class="fas fa-arrow-up"></i> +${formatCurrency(1240)} this month`;

        // Today's Profit
        const todayProfitEl = document.getElementById('todayProfit');
        if (todayProfitEl) {
            todayProfitEl.textContent = (stats.today_profit >= 0 ? '+' : '') + formatCurrency(stats.today_profit);
            todayProfitEl.style.color = stats.today_profit >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
        }

        const todayBets = document.getElementById('todayBets');
        if (todayBets) todayBets.innerHTML = `<i class="fas fa-arrow-up"></i> ${stats.today_bets} bets placed today`;

        // ROI
        const roiEl = document.getElementById('roiValue');
        if (roiEl) roiEl.textContent = stats.roi + '%';

        const roiChange = document.getElementById('roiChange');
        if (roiChange) roiChange.innerHTML = `<i class="fas fa-arrow-up"></i> +${stats.roi > 0 ? '2.1' : '0.0'}% vs last month`;

        // Strike Rate
        const strikeEl = document.getElementById('strikeRate');
        if (strikeEl) strikeEl.textContent = stats.strike_rate + '%';

        const strikeDetail = document.getElementById('strikeDetail');
        if (strikeDetail) strikeDetail.innerHTML = `<i class="fas fa-arrow-up"></i> ${stats.total_wins} wins / ${stats.total_bets} bets`;

        // Pending
        const pendingEl = document.getElementById('pendingBets');
        if (pendingEl) pendingEl.textContent = stats.pending_bets;

        const pendingStake = document.getElementById('pendingStake');
        if (pendingStake) pendingStake.innerHTML = `<i class="fas fa-info-circle"></i> ${formatCurrency(stats.pending_stake)} at stake`;

        // Streak
        const streakType = stats.streak_type || 'win';
        const streakValue = document.getElementById('streakValue');
        if (streakValue) {
            streakValue.textContent = (streakType === 'win' ? 'W' : 'L') + stats.streak;
            streakValue.style.color = streakType === 'win' ? 'var(--accent-green)' : 'var(--accent-red)';
        }

        const streakDisplay = document.getElementById('streakDisplay');
        if (streakDisplay) {
            const streakHtml = [];
            for (let i = 0; i < Math.min(stats.streak, 10); i++) {
                streakHtml.push(`<span class="streak-dot ${streakType}"></span>`);
            }
            streakDisplay.innerHTML = streakHtml.join('');
        }

        // Load chart and slips
        loadProfitChart(currentPeriod);
        loadLatestSlips();
        loadQuickAnalytics();

    } catch (err) {
        console.error('Dashboard load error:', err);
    }
}

async function loadLatestSlips() {
    try {
        const res = await fetch('/api/slips');
        const slips = await res.json();
        const tbody = document.getElementById('latestSlipsBody');
        if (!tbody) return;

        if (slips.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="empty-state"><div style="padding:40px"><i class="fas fa-receipt"></i><h3>No bets yet</h3><p>Add your first bet to get started</p></div></td></tr>`;
            return;
        }

        tbody.innerHTML = slips.slice(0, 5).map(slip => {
            const statusClass = slip.status === 'won' ? 'badge-won' :
                               slip.status === 'lost' ? 'badge-lost' :
                               slip.status === 'cashed' ? 'badge-cashed' : 'badge-pending';
            const profitClass = slip.profit_loss > 0 ? 'profit-positive' :
                               slip.profit_loss < 0 ? 'profit-negative' : '';
            const profitText = slip.status === 'pending' ? '—' :
                              (slip.profit_loss >= 0 ? '+' : '') + formatCurrency(slip.profit_loss);
            const date = new Date(slip.match_datetime);
            const dateStr = date.toLocaleDateString('en-GB', {
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit'
            });

            return `<tr>
                <td><div class="slip-team">${slip.match}</div><div class="slip-league"><i class="fas fa-futbol"></i> ${slip.league} · ${slip.country}</div></td>
                <td>${slip.prediction}</td>
                <td class="odds-display">${slip.odds.toFixed(2)}</td>
                <td class="stake-display">${formatCurrency(slip.stake)}</td>
                <td><span class="badge ${statusClass}">${slip.status}</span></td>
                <td class="profit-display ${profitClass}">${profitText}</td>
                <td style="color:var(--text-muted);font-size:12px">${dateStr}</td>
                <td>
                    <div class="action-btns">
                        ${slip.status === 'pending' ? `
                        <button class="action-btn win" onclick="updateSlipStatus(${slip.id}, 'won')" title="Mark as Won"><i class="fas fa-check"></i></button>
                        <button class="action-btn loss" onclick="updateSlipStatus(${slip.id}, 'lost')" title="Mark as Lost"><i class="fas fa-times"></i></button>
                        ` : ''}
                    </div>
                </td>
            </tr>`;
        }).join('');
    } catch (err) {
        console.error('Latest slips error:', err);
    }
}

async function loadQuickAnalytics() {
    try {
        // Best market
        const marketRes = await fetch('/api/analytics/by-market');
        const markets = await marketRes.json();
        const bestMarket = document.getElementById('bestMarket');
        if (bestMarket && markets.length > 0) bestMarket.textContent = markets[0].name;

        // Best league
        const slipsRes = await fetch('/api/slips');
        const slips = await slipsRes.json();
        const leagueStats = {};
        slips.forEach(s => {
            if (!leagueStats[s.league]) leagueStats[s.league] = { profit: 0, bets: 0 };
            leagueStats[s.league].profit += s.profit_loss;
            leagueStats[s.league].bets += 1;
        });
        const bestLeague = Object.entries(leagueStats).sort((a, b) => b[1].profit - a[1].profit)[0];
        const bestLeagueEl = document.getElementById('bestLeague');
        if (bestLeagueEl && bestLeague) bestLeagueEl.textContent = bestLeague[0];

        // Avg odds & stake
        const avgOddsEl = document.getElementById('avgOdds');
        if (avgOddsEl) {
            const avgOdds = slips.length > 0 ? slips.reduce((s, x) => s + x.odds, 0) / slips.length : 0;
            avgOddsEl.textContent = avgOdds.toFixed(2);
        }

        const avgStakeEl = document.getElementById('avgStake');
        if (avgStakeEl) {
            const avgStake = slips.length > 0 ? slips.reduce((s, x) => s + x.stake, 0) / slips.length : 0;
            avgStakeEl.textContent = formatCurrency(avgStake);
        }

        // Total yield
        const totalStaked = slips.reduce((sum, s) => sum + s.stake, 0);
        const totalProfit = slips.reduce((sum, s) => sum + s.profit_loss, 0);
        const yieldPct = totalStaked > 0 ? (totalProfit / totalStaked * 100).toFixed(1) : 0;
        const totalYield = document.getElementById('totalYield');
        if (totalYield) totalYield.textContent = yieldPct + '%';

        // High confidence win rate
        const highConf = slips.filter(s => s.confidence >= 4 && s.status !== 'pending');
        const highConfWins = highConf.filter(s => s.status === 'won').length;
        const highConfRate = highConf.length > 0 ? Math.round(highConfWins / highConf.length * 100) : 0;
        const highConfEl = document.getElementById('highConfRate');
        if (highConfEl) highConfEl.textContent = `High: ${highConfRate}%`;
        const confBar = document.getElementById('confidenceBar');
        if (confBar) confBar.style.width = highConfRate + '%';

    } catch (err) {
        console.error('Quick analytics error:', err);
    }
}

async function loadProfitChart(days) {
    try {
        const res = await fetch(`/api/dashboard/profit-chart?days=${days}`);
        const data = await res.json();

        const ctx = document.getElementById('profitChart');
        if (!ctx) return;

        if (profitChart) profitChart.destroy();

        profitChart = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Cumulative Profit',
                    data: data.data,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#3b82f6',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 7
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
                        grid: { color: 'rgba(255, 255, 255, 0.03)' },
                        ticks: { color: '#64748b' }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.03)' },
                        ticks: {
                            color: '#64748b',
                            callback: v => 'TZS ' + formatNumber(v)
                        }
                    }
                }
            }
        });
    } catch (err) {
        console.error('Chart error:', err);
    }
}

function switchChartPeriod(btn, days) {
    const tabs = btn.parentElement.querySelectorAll('.tab');
    tabs.forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    currentPeriod = days;
    loadProfitChart(days);
}

document.addEventListener('DOMContentLoaded', loadDashboard);