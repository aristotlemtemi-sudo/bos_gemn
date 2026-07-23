/* ============================================
   BOS — Bankroll Page Scripts
   ============================================ */

async function loadBankroll() {
    try {
        const statsRes = await fetch('/api/bankroll/stats');
        const stats = await statsRes.json();

        const totalBalance = document.getElementById('totalBalance');
        if (totalBalance) totalBalance.textContent = formatCurrency(stats.total_balance);

        const availableBalance = document.getElementById('availableBalance');
        if (availableBalance) availableBalance.textContent = formatCurrency(stats.available);

        const atStake = document.getElementById('atStake');
        if (atStake) atStake.textContent = formatCurrency(stats.at_stake);

        const allTimeProfit = document.getElementById('allTimeProfit');
        if (allTimeProfit) {
            allTimeProfit.textContent = (stats.all_time_profit >= 0 ? '+' : '') + formatCurrency(stats.all_time_profit);
            allTimeProfit.style.color = stats.all_time_profit >= 0 ? 'var(--accent-purple)' : 'var(--accent-red)';
        }

        const availablePct = document.getElementById('availablePct');
        if (availablePct) {
            availablePct.textContent = stats.total_balance > 0
                ? Math.round(stats.available / stats.total_balance * 100) + '% of total'
                : '0% of total';
        }

        const stakeCount = document.getElementById('stakeCount');
        if (stakeCount) {
            stakeCount.textContent = stats.at_stake > 0 ? 'Funds locked in bets' : 'No pending bets';
        }

        const totalRoi = document.getElementById('totalRoi');
        if (totalRoi) totalRoi.innerHTML = `<i class="fas fa-arrow-up"></i> ${stats.roi}% since start`;

        // Load bookmaker table
        const bmRes = await fetch('/api/bookmakers');
        const bms = await bmRes.json();

        const tbody = document.getElementById('bankrollTableBody');
        if (tbody) {
            if (bms.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" class="empty-state"><div style="padding:40px"><i class="fas fa-university"></i><h3>No bookmakers added</h3><p>Add a bookmaker to track your funds</p></div></td></tr>`;
            } else {
                tbody.innerHTML = bms.map(bm => {
                    const atStake = bm.total_bets > 0 ? Math.round(bm.balance * 0.1) : 0;
                    const available = bm.balance - atStake;
                    const statusClass = bm.status === 'active' ? 'badge-won' :
                                       bm.status === 'review' ? 'badge-pending' : 'badge-lost';

                    return `<tr>
                        <td><strong>${bm.name}</strong></td>
                        <td>${formatCurrency(bm.balance)}</td>
                        <td>${formatCurrency(atStake)}</td>
                        <td>${formatCurrency(available)}</td>
                        <td class="profit-display ${bm.total_profit >= 0 ? 'profit-positive' : 'profit-negative'}">${bm.total_profit >= 0 ? '+' : ''}${formatCurrency(bm.total_profit)}</td>
                        <td style="color:${bm.roi >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'};font-weight:700">${bm.roi > 0 ? '+' : ''}${bm.roi.toFixed(1)}%</td>
                        <td><span class="badge ${statusClass}">${bm.status}</span></td>
                        <td><button class="btn" style="padding:6px 12px;font-size:12px" onclick="withdrawFunds(${bm.id})">Withdraw</button></td>
                    </tr>`;
                }).join('');
            }
        }

        // Load chart
        await loadBankrollChart(30);

    } catch (err) {
        console.error('Bankroll load error:', err);
    }
}

let bankrollChartInstance = null;

async function loadBankrollChart(days = 30) {
    const ctx = document.getElementById('bankrollChart');
    if (!ctx) return;

    try {
        const res = await fetch(`/api/bankroll/history?days=${days}`);
        const data = await res.json();

        if (bankrollChartInstance) bankrollChartInstance.destroy();

        bankrollChartInstance = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Bankroll Balance',
                    data: data.balance_data,
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.15)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#64748b' } },
                    y: { ticks: { color: '#64748b', callback: v => formatCurrency(v) } }
                }
            }
        });
    } catch (e) {
        console.error('Chart load error:', e);
    }
}