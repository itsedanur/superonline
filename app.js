// ==========================================================================
// Turkcell Superonline - Enterprise AI Dashboard, Review Queue & Product Analytics Logic
// ==========================================================================

const API_BASE = window.location.protocol.startsWith("http") ? "" : "http://localhost:8080";

const presets = {
    fiber: "İnternetim sürekli kopuyor, modemde LOS ışığı yanıyor.",
    superbox: "Taşınabilir modem evin içinde çekmiyor, 4.5G sinyali çok düşük.",
    dsl: "DSL ışığım yanmıyor, ankastreden modeme sinyal gelmiyor.",
    multi: "Fiber aboneliğimi kapatıp Superbox aldım fakat ikisinde de bağlantı problemi yaşıyorum.",
    other: "Faturam çok yüksek geldi."
};

let productChartInstance = null;
let topicChartInstance = null;
let pdTrendChartInstance = null;
let pdSentimentChartInstance = null;
let pdUrgencyChartInstance = null;

let currentComplaints = [];
let currentReviewQueue = [];
let currentActiveItem = null;
let currentSelectedProduct = "Fiber";

document.addEventListener("DOMContentLoaded", () => {
    console.log("APP_JS_PROTOTYPE_FIX_LOADED");

    initTabSwitcher();
    checkServerConfig();
    loadDashboardData();
    loadReviewQueueData();

    const button = document.getElementById("btn-prototype-scrape");

    if (!button) {
        console.error("BUTTON_NOT_FOUND");
        return;
    }

    button.type = "button";
    button.disabled = false;
    button.removeAttribute("disabled");
    button.style.pointerEvents = "auto";

    button.onclick = async function (event) {
        event.preventDefault();
        event.stopPropagation();

        console.log("PROTOTYPE_BUTTON_CLICK_RECEIVED");

        const choice = window.prompt(
            "Lütfen veri toplama modunu seçin:\n\n1 = Yeni Kayıtları Kontrol Et (INCREMENTAL - Sayfa 1'den başlar)\n2 = Geçmiş Kayıtları İçe Aktar (BACKFILL - Checkpoint sayfasından devam eder)\n\nVarsayılan: 1",
            "1"
        );

        if (choice === null) return;

        const strategy = choice.trim() === "2" ? "BACKFILL" : "INCREMENTAL";

        const approved = window.confirm(
            `Seçilen Strateji: ${strategy}\nFiber, Superbox ve DSL için en fazla 3 sayfa ve ürün başına 100 kayıt taranacaktır. İşlemi başlatmak istiyor musunuz?`
        );

        console.log("PROTOTYPE_CONFIRM_RESULT", approved);

        if (!approved) return;

        await startPrototypeScrape(strategy);
    };

    // Initialize Hash Router
    handleHashRouting();
    window.addEventListener("hashchange", handleHashRouting);
});

function handleHashRouting() {
    const rawHash = window.location.hash || "";
    const hash = rawHash.replace("#", "").replace(/^\//, "");
    
    if (!hash) return;

    if (hash === "executive") {
        switchTab("executive");
    } else if (hash === "complaints" || hash === "database") {
        switchTab("complaints-db");
    } else if (hash === "dashboard") {
        switchTab("dashboard");
    } else if (hash.startsWith("scrape-runs/")) {
        const runId = hash.replace("scrape-runs/", "");
        switchTab("scrape-runs");
        loadScrapeRunDetail(runId);
    } else if (hash === "review-queue") {
        switchTab("review-queue");
    } else if (hash === "live-analyzer") {
        switchTab("live-analyzer");
    } else if (hash.startsWith("products/")) {
        const prod = hash.replace("products/", "");
        if (["fiber", "superbox", "adsl", "dsl"].includes(prod)) {
            const targetProd = prod === "dsl" ? "adsl" : prod;
            switchTab(`product-${targetProd}`);
        } else if (prod === "compare") {
            switchTab("product-compare");
        }
    }
}

async function startPrototypeScrape(strategy = "INCREMENTAL") {
    console.log("PROTOTYPE_POST_START", strategy);

    try {
        const response = await fetch("/api/v1/prototype-scrape", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                products: ["Fiber", "Superbox", "DSL"],
                scanMode: "STANDARD",
                strategy: strategy,
                maxPagesPerProduct: 3,
                limitPerProduct: 100
            })
        });

        const text = await response.text();
        let data;

        try {
            data = JSON.parse(text);
        } catch {
            data = { rawResponse: text };
        }

        console.log("PROTOTYPE_POST_RESPONSE", response.status, data);

        if (!response.ok) {
            throw new Error(
                data.error ||
                data.message ||
                "Prototip veri toplama işlemi başlatılamadı."
            );
        }

        if (!data.runId) {
            throw new Error("Sunucudan runId dönmedi.");
        }

        // Auto switch tab to Scrape Run Details view immediately
        window.location.hash = `#/scrape-runs/${data.runId}`;
        switchTab("scrape-runs");

        await pollPrototypeScrape(data.runId);

    } catch (error) {
        console.error("PROTOTYPE_SCRAPE_ERROR", error);
        alert("Veri toplama işlemi hatası: " + error.message);
    }
}

async function pollPrototypeScrape(runId) {
    console.log("PROTOTYPE_POLLING_STARTED", runId);

    const maxAttempts = 360; // 6 minutes maximum polling limit for deep multi-page runs

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 1000));

        const response = await fetch(
            "/api/v1/prototype-scrape/" + encodeURIComponent(runId)
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error ||
                data.message ||
                "İşlem durumu alınamadı."
            );
        }

        // Periodically refresh the run details dashboard during active run
        if (attempt % 3 === 0 && typeof loadScrapeRunDetail === 'function') {
            loadScrapeRunDetail(runId);
        }

        if (
            data.status === "COMPLETED" ||
            data.status === "FAILED" ||
            data.status === "STOPPED_RATE_LIMIT"
        ) {
            const insCount = data.inserted_count ?? data.stats?.inserted_count ?? data.stats?.inserted ?? 0;
            const foundCount = data.unique_urls_seen ?? data.stats?.found ?? data.stats?.unique_urls ?? data.stats?.source_visible_count ?? 0;
            const dupCount = data.duplicate_count ?? data.stats?.duplicate_count ?? data.stats?.duplicate ?? 0;
            const pm = data.productMetrics || {};

            let summaryLines = [];
            summaryLines.push(insCount > 0 ? "✅ Canlı Veri Toplama Tamamlandı!" : (foundCount > 0 ? "ℹ️ Veriler başarıyla tarandı (DB Duplicate mevcut)." : "⚠️ Veri toplama tamamlandı / durduruldu."));
            summaryLines.push(`Strateji: ${data.strategy || 'N/A'} | Durum: ${data.status} | Run ID: ${runId}\n`);

            if (Object.keys(pm).length > 0) {
                summaryLines.push("📊 Ürün Bazlı Detay Sonuçlar:");
                for (const [prodName, m] of Object.entries(pm)) {
                    summaryLines.push(`• ${prodName}: [Sayfa ${m.start_page} ➔ ${m.end_page}] | Taranan: ${m.cards_seen || 0} | Benzersiz: ${m.unique_urls || 0} | Yeni: +${m.inserted || 0} | Duplicate: ${m.duplicate || 0} | Durum: ${m.stop_reason}`);
                }
            }

            summaryLines.push(`\nGenel Toplam -> Bulunan (Benzersiz): ${foundCount} | Yeni Eklenen: +${insCount} | Duplicate: ${dupCount}`);

            alert(summaryLines.join("\n"));

            // Auto refresh UI data & complaints table
            await loadDashboardData();
            await loadReviewQueueData();
            await filterComplaintsTable();
            
            // Refresh final Scrape Run Detail tab
            window.location.hash = `#/scrape-runs/${runId}`;
            switchTab("scrape-runs");
            if (typeof loadScrapeRunDetail === 'function') {
                loadScrapeRunDetail(runId);
            }
            return data;
        }
    }

    throw new Error("İşlem zaman aşımına uğradı (6 dakika aşıldı).");
}

async function checkServerConfig() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/config`);
        if (res.ok) {
            const cfg = await res.json();
            const btn = document.getElementById("btn-prototype-scrape");
            if (btn) {
                if (cfg.publicWebPrototypeEnabled) {
                    btn.disabled = false;
                    btn.classList.remove("disabled");
                    btn.title = "Prototip Canlı Veri Toplama Modunu Başlat";
                } else {
                    btn.disabled = true;
                    btn.classList.add("disabled");
                    btn.title = "Prototip veri kaynağı devre dışı (ENABLE_PUBLIC_WEB_PROTOTYPE=false).";
                }
            }
        }
    } catch (e) {
        console.log("Config check error:", e);
    }
}

function initTabSwitcher() {
    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");
            switchTab(targetTab);
        });
    });
}

function switchTab(tabId) {
    document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));

    const activeBtn = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    if (activeBtn) activeBtn.classList.add("active");

    if (tabId.startsWith("product-")) {
        const subProd = tabId.replace("product-", "");
        window.location.hash = `#/products/${subProd}`;
        
        if (tabId === "product-compare") {
            const tabEl = document.getElementById("tab-product-compare");
            if (tabEl) tabEl.classList.add("active");
            loadProductCompareData();
        } else {
            const tabEl = document.getElementById("tab-product-detail");
            if (tabEl) tabEl.classList.add("active");
            const prod = subProd.toUpperCase();
            const prodName = prod === "FIBER" ? "Fiber" : (prod === "SUPERBOX" ? "Superbox" : "ADSL");
            loadProductDetailData(prodName);
        }
        return;
    }

    if (tabId === "executive") {
        window.location.hash = "#/executive";
        loadExecutiveDashboardData();
    } else if (tabId === "complaints-db") {
        window.location.hash = "#/complaints";
    } else if (tabId === "dashboard") {
        window.location.hash = "#/dashboard";
    } else if (tabId === "review-queue") {
        window.location.hash = "#/review-queue";
    } else if (tabId === "live-analyzer") {
        window.location.hash = "#/live-analyzer";
    }

    const activeTab = document.getElementById(`tab-${tabId}`);
    if (activeTab) activeTab.classList.add("active");

    const titleMap = {
        "executive": "Yönetici Paneli & AI İçgörü Motoru",
        "dashboard": "Turkcell Superonline Genel Bakış (KPI)",
        "live-analyzer": "Canlı AI / LLM Bağlam & Çoklu Ürün Analiz Testi",
        "review-queue": "Manuel İnceleme Kuyruğu",
        "complaints-db": "Veritabanı & Şikayet Kayıtları"
    };
    document.getElementById("page-title").innerText = titleMap[tabId] || "Superonline AI Platform";

    if (tabId === "review-queue") {
        loadReviewQueueData();
    } else if (tabId === "complaints-db" || tabId === "dashboard") {
        filterComplaintsTable();
    }
}

// PHASE 2.3 PRODUCT DETAIL & COMPARE LOGIC
async function loadProductDetailData(productName) {
    currentSelectedProduct = productName;

    const titleEl = document.getElementById("pd-title");
    if (titleEl) {
        const icon = productName === "Fiber" ? "⚡" : (productName === "Superbox" ? "📦" : "🔌");
        titleEl.innerHTML = `${icon} ${productName} İnternet Analiz Detayı`;
    }

    try {
        const [sumRes, trendRes, catRes, sentRes, urgRes] = await Promise.all([
            fetch(`${API_BASE}/api/v1/products/${productName}/summary`),
            fetch(`${API_BASE}/api/v1/products/${productName}/trend?days=30`),
            fetch(`${API_BASE}/api/v1/products/${productName}/categories`),
            fetch(`${API_BASE}/api/v1/products/${productName}/sentiment`),
            fetch(`${API_BASE}/api/v1/products/${productName}/urgency`)
        ]);

        if (sumRes.ok) {
            const summary = await sumRes.json();
            document.getElementById("pd-kpi-total").innerText = summary.total_complaints.toLocaleString('tr-TR');
            document.getElementById("pd-kpi-today").innerText = summary.today_complaints.toLocaleString('tr-TR');
            document.getElementById("pd-kpi-week").innerText = summary.last_7_days_complaints.toLocaleString('tr-TR');
            document.getElementById("pd-kpi-neg-ratio").innerText = `%${summary.negative_ratio_pct}`;
            document.getElementById("pd-kpi-crit").innerText = summary.critical_count.toLocaleString('tr-TR');
            document.getElementById("pd-kpi-pending").innerText = summary.pending_review_count.toLocaleString('tr-TR');
            document.getElementById("pd-kpi-conflict").innerText = summary.product_conflict_count.toLocaleString('tr-TR');
            
            const acc = summary.accuracy;
            if (acc && acc.total_manually_reviewed > 0) {
                document.getElementById("pd-kpi-accuracy").innerText = `%${acc.product_accuracy_pct}`;
            } else {
                document.getElementById("pd-kpi-accuracy").innerText = "Yeterli Veri Yok";
            }
        }

        if (trendRes.ok) {
            const trendData = await trendRes.json();
            renderProductTrendChart(trendData);
        }

        if (sentRes.ok && urgRes.ok) {
            const sentData = await sentRes.json();
            const urgData = await urgRes.json();
            renderProductDistributionCharts(sentData, urgData);
        }

        if (catRes.ok) {
            const catData = await catRes.json();
            renderTop5IssuesTable(catData.top_5_issues || []);
        }

    } catch (e) {
        console.log("Product detail fetch error:", e);
    }
}

function renderProductTrendChart(trendData) {
    if (pdTrendChartInstance) pdTrendChartInstance.destroy();
    const ctx = document.getElementById("productTrendChart");
    if (!ctx) return;

    const labels = trendData.length ? trendData.map(d => d.day) : ["Tarih Yok"];
    const totals = trendData.length ? trendData.map(d => d.total) : [0];
    const negatives = trendData.length ? trendData.map(d => d.negative_cnt) : [0];

    pdTrendChartInstance = new Chart(ctx.getContext("2d"), {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Toplam Şikayet",
                    data: totals,
                    borderColor: "#00A3E0",
                    backgroundColor: "rgba(0, 163, 224, 0.1)",
                    fill: true,
                    tension: 0.3
                },
                {
                    label: "Negatif Şikayet",
                    data: negatives,
                    borderColor: "#EF4444",
                    backgroundColor: "rgba(239, 68, 68, 0.1)",
                    fill: true,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: "#94A3B8" } } },
            scales: {
                x: { ticks: { color: "#94A3B8" }, grid: { display: false } },
                y: { ticks: { color: "#94A3B8" }, grid: { color: "rgba(255, 255, 255, 0.05)" } }
            }
        }
    });
}

function renderProductDistributionCharts(sentData, urgData) {
    if (pdSentimentChartInstance) pdSentimentChartInstance.destroy();
    if (pdUrgencyChartInstance) pdUrgencyChartInstance.destroy();

    const ctx1 = document.getElementById("productSentimentChart");
    if (ctx1) {
        pdSentimentChartInstance = new Chart(ctx1.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: Object.keys(sentData),
                datasets: [{
                    data: Object.values(sentData),
                    backgroundColor: ["#EF4444", "#64748B", "#10B981"]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom", labels: { color: "#94A3B8" } } }
            }
        });
    }

    const ctx2 = document.getElementById("productUrgencyChart");
    if (ctx2) {
        pdUrgencyChartInstance = new Chart(ctx2.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: Object.keys(urgData),
                datasets: [{
                    data: Object.values(urgData),
                    backgroundColor: ["#DC2626", "#F97316", "#FBBF24", "#34D399"]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom", labels: { color: "#94A3B8" } } }
            }
        });
    }
}

function renderTop5IssuesTable(issues) {
    const tbody = document.getElementById("pd-top5-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!issues || issues.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:16px; color:var(--text-muted);">Sorun verisi bulunamadı.</td></tr>`;
        return;
    }

    issues.forEach((item, index) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>#${index + 1}</strong></td>
            <td><strong>${item.sub_category}</strong></td>
            <td><span class="info-badge">${item.count} adet</span></td>
            <td><span class="badge-sent negative">⚡ Kritik İncele</span></td>
        `;
        tbody.appendChild(tr);
    });
}

async function loadProductCompareData() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/products/compare`);
        if (res.ok) {
            const data = await res.json();
            const f = data["Fiber"] || {};
            const s = data["Superbox"] || {};
            const d = data["DSL"] || {};

            document.getElementById("cmp-fiber-total").innerText = (f.total_complaints || 0).toLocaleString('tr-TR');
            document.getElementById("cmp-superbox-total").innerText = (s.total_complaints || 0).toLocaleString('tr-TR');
            document.getElementById("cmp-dsl-total").innerText = (d.total_complaints || 0).toLocaleString('tr-TR');

            document.getElementById("cmp-fiber-neg").innerText = `%${f.negative_ratio_pct || 0}`;
            document.getElementById("cmp-superbox-neg").innerText = `%${s.negative_ratio_pct || 0}`;
            document.getElementById("cmp-dsl-neg").innerText = `%${d.negative_ratio_pct || 0}`;

            document.getElementById("cmp-fiber-crit").innerText = (f.critical_count || 0).toLocaleString('tr-TR');
            document.getElementById("cmp-superbox-crit").innerText = (s.critical_count || 0).toLocaleString('tr-TR');
            document.getElementById("cmp-dsl-crit").innerText = (d.critical_count || 0).toLocaleString('tr-TR');

            document.getElementById("cmp-fiber-pending").innerText = (f.pending_review_count || 0).toLocaleString('tr-TR');
            document.getElementById("cmp-superbox-pending").innerText = (s.pending_review_count || 0).toLocaleString('tr-TR');
            document.getElementById("cmp-dsl-pending").innerText = (d.pending_review_count || 0).toLocaleString('tr-TR');

            document.getElementById("cmp-fiber-conflict").innerText = (f.product_conflict_count || 0).toLocaleString('tr-TR');
            document.getElementById("cmp-superbox-conflict").innerText = (s.product_conflict_count || 0).toLocaleString('tr-TR');
            document.getElementById("cmp-dsl-conflict").innerText = (d.product_conflict_count || 0).toLocaleString('tr-TR');

            const fAcc = f.accuracy && f.accuracy.total_manually_reviewed > 0 ? `%${f.accuracy.product_accuracy_pct}` : "Yeterli Veri Yok";
            const sAcc = s.accuracy && s.accuracy.total_manually_reviewed > 0 ? `%${s.accuracy.product_accuracy_pct}` : "Yeterli Veri Yok";
            const dAcc = d.accuracy && d.accuracy.total_manually_reviewed > 0 ? `%${d.accuracy.product_accuracy_pct}` : "Yeterli Veri Yok";

            document.getElementById("cmp-fiber-acc").innerText = fAcc;
            document.getElementById("cmp-superbox-acc").innerText = sAcc;
            document.getElementById("cmp-dsl-acc").innerText = dAcc;
        }
    } catch (e) {
        console.log("Compare fetch error:", e);
    }
}

// DASHBOARD & REVIEW QUEUE FUNCTIONS
async function loadDashboardData() {
    try {
        const statsRes = await fetch(`${API_BASE}/api/v1/stats`);
        if (statsRes.ok) {
            const stats = await statsRes.json();
            updateKPIs(stats);
            initCharts(stats);
        }
        await filterComplaintsTable();
    } catch (err) {
        console.error("Backend API loadDashboardData error:", err);
    }
}

function updateKPIs(stats) {
    if (!stats || !stats.product_counts) return;
    const counts = stats.product_counts;
    
    if (document.getElementById("kpi-fiber-cnt")) document.getElementById("kpi-fiber-cnt").innerText = (counts["Fiber"] || 0).toLocaleString('tr-TR');
    if (document.getElementById("kpi-superbox-cnt")) document.getElementById("kpi-superbox-cnt").innerText = (counts["Superbox"] || 0).toLocaleString('tr-TR');
    if (document.getElementById("kpi-adsl-cnt")) document.getElementById("kpi-adsl-cnt").innerText = (counts["ADSL"] || 0).toLocaleString('tr-TR');

    if (stats.review_stats) {
        const rs = stats.review_stats;
        if (document.getElementById("kpi-pending-review-cnt")) document.getElementById("kpi-pending-review-cnt").innerText = rs.pending_queue_count || 0;
        if (document.getElementById("nav-review-badge")) document.getElementById("nav-review-badge").innerText = rs.pending_queue_count || 0;
        if (document.getElementById("kpi-reviewed-today")) document.getElementById("kpi-reviewed-today").innerText = rs.reviewed_today || 0;
        if (document.getElementById("kpi-manually-corrected")) document.getElementById("kpi-manually-corrected").innerText = rs.manually_corrected_count || 0;
        if (document.getElementById("kpi-ai-approved")) document.getElementById("kpi-ai-approved").innerText = rs.ai_approved_count || 0;
        if (document.getElementById("kpi-conflict-cnt")) document.getElementById("kpi-conflict-cnt").innerText = rs.product_conflict_count || 0;
    }
}

function populateComplaintsTable(data) {
    const tbody = document.getElementById("complaints-tbody");
    if (!tbody) {
        console.error("COMPLAINT_TABLE_BODY_NOT_FOUND");
        return;
    }
    tbody.innerHTML = "";

    const rows = Array.isArray(data) ? data : (data.items || data.data || []);
    console.log("COMPLAINT_API_RESPONSE", data);
    console.log("COMPLAINT_ROWS_COUNT", rows.length);

    if (rows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 24px; color: var(--text-muted);">Veritabanında kayıtlı şikayet bulunamadı. Filtre seçeneklerini veya Prototip Veri Toplama aracını kullanabilirsiniz.</td></tr>`;
        return;
    }

    rows.forEach(item => {
        const tr = document.createElement("tr");
        
        const prods = item.products || [item.primaryProduct || item.product || "Belirlenemedi"];
        let sourceHtml = item.sourcePageProduct ? `<span class="badge-prod" style="background:#64748B;">S: ${item.sourcePageProduct}</span>` : "";
        let finalHtml = item.finalProduct ? `<span class="badge-prod" style="background:#0F172A; border: 1px solid #38BDF8;">F: ${item.finalProduct}</span>` : "";

        if (item.productConflict) {
            finalHtml += `<br><span class="badge-prod other" style="background: rgba(239, 68, 68, 0.2); color: #F87171; margin-top:4px;" title="Sayfa ürünü ile AI tespiti çelişiyor">⚠️ Çelişki</span>`;
        }

        const decisionSrc = item.productDecisionSource || "LOCAL_RULES";
        let srcBadgeCls = "other";
        if (decisionSrc === "TEXT_HIGH_CONFIDENCE") srcBadgeCls = "fiber";
        else if (decisionSrc === "TEXT_AND_SOURCE_AGREEMENT") srcBadgeCls = "superbox";
        else if (decisionSrc === "MANUAL_REVIEW") srcBadgeCls = "dsl";

        const conf = item.confidence || 0.95;
        const urgency = item.urgency || "Medium";
        const textContent = item.masked_content || item.maskedText || item.rawText || item.comment || "";
        const pubDate = item.sourcePublishedAt || item.date || item.created_at || "";

        tr.innerHTML = `
            <td><strong>${item.id}</strong></td>
            <td><span class="badge-prod ${srcBadgeCls}" style="font-size:0.7rem;">${decisionSrc}</span></td>
            <td>${sourceHtml}<br>${finalHtml}</td>
            <td style="max-width: 320px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${textContent.replace(/"/g, '&quot;')}">${textContent}</td>
            <td><div style="font-weight: 600; font-size: 0.85rem;">${item.mainCategory || item.topic || "Diğer"}</div><div style="font-size: 0.75rem; color: var(--text-muted);">${item.subCategory || ""}</div></td>
            <td><span class="badge-sent ${urgency === 'High' || urgency === 'Critical' ? 'negative' : 'positive'}">${urgency}</span></td>
            <td><span style="font-family: var(--font-mono); font-weight: 700; color: var(--turkcell-yellow);">${conf}</span></td>
            <td><span style="font-size: 0.78rem; color: var(--text-muted); font-family: var(--font-mono);">${pubDate}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

async function filterComplaintsTable() {
    const prodSelect = document.getElementById("filter-product");
    const dateSelect = document.getElementById("filter-date");
    const sortSelect = document.getElementById("sort-date");

    const prodFilter = prodSelect ? prodSelect.value : "ALL";
    const dateRange = dateSelect ? dateSelect.value : "ALL";
    const sortOrder = sortSelect ? sortSelect.value : "DESC";

    try {
        const url = `${API_BASE}/api/v1/complaints?product=${encodeURIComponent(prodFilter)}&date_range=${encodeURIComponent(dateRange)}&sort=${encodeURIComponent(sortOrder)}`;
        const res = await fetch(url);
        
        if (!res.ok) {
            const errTxt = await res.text();
            console.error("COMPLAINTS_API_ERROR", res.status, errTxt);
            alert(`Şikâyet kayıtları yüklenemedi (HTTP ${res.status}): ${errTxt}`);
            return;
        }

        currentComplaints = await res.json();
        populateComplaintsTable(currentComplaints);

    } catch (e) {
        console.error("Filtreleme API hatası:", e);
        alert("Şikâyet kayıtları yüklenemedi: " + e.message);
    }
}

function initCharts(stats) {
    const counts = stats ? stats.product_counts : { "Fiber": 0, "Superbox": 0, "DSL": 0, "Ürün Bağımsız Genel Şikâyet": 0 };
    const topics = stats ? stats.topic_breakdown : {};

    if (productChartInstance) productChartInstance.destroy();
    if (topicChartInstance) topicChartInstance.destroy();

    const ctx1 = document.getElementById("productPieChart");
    if (ctx1) {
        productChartInstance = new Chart(ctx1.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: Object.keys(counts).map(k => `${k} (${counts[k]})`),
                datasets: [{
                    data: Object.values(counts),
                    backgroundColor: ["#00A3E0", "#FFC72C", "#A855F7", "#64748B", "#EC4899", "#94A3B8"],
                    borderWidth: 0,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom", labels: { color: "#94A3B8", font: { family: "Inter", size: 12 } } }
                },
                cutout: "65%"
            }
        });
    }

    const ctx2 = document.getElementById("topicBarChart");
    if (ctx2) {
        topicChartInstance = new Chart(ctx2.getContext("2d"), {
            type: "bar",
            data: {
                labels: Object.keys(topics).length ? Object.keys(topics) : ["Veri Yok"],
                datasets: [{
                    label: "Şikayet Adedi",
                    data: Object.values(topics).length ? Object.values(topics) : [0],
                    backgroundColor: "rgba(0, 71, 187, 0.7)",
                    borderColor: "#0047BB",
                    borderWidth: 1,
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: "#94A3B8" }, grid: { display: false } },
                    y: { ticks: { color: "#94A3B8" }, grid: { color: "rgba(255, 255, 255, 0.05)" } }
                }
            }
        });
    }
}

// REVIEW QUEUE LOGIC
async function loadReviewQueueData() {
    try {
        const res = await fetch(`${API_BASE}/api/v1/review-queue`);
        if (res.ok) {
            const data = await res.json();
            currentReviewQueue = data.queue || [];
            populateReviewQueueTable(currentReviewQueue);
            
            if (data.stats) {
                if (document.getElementById("nav-review-badge")) document.getElementById("nav-review-badge").innerText = data.stats.pending_queue_count || 0;
                if (document.getElementById("kpi-pending-review-cnt")) document.getElementById("kpi-pending-review-cnt").innerText = data.stats.pending_queue_count || 0;
            }
        }
    } catch (e) {
        console.log("Review queue fetch error:", e);
    }
}

function populateReviewQueueTable(data) {
    const tbody = document.getElementById("rq-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!data || data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="13" style="text-align:center; padding: 24px; color: var(--text-muted);">Manuel inceleme bekleyen kayıt bulunmamaktadır. Tüm şikayetler yüksek güvenle onaylanmıştır.</td></tr>`;
        return;
    }

    data.forEach(item => {
        const tr = document.createElement("tr");
        const primary = item.primaryProduct || item.product || "Belirlenemedi";
        const sourceProd = item.sourceProduct || primary;

        const conflictBadge = item.productConflict ? 
            `<span class="badge-sent negative" style="background: rgba(239, 68, 68, 0.2); color: #F87171;">⚠️ Evet</span>` : 
            `<span style="color: var(--text-muted); font-size: 0.8rem;">Hayır</span>`;

        const conf = item.confidence || 0.95;
        const urgency = item.urgency || "Medium";

        tr.innerHTML = `
            <td><strong>${item.id}</strong></td>
            <td><span class="info-badge">${item.source || "Şikayetvar"}</span></td>
            <td><span class="badge-prod other">${sourceProd}</span></td>
            <td><span class="badge-prod fiber">${primary}</span></td>
            <td style="max-width: 240px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${item.maskedText || item.masked_content}</td>
            <td><div style="font-weight: 600; font-size: 0.8rem;">${item.mainCategory || "Diğer"}</div><div style="font-size: 0.72rem; color: var(--text-muted);">${item.subCategory || ""}</div></td>
            <td><span style="font-size: 0.8rem;">${item.sentiment}</span></td>
            <td><span class="badge-sent ${urgency === 'High' || urgency === 'Critical' ? 'negative' : 'positive'}">${urgency}</span></td>
            <td><span style="font-family: var(--font-mono); font-weight: 700; color: ${conf < 0.85 ? '#F87171' : 'var(--turkcell-yellow)'};">${conf}</span></td>
            <td>${conflictBadge}</td>
            <td><span class="info-badge" style="font-size: 0.72rem;">${item.reviewStatus || 'PENDING'}</span></td>
            <td><span style="font-size: 0.75rem; color: var(--text-muted);">${item.date || ""}</span></td>
            <td><button class="btn btn-outline" style="padding: 4px 8px; font-size: 0.75rem;" onclick="openReviewDetailModal('${item.id}')">🔍 İncele</button></td>
        `;
        tbody.appendChild(tr);
    });
}

function filterReviewQueue() {
    const search = document.getElementById("rq-search").value.toLowerCase();
    const prod = document.getElementById("rq-prod").value;
    const urgency = document.getElementById("rq-urgency").value;
    const sentiment = document.getElementById("rq-sentiment").value;

    const filtered = currentReviewQueue.filter(x => {
        if (search && !x.id.toLowerCase().includes(search) && !(x.maskedText || "").toLowerCase().includes(search)) return false;
        if (prod !== "ALL" && x.primaryProduct !== prod && x.sourceProduct !== prod) return false;
        if (urgency !== "ALL" && x.urgency !== urgency) return false;
        if (sentiment !== "ALL" && x.sentiment !== sentiment) return false;
        return true;
    });

    populateReviewQueueTable(filtered);
}

async function filterReviewQueuePreset(presetName) {
    try {
        const res = await fetch(`${API_BASE}/api/v1/review-queue?preset=${presetName}`);
        if (res.ok) {
            const data = await res.json();
            populateReviewQueueTable(data.queue || []);
        }
    } catch (e) {
        console.log("Preset filter error:", e);
    }
}

async function openReviewDetailModal(id) {
    try {
        const res = await fetch(`${API_BASE}/api/v1/complaints/${id}`);
        if (res.ok) {
            currentActiveItem = await res.json();
            
            document.getElementById("md-title").innerText = `✏️ İnceleme ve Düzeltme Modalı: ${currentActiveItem.id}`;
            document.getElementById("md-masked-text").innerText = currentActiveItem.maskedText || currentActiveItem.masked_content;
            
            document.getElementById("edit-primary-product").value = currentActiveItem.primaryProduct || "Fiber";
            document.getElementById("edit-main-cat").value = currentActiveItem.mainCategory || "Bağlantı ve Erişim";
            document.getElementById("edit-sub-cat").value = currentActiveItem.subCategory || "";
            document.getElementById("edit-sentiment").value = currentActiveItem.sentiment || "Negative";
            document.getElementById("edit-emotion").value = currentActiveItem.emotion || "Hayal Kırıklığı";
            document.getElementById("edit-urgency").value = currentActiveItem.urgency || "High";
            document.getElementById("edit-note").value = currentActiveItem.reviewNote || "";

            document.getElementById("md-comparison-box").classList.add("hidden");
            document.getElementById("modal-review-detail").classList.remove("hidden");
        }
    } catch (e) {
        alert("Kayıt detayları yüklenemedi.");
    }
}

function closeReviewDetailModal() {
    document.getElementById("modal-review-detail").classList.add("hidden");
}

async function submitApproveAiReview() {
    if (!currentActiveItem) return;
    try {
        const res = await fetch(`${API_BASE}/api/v1/complaints/${currentActiveItem.id}/approve`, { method: "POST" });
        if (res.ok) {
            alert(`✅ ${currentActiveItem.id} AI sonucu başarıyla onaylandı.`);
            closeReviewDetailModal();
            loadReviewQueueData();
            loadDashboardData();
        }
    } catch (e) {
        alert("Onaylama hatası.");
    }
}

async function submitEditReview() {
    if (!currentActiveItem) return;

    const payload = {
        primaryProduct: document.getElementById("edit-primary-product").value,
        mainCategory: document.getElementById("edit-main-cat").value,
        subCategory: document.getElementById("edit-sub-cat").value,
        sentiment: document.getElementById("edit-sentiment").value,
        emotion: document.getElementById("edit-emotion").value,
        urgency: document.getElementById("edit-urgency").value,
        reviewNote: document.getElementById("edit-note").value
    };

    try {
        const res = await fetch(`${API_BASE}/api/v1/complaints/${currentActiveItem.id}/review`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            alert(`✏️ ${currentActiveItem.id} kaydı başarıyla düzenlendi ve onaylandı.`);
            closeReviewDetailModal();
            loadReviewQueueData();
            loadDashboardData();
        } else {
            const errData = await res.json();
            alert(`Hata: ${errData.error}`);
        }
    } catch (e) {
        alert("Düzenleme kaydetme hatası.");
    }
}

async function submitReanalyzeReview() {
    if (!currentActiveItem) return;
    try {
        const res = await fetch(`${API_BASE}/api/v1/complaints/${currentActiveItem.id}/reanalyze`, { method: "POST" });
        if (res.ok) {
            const data = await res.json();
            const compBox = document.getElementById("md-comparison-box");
            const compContent = document.getElementById("md-comparison-content");
            
            compContent.innerHTML = `
                <div><strong>Eski AI Ürün:</strong> ${data.oldResult.primaryProduct} ➔ <strong>Yeni AI Ürün:</strong> ${data.newResult.primaryProduct}</div>
                <div><strong>Eski Kategori:</strong> ${data.oldResult.mainCategory} ➔ <strong>Yeni Kategori:</strong> ${data.newResult.mainCategory}</div>
                <div><strong>Yeni Güven Skoru:</strong> ${data.newResult.confidence}</div>
            `;
            compBox.classList.remove("hidden");
        }
    } catch (e) {
        alert("Yeniden analiz hatası.");
    }
}

async function submitDeferReview() {
    if (!currentActiveItem) return;
    const note = prompt("Erteleme sebebini yazın:", "Daha sonra incelenecek");
    if (note === null) return;

    try {
        const res = await fetch(`${API_BASE}/api/v1/complaints/${currentActiveItem.id}/defer`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ note })
        });
        if (res.ok) {
            alert(`⏸️ ${currentActiveItem.id} incelemesi ertelendi.`);
            closeReviewDetailModal();
            loadReviewQueueData();
        }
    } catch (e) {
        alert("Erteleme hatası.");
    }
}

async function submitDeleteReview() {
    if (!currentActiveItem) return;
    if (!confirm(`${currentActiveItem.id} kaydını silmek istediğinize emin misiniz?`)) return;

    try {
        const res = await fetch(`${API_BASE}/api/v1/complaints/${currentActiveItem.id}`, { method: "DELETE" });
        if (res.ok) {
            alert(`🗑️ ${currentActiveItem.id} kaydı silindi.`);
            closeReviewDetailModal();
            loadReviewQueueData();
            loadDashboardData();
        }
    } catch (e) {
        alert("Silme hatası.");
    }
}

function setPreset(type) {
    const input = document.getElementById("review-input");
    if (input) {
        input.value = presets[type] || "";
        analyzeText();
    }
}

async function analyzeText() {
    const input = document.getElementById("review-input").value.trim();
    if (!input) {
        alert("Lütfen önce analiz edilecek bir müşteri yorumu girin.");
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/v1/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: input })
        });
        if (res.ok) {
            const data = await res.json();
            renderAnalysisResult(data);
            return;
        }
    } catch (e) {
        console.log("API Error...", e);
    }
}

function renderAnalysisResult(data) {
    document.getElementById("result-placeholder").classList.add("hidden");
    document.getElementById("result-details").classList.remove("hidden");

    const prodsContainer = document.getElementById("res-products-list");
    prodsContainer.innerHTML = "";

    const primary = data.primaryProduct || data.product || "Belirlenemedi";
    const prods = data.products || [primary];

    prods.forEach(p => {
        const badge = document.createElement("div");
        badge.className = "product-badge-large";
        badge.innerText = p;
        if (p === "Superbox") badge.style.background = "linear-gradient(135deg, #FFC72C, #D9A20B)";
        else if (p === "Fiber") badge.style.background = "linear-gradient(135deg, #00A3E0, #0047BB)";
        else if (p === "DSL") badge.style.background = "linear-gradient(135deg, #A855F7, #7E22CE)";
        else badge.style.background = "linear-gradient(135deg, #64748B, #475569)";
        badge.style.color = p === "Superbox" ? "#0F172A" : "#FFF";
        prodsContainer.appendChild(badge);
    });

    if (data.isMultiProduct) {
        const multiBadge = document.createElement("div");
        multiBadge.className = "product-badge-large";
        multiBadge.style.background = "linear-gradient(135deg, #EC4899, #BE185D)";
        multiBadge.innerText = "🔥 Çoklu Ürün Tespit Edildi";
        prodsContainer.appendChild(multiBadge);
    }

    document.getElementById("result-confidence").innerText = `${data.confidence || 0.95} Güven Skoru`;
    
    const reviewBadge = document.getElementById("res-review-badge");
    if (data.needsHumanReview) {
        reviewBadge.innerHTML = `<span class="badge-sent negative">⚠️ Manuel İnceleme Öneriliyor</span>`;
    } else {
        reviewBadge.innerHTML = `<span class="badge-sent positive">✅ Otomatik Onaylandı</span>`;
    }

    document.getElementById("res-main-cat").innerText = data.mainCategory || "Diğer";
    document.getElementById("res-sub-cat").innerText = data.subCategory || "Genel";
    
    const sentEmoji = data.sentiment === "Negative" ? "🔴" : (data.sentiment === "Positive" ? "🟢" : "⚪");
    document.getElementById("res-sentiment-emotion").innerText = `${sentEmoji} ${data.sentiment} (${data.emotion || 'Nötr'}, Skor: ${data.sentimentScore || 0.0})`;
    document.getElementById("res-urgency").innerText = `⚡ ${data.urgency || 'Medium'}`;

    const evList = document.getElementById("res-evidence-list");
    evList.innerHTML = "";
    const evs = data.evidence || ["Gerekçe oluşturuldu"];
    evs.forEach(ev => {
        const li = document.createElement("li");
        li.innerText = ev;
        evList.appendChild(li);
    });

    document.getElementById("json-output-pre").querySelector("code").innerText = JSON.stringify(data, null, 2);
}

let currentRunItems = [];

async function loadScrapeRunDetail(runId) {
    try {
        const res = await fetch(`/api/v1/scrape-runs/${encodeURIComponent(runId)}`);
        if (!res.ok) throw new Error("Run verisi alınamadı");
        const data = await res.json();
        const run = data.run || {};
        const items = data.items || [];
        currentRunItems = items;

        const headerId = document.getElementById("run-header-id");
        if (headerId) headerId.innerText = run.id || runId;

        const statusBadge = document.getElementById("run-status-badge");
        if (statusBadge) {
            const st = run.status || "RUNNING";
            let cls = "other";
            if (st === "COMPLETED") cls = "positive";
            else if (st === "FAILED") cls = "negative";
            else if (st === "RUNNING") cls = "fiber";
            statusBadge.className = `badge-sent ${cls}`;
            statusBadge.innerText = `DURUM: ${st}`;
        }

        const metaInfo = document.getElementById("run-meta-info");
        if (metaInfo) {
            const strategy = run.strategy || "INCREMENTAL";
            const startedAt = run.started_at || "-";
            const completedAt = run.completed_at || "Devam Ediyor...";
            let durationStr = "-";
            if (run.started_at && run.completed_at) {
                const s = new Date(run.started_at);
                const c = new Date(run.completed_at);
                const diffSec = Math.round((c - s) / 1000);
                if (diffSec >= 0) durationStr = `${diffSec}s`;
            }
            metaInfo.innerText = `Strateji: ${strategy} | Başlangıç: ${startedAt} | Bitiş: ${completedAt} | Süre: ${durationStr}`;
        }

        const pagesScanned = run.pages_scanned || (items.length > 0 ? Math.max(...items.map(i => i.page_number || 1)) : 0);
        const uniqueUrls = run.unique_urls_seen || run.stats?.found || items.length;
        const inserted = run.inserted_count ?? run.stats?.inserted ?? items.filter(i => i.status === "NEW_INSERTED").length;
        const duplicates = run.duplicate_count ?? run.stats?.duplicate ?? items.filter(i => i.status === "DUPLICATE").length;
        const failed = run.failed_count ?? run.stats?.failed ?? items.filter(i => i.status === "FAILED").length;

        if (document.getElementById("run-pages-scanned")) document.getElementById("run-pages-scanned").innerText = pagesScanned;
        if (document.getElementById("run-unique-urls")) document.getElementById("run-unique-urls").innerText = uniqueUrls;
        if (document.getElementById("run-inserted")) document.getElementById("run-inserted").innerText = inserted;
        if (document.getElementById("run-duplicates")) document.getElementById("run-duplicates").innerText = duplicates;
        if (document.getElementById("run-failed")) document.getElementById("run-failed").innerText = failed;

        filterRunItemsTable();

    } catch (e) {
        console.error("Load Scrape Run Error:", e);
        const tbody = document.getElementById("run-items-tbody");
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:red;">${e.message}</td></tr>`;
    }
}

function filterRunItemsTable() {
    const tbody = document.getElementById("run-items-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    const selectedProduct = document.getElementById("filter-run-product") ? document.getElementById("filter-run-product").value : "ALL";

    let filtered = currentRunItems;
    if (selectedProduct !== "ALL") {
        filtered = currentRunItems.filter(i => (i.detected_product || i.final_product || i.product_source_page) === selectedProduct);
    }

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;">Kayıt bulunamadı.</td></tr>`;
        return;
    }

    filtered.forEach(item => {
        const tr = document.createElement("tr");
        let statCls = item.status === "NEW_INSERTED" ? "positive" : (item.status === "DUPLICATE" ? "other" : "negative");
        
        const dupReason = item.duplicate_match_reason || (item.status === "DUPLICATE" ? "DB_DUPLICATE_MATCH" : "NONE");
        let dupReasonBadge = `<span class="badge-prod other" style="font-size:0.75rem; background:rgba(255,255,255,0.05); color:#94A3B8;">NONE</span>`;
        
        if (dupReason === "DB_CANONICAL_URL_MATCH" || dupReason === "DB_EXTERNAL_ID_MATCH" || dupReason === "DB_SOURCE_URL_MATCH" || dupReason === "DB_CONTENT_HASH_MATCH") {
            dupReasonBadge = `<span class="badge-prod superbox" style="font-size:0.72rem;" title="Veritabanında eşleşen kayıt bulundu">${dupReason}</span>`;
        } else if (dupReason === "CROSS_PAGE_DUPLICATE") {
            dupReasonBadge = `<span class="badge-prod other" style="font-size:0.72rem; background:rgba(234,179,8,0.2); color:#FACC15;" title="Aynı run içerisinde birden fazla sayfada tekrar eden URL">${dupReason}</span>`;
        }

        tr.innerHTML = `
            <td><span class="badge-prod" style="background:#64748B;">${item.product_source_page || "N/A"}</span></td>
            <td>Sayfa ${item.page_number || "?"}</td>
            <td style="max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                <a href="${item.complaint_url}" target="_blank" style="color:#38BDF8; font-weight: 500;" title="${(item.title || "").replace(/"/g, '&quot;')}">${item.title || "Link"}</a>
            </td>
            <td><span class="badge-prod" style="background:#0F172A; border: 1px solid #38BDF8;">${item.detected_product || "N/A"}</span></td>
            <td><span style="font-family:var(--font-mono); font-weight:700; color:var(--turkcell-yellow);">${item.product_confidence || 0.95}</span></td>
            <td><span class="badge-sent ${statCls}">${item.status}</span></td>
            <td>${dupReasonBadge}</td>
            <td><span style="font-size: 0.78rem; color: var(--text-muted); font-family: var(--font-mono);">${item.source_published_at || item.created_at || "-"}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// EXECUTIVE DASHBOARD & AI INSIGHT ENGINE
let execTrendChartInstance = null;
let execRisingChartInstance = null;
let execVolumeChartInstance = null;
let execDistChartInstance = null;

async function loadExecutiveDashboardData() {
    try {
        const [sumRes, trendRes] = await Promise.all([
            fetch(`${API_BASE}/api/v1/executive/summary`),
            fetch(`${API_BASE}/api/v1/executive/trends`)
        ]);

        if (!sumRes.ok || !trendRes.ok) {
            console.error("Executive API request failed", sumRes.status, trendRes.status);
            return;
        }

        const summary = await sumRes.json();
        const trendResponse = await trendRes.json();
        const trendData = Array.isArray(trendResponse) ? trendResponse : (trendResponse.series || []);
        const meta = trendResponse.coverage_metadata || {};

        console.log("EXEC_SUMMARY_RAW:", summary);
        console.log("EXEC_TRENDS_RAW:", trendResponse);

        // Helper to populate KPI cards with period boundaries & zero-base status
        function renderKPICard(cntId, pctId, msgId, metric) {
            if (!metric) return;
            const cntEl = document.getElementById(cntId);
            const pctEl = document.getElementById(pctId);
            const msgEl = document.getElementById(msgId);

            if (cntEl) cntEl.innerText = (metric.current_count || 0).toLocaleString('tr-TR');
            
            if (pctEl) {
                if (metric.change_status === "NEW_ACTIVITY") {
                    pctEl.innerText = "Yeni Aktivite";
                    pctEl.style.color = "#38BDF8";
                } else if (metric.change_pct !== null && metric.change_pct !== undefined) {
                    const pct = metric.change_pct;
                    pctEl.innerText = `${pct >= 0 ? '+' : ''}${pct}%`;
                    pctEl.style.color = pct > 0 ? '#F87171' : (pct < 0 ? '#4ADE80' : '#94A3B8');
                } else {
                    pctEl.innerText = "Değişim Yok";
                    pctEl.style.color = "#94A3B8";
                }
            }

            if (msgEl) {
                msgEl.innerText = metric.message || `${metric.period_start || ''} ~ ${metric.period_end || ''}`;
            }
        }

        renderKPICard("exec-daily-cnt", "exec-daily-pct", "exec-daily-msg", summary.daily_metrics || { current_count: summary.today_complaints, change_pct: summary.daily_change_pct });
        renderKPICard("exec-weekly-cnt", "exec-weekly-pct", "exec-weekly-msg", summary.weekly_metrics || { current_count: summary.this_week_complaints, change_pct: summary.weekly_change_pct });
        renderKPICard("exec-monthly-cnt", "exec-monthly-pct", "exec-monthly-msg", summary.monthly_metrics || { current_count: summary.this_month_complaints, change_pct: summary.monthly_change_pct });

        if (document.getElementById("exec-crit-ratio")) document.getElementById("exec-crit-ratio").innerText = `%${summary.critical_ratio_pct || 0}`;
        if (document.getElementById("exec-crit-cnt")) document.getElementById("exec-crit-cnt").innerText = `${summary.critical_complaints_count ?? summary.critical_complaint_count ?? 0} Kritik Şikâyet`;

        if (document.getElementById("exec-most-problematic")) {
            document.getElementById("exec-most-problematic").innerText = summary.most_problematic_product || "Yok";
        }
        if (document.getElementById("exec-most-prob-tag")) {
            const probSum = summary.most_problematic_summary;
            if (probSum && probSum.highlight_reason) {
                document.getElementById("exec-most-prob-tag").innerText = probSum.highlight_reason;
            } else {
                document.getElementById("exec-most-prob-tag").innerText = "Aksiyon Gerekli";
            }
        }

        // Handle Trend Sparsity Banner
        const sparsityBanner = document.getElementById("exec-sparsity-banner");
        const trendBadge = document.getElementById("exec-trend-badge");
        if (meta.is_sparse && meta.warning_message) {
            if (sparsityBanner) sparsityBanner.innerText = `⚠️ ${meta.warning_message}`;
        } else {
            if (sparsityBanner) sparsityBanner.innerText = "";
        }
        if (trendBadge) {
            trendBadge.innerText = meta.days_with_data_count ? `Veri: ${meta.days_with_data_count} gün / ${meta.total_timepoints_count} gün` : "Son 30 Günlük Zaman Serisi";
        }

        // Render AI Insights Panel
        const insightsContainer = document.getElementById("executive-ai-insights-container");
        if (insightsContainer && Array.isArray(summary.ai_insights)) {
            insightsContainer.innerHTML = summary.ai_insights.map(item => {
                let borderCol = "#38BDF8";
                let bgCol = "rgba(56, 189, 248, 0.08)";
                if (item.type === "CRITICAL_ALERT") {
                    borderCol = "#F87171";
                    bgCol = "rgba(248, 113, 113, 0.1)";
                } else if (item.type === "PRODUCT_HIGHLIGHT") {
                    borderCol = "#FFC72C";
                    bgCol = "rgba(255, 199, 44, 0.1)";
                } else if (item.type === "ACTION_RECOMMENDATION") {
                    borderCol = "#A855F7";
                    bgCol = "rgba(168, 85, 247, 0.1)";
                }

                return `
                    <div style="padding: 14px; background: ${bgCol}; border-left: 4px solid ${borderCol}; border-radius: 8px;">
                        <div style="font-weight: 700; font-size: 0.95rem; color: #F8FAFC; margin-bottom: 6px;">${item.icon || ''} ${item.title}</div>
                        <div style="font-size: 0.85rem; color: #CBD5E1; line-height: 1.4;">${item.body || item.message || ''}</div>
                    </div>
                `;
            }).join("");
        }

        // 1. CHART: Product Trend Line Chart (Fiber vs Superbox vs ADSL)
        if (execTrendChartInstance) execTrendChartInstance.destroy();
        const ctxTrend = document.getElementById("execProductTrendChart");
        if (ctxTrend && Array.isArray(trendData)) {
            const labels = trendData.map(d => d.day || d.date || "Tarih Yok");
            const fiberData = trendData.map(d => d.fiber_cnt ?? d.Fiber ?? 0);
            const superboxData = trendData.map(d => d.superbox_cnt ?? d.Superbox ?? 0);
            const adslData = trendData.map(d => d.adsl_cnt ?? d.ADSL ?? 0);

            console.log("EXEC_PRODUCT_TREND_LABELS:", labels);
            console.log("EXEC_PRODUCT_TREND_DATA:", { fiberData, superboxData, adslData });

            execTrendChartInstance = new Chart(ctxTrend.getContext("2d"), {
                type: "line",
                data: {
                    labels,
                    datasets: [
                        { label: "⚡ Fiber", data: fiberData, borderColor: "#00A3E0", backgroundColor: "rgba(0,163,224,0.15)", fill: true, tension: 0.3 },
                        { label: "📦 Superbox", data: superboxData, borderColor: "#FFC72C", backgroundColor: "rgba(255,199,44,0.15)", fill: true, tension: 0.3 },
                        { label: "🔌 ADSL", data: adslData, borderColor: "#A855F7", backgroundColor: "rgba(168,85,247,0.15)", fill: true, tension: 0.3 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "top", labels: { color: "#94A3B8" } }
                    },
                    scales: {
                        x: { ticks: { color: "#64748B" }, grid: { color: "rgba(255,255,255,0.05)" } },
                        y: { ticks: { color: "#64748B" }, grid: { color: "rgba(255,255,255,0.05)" } }
                    }
                }
            });
        }

        // 2. CHART: Top 5 Surging Categories Bar Chart
        if (execRisingChartInstance) execRisingChartInstance.destroy();
        const ctxRising = document.getElementById("execRisingCategoryChart");
        if (ctxRising && Array.isArray(summary.fastest_rising_categories)) {
            const catLabels = summary.fastest_rising_categories.map(c => c.sub_category || c.category || "Genel");
            const catValues = summary.fastest_rising_categories.map(c => c.growth_pct ?? c.growth ?? 0);

            console.log("EXEC_RISING_LABELS:", catLabels);
            console.log("EXEC_RISING_VALUES:", catValues);

            execRisingChartInstance = new Chart(ctxRising.getContext("2d"), {
                type: "bar",
                data: {
                    labels: catLabels,
                    datasets: [{
                        label: "Büyüme Oranı (%)",
                        data: catValues,
                        backgroundColor: ["#F87171", "#FB923C", "#FACC15", "#38BDF8", "#A855F7"],
                        borderRadius: 6
                    }]
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: { ticks: { color: "#64748B" }, grid: { color: "rgba(255,255,255,0.05)" } },
                        y: { ticks: { color: "#94A3B8" }, grid: { display: false } }
                    }
                }
            });
        }

        // 3. CHART: Daily Volume & Sentiment Analysis
        if (execVolumeChartInstance) execVolumeChartInstance.destroy();
        const ctxVolume = document.getElementById("execDailyVolumeChart");
        if (ctxVolume && Array.isArray(trendData)) {
            const labels = trendData.map(d => d.day || d.date || "Tarih Yok");
            const totalVolume = trendData.map(d => d.total ?? 0);
            const negVolume = trendData.map(d => d.negative_cnt ?? 0);

            execVolumeChartInstance = new Chart(ctxVolume.getContext("2d"), {
                type: "bar",
                data: {
                    labels,
                    datasets: [
                        { label: "Toplam Şikâyet Hacmi", data: totalVolume, backgroundColor: "#38BDF8", borderRadius: 4 },
                        { label: "Negatif Duygulu Şikâyetler", data: negVolume, backgroundColor: "#F87171", borderRadius: 4 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "top", labels: { color: "#94A3B8" } }
                    },
                    scales: {
                        x: { ticks: { color: "#64748B" }, grid: { color: "rgba(255,255,255,0.05)" } },
                        y: { ticks: { color: "#64748B" }, grid: { color: "rgba(255,255,255,0.05)" } }
                    }
                }
            });
        }

        // 4. CHART: Product Distribution Doughnut Chart
        if (execDistChartInstance) execDistChartInstance.destroy();
        const ctxDist = document.getElementById("execProductDistChart");
        if (ctxDist && summary.product_metrics) {
            const pm = summary.product_metrics;
            const distLabels = Object.keys(pm).map(k => `${k} (${pm[k].total || 0})`);
            const distValues = Object.values(pm).map(v => v.total || 0);

            execDistChartInstance = new Chart(ctxDist.getContext("2d"), {
                type: "doughnut",
                data: {
                    labels: distLabels,
                    datasets: [{
                        data: distValues,
                        backgroundColor: ["#00A3E0", "#FFC72C", "#A855F7"],
                        borderWidth: 0,
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "bottom", labels: { color: "#94A3B8" } }
                    }
                }
            });
        }

    } catch (e) {
        console.error("Executive Dashboard Data Error:", e);
    }
}
