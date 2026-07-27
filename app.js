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
    } else if (hash === "reviewed-complaints") {
        switchTab("reviewed-complaints");
    } else if (hash === "live-analyzer") {
        switchTab("live-analyzer");
    } else if (hash === "social-providers") {
        switchTab("social-providers");
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

    document.body.setAttribute("data-active-tab", tabId);

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
    } else if (tabId === "reviewed-complaints") {
        window.location.hash = "#/reviewed-complaints";
    } else if (tabId === "live-analyzer") {
        window.location.hash = "#/live-analyzer";
    } else if (tabId === "social-providers") {
        window.location.hash = "#/social-providers";
        loadSocialProvidersStatus();
    }

    const activeTab = document.getElementById(`tab-${tabId}`);
    if (activeTab) activeTab.classList.add("active");

    const titleMap = {
        "executive": "Yönetici Paneli & AI İçgörü Motoru",
        "dashboard": "Turkcell Superonline Genel Bakış (KPI)",
        "live-analyzer": "Canlı AI / LLM Bağlam & Çoklu Ürün Analiz Testi",
        "review-queue": "Manuel İnceleme Kuyruğu",
        "reviewed-complaints": "İncelenen Şikâyetler",
        "complaints-db": "Veritabanı & Şikayet Kayıtları",
        "social-providers": "Sosyal Medya Kaynakları"
    };
    document.getElementById("page-title").innerText = titleMap[tabId] || "Superonline AI Platform";

    if (tabId === "review-queue") {
        loadReviewQueueData();
    } else if (tabId === "reviewed-complaints") {
        loadReviewedComplaints();
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

        let sourceUrlBtn = "";
        if (item.sourceUrl && (item.sourceUrl.startsWith("http://") || item.sourceUrl.startsWith("https://"))) {
            sourceUrlBtn = `<button type="button" class="btn btn-outline" style="padding: 4px 8px; font-size: 0.75rem;" onclick="window.open('${item.sourceUrl}', '_blank', 'noopener,noreferrer')">🔗 Kaynakta Aç</button>`;
        } else {
            sourceUrlBtn = `<button type="button" class="btn btn-outline disabled" style="padding: 4px 8px; font-size: 0.75rem; opacity: 0.5; cursor: not-allowed;" title="Kaynak bağlantısı bulunamadı" disabled>🔗 Kaynakta Aç</button>`;
        }
        
        const platformLabel = item.platform || "SIKAYETVAR";
        const contentTypeLabel = item.contentType || "COMPLAINT";

        tr.innerHTML = `
            <td><strong style="color: var(--turkcell-blue); cursor: pointer;" data-action="view-complaint" data-complaint-id="${item.id}">${item.id}</strong></td>
            <td><span class="badge-prod" style="background: #334155; font-size: 0.7rem;">${platformLabel}</span></td>
            <td><span class="badge-prod" style="background: #475569; font-size: 0.7rem;">${contentTypeLabel}</span></td>
            <td>${sourceHtml}<br>${finalHtml}</td>
            <td style="max-width: 320px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer;" title="${textContent.replace(/"/g, '&quot;')}" data-action="view-complaint" data-complaint-id="${item.id}">${textContent}</td>
            <td><div style="font-weight: 600; font-size: 0.85rem;">${item.mainCategory || item.topic || "Diğer"}</div><div style="font-size: 0.75rem; color: var(--text-muted);">${item.subCategory || ""}</div></td>
            <td><span class="badge-sent ${urgency === 'High' || urgency === 'Critical' ? 'negative' : 'positive'}">${urgency}</span></td>
            <td><span style="font-family: var(--font-mono); font-weight: 700; color: var(--turkcell-yellow);">${conf}</span></td>
            <td><span style="font-size: 0.78rem; color: var(--text-muted); font-family: var(--font-mono);">${pubDate}</span></td>
            <td style="display: flex; gap: 4px;">
                <button type="button" class="btn btn-outline" style="padding: 4px 8px; font-size: 0.75rem;" data-action="view-complaint" data-complaint-id="${item.id}">🔍 İncele</button>
                ${sourceUrlBtn}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function filterComplaintsTable() {
    const platformSelect = document.getElementById("filter-platform");
    const contentSelect = document.getElementById("filter-content-type");
    const prodSelect = document.getElementById("filter-product");
    const dateSelect = document.getElementById("filter-date");
    const sortSelect = document.getElementById("sort-date");

    const platformFilter = platformSelect ? platformSelect.value : "ALL";
    const contentFilter = contentSelect ? contentSelect.value : "ALL";
    const prodFilter = prodSelect ? prodSelect.value : "ALL";
    const dateRange = dateSelect ? dateSelect.value : "ALL";
    const sortOrder = sortSelect ? sortSelect.value : "DESC";

    try {
        const url = `${API_BASE}/api/v1/complaints?product=${encodeURIComponent(prodFilter)}&date_range=${encodeURIComponent(dateRange)}&sort=${encodeURIComponent(sortOrder)}&platform=${encodeURIComponent(platformFilter)}&content_type=${encodeURIComponent(contentFilter)}`;
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
            <td><button type="button" class="btn btn-outline" style="padding: 4px 8px; font-size: 0.75rem;" data-action="review-complaint" data-complaint-id="${item.id}">🔍 İncele</button></td>
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

            // Instantly remove from DOM
            const row = document.querySelector(`tr:has(button[data-complaint-id="${currentActiveItem.id}"])`);
            if(row) row.remove();
            const badge = document.getElementById("nav-review-badge");
            if(badge) badge.innerText = Math.max(0, parseInt(badge.innerText)-1);

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
        const res = await fetch(`${API_BASE}/api/v1/complaints/${currentActiveItem.id}/correct`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            alert(`✏️ ${currentActiveItem.id} kaydı başarıyla düzenlendi ve onaylandı.`);
            closeReviewDetailModal();
            
            // Instantly remove from DOM
            const row = document.querySelector(`tr:has(button[data-complaint-id="${currentActiveItem.id}"])`);
            if(row) row.remove();
            const badge = document.getElementById("nav-review-badge");
            if(badge) badge.innerText = Math.max(0, parseInt(badge.innerText)-1);

            loadReviewQueueData();
            loadDashboardData();
            if (document.getElementById("tab-reviewed-complaints")?.classList.contains("active")) {
                loadReviewedComplaints();
            }
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
                <div style="margin-top:8px; color:#10B981; font-weight:bold;">Yeniden analiz sonuçları kaydedildi!</div>
            `;
            compBox.classList.remove("hidden");
            
            // Instantly remove from DOM
            const row = document.querySelector(`tr:has(button[data-complaint-id="${currentActiveItem.id}"])`);
            if(row) row.remove();
            const badge = document.getElementById("nav-review-badge");
            if(badge) badge.innerText = Math.max(0, parseInt(badge.innerText)-1);
            
            setTimeout(() => {
                closeReviewDetailModal();
                loadReviewQueueData();
                loadDashboardData();
            }, 3000);
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

async function submitRejectReview() {
    if (!currentActiveItem) return;
    const note = prompt("Reddetme sebebini yazın:", "Geçersiz veya alakasız kayıt");
    if (note === null) return;

    try {
        const res = await fetch(`${API_BASE}/api/v1/complaints/${currentActiveItem.id}/reject`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ note })
        });
        if (res.ok) {
            alert(`❌ ${currentActiveItem.id} kaydı reddedildi.`);
            closeReviewDetailModal();
            
            // Instantly remove from DOM
            const row = document.querySelector(`tr:has(button[data-complaint-id="${currentActiveItem.id}"])`);
            if(row) row.remove();
            const badge = document.getElementById("nav-review-badge");
            if(badge) badge.innerText = Math.max(0, parseInt(badge.innerText)-1);

            loadReviewQueueData();
            loadDashboardData();
        }
    } catch (e) {
        alert("Reddetme hatası.");
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
                let borderCol = "#005BAC";
                let bgCol = "#F0F9FF";
                if (item.type === "CRITICAL_ALERT") {
                    borderCol = "#EF4444";
                    bgCol = "#FEF2F2";
                } else if (item.type === "PRODUCT_HIGHLIGHT") {
                    borderCol = "#005BAC";
                    bgCol = "#F0F9FF";
                } else if (item.type === "ACTION_RECOMMENDATION") {
                    borderCol = "#FFC72C";
                    bgCol = "#FFFBEB";
                } else if (item.type === "STABLE") {
                    borderCol = "#22C55E";
                    bgCol = "#F0FDF4";
                }

                return `
                    <div style="padding: 12px 14px; background: ${bgCol}; border-left: 4px solid ${borderCol}; border-radius: 6px; border-top: 1px solid #E2E8F0; border-right: 1px solid #E2E8F0; border-bottom: 1px solid #E2E8F0;">
                        <div style="font-weight: 700; font-size: 0.88rem; color: #1F2937; margin-bottom: 4px;">${item.icon || ''} ${item.title}</div>
                        <div style="font-size: 0.82rem; color: #4B5563; line-height: 1.4;">${item.body || item.message || ''}</div>
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

            execTrendChartInstance = new Chart(ctxTrend.getContext("2d"), {
                type: "line",
                data: {
                    labels,
                    datasets: [
                        { label: "⚡ Fiber", data: fiberData, borderColor: "#005BAC", backgroundColor: "rgba(0,91,172,0.08)", fill: true, tension: 0.3 },
                        { label: "📦 Superbox", data: superboxData, borderColor: "#D97706", backgroundColor: "rgba(217,119,6,0.08)", fill: true, tension: 0.3 },
                        { label: "🔌 ADSL", data: adslData, borderColor: "#7C3AED", backgroundColor: "rgba(124,58,237,0.08)", fill: true, tension: 0.3 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "top", labels: { color: "#4B5563", font: { family: "Inter" } } }
                    },
                    scales: {
                        x: { ticks: { color: "#6B7280" }, grid: { color: "#E5E7EB" } },
                        y: { ticks: { color: "#6B7280" }, grid: { color: "#E5E7EB" } }
                    }
                }
            });
        }

        // 2. CHART: Top 5 Surging Categories Bar Chart
        if (execRisingChartInstance) execRisingChartInstance.destroy();
        const ctxRising = document.getElementById("execRisingCategoryChart");
        if (ctxRising && Array.isArray(summary.fastest_rising_categories)) {
            const catLabels = summary.fastest_rising_categories.map(c => c.sub_category || c.category || "Genel");
            // Grafiği adet bazlı göster: barValue = absolute_change (eğer yoksa recent_count)
            const catValues = summary.fastest_rising_categories.map(c => c.absolute_change ?? c.recent_count ?? 0);

            execRisingChartInstance = new Chart(ctxRising.getContext("2d"), {
                type: "bar",
                data: {
                    labels: catLabels,
                    datasets: [{
                        label: "Şikâyet Adedi Değişimi",
                        data: catValues,
                        backgroundColor: ["#EF4444", "#F59E0B", "#EAB308", "#0284C7", "#7C3AED"],
                        borderRadius: 4
                    }]
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const raw = summary.fastest_rising_categories[context.dataIndex];
                                    return [
                                        `Son 7 gün: ${raw.recent_count || 0}`,
                                        `Önceki 7 gün: ${raw.previous_count || 0}`,
                                        `Değişim: +${raw.absolute_change || 0}`,
                                        `Durum: ${raw.change_status === 'NEW_ACTIVITY' ? 'Yeni Aktivite' : 'Artış'}`
                                    ];
                                }
                            }
                        }
                    },
                    scales: {
                        x: { ticks: { color: "#6B7280" }, grid: { color: "#E5E7EB" } },
                        y: { ticks: { color: "#4B5563" }, grid: { display: false } }
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
                        { label: "Toplam Şikâyet Hacmi", data: totalVolume, backgroundColor: "#0284C7", borderRadius: 4 },
                        { label: "Negatif Duygulu Şikâyetler", data: negVolume, backgroundColor: "#EF4444", borderRadius: 4 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "top", labels: { color: "#4B5563", font: { family: "Inter" } } }
                    },
                    scales: {
                        x: { ticks: { color: "#6B7280" }, grid: { color: "#E5E7EB" } },
                        y: { ticks: { color: "#6B7280" }, grid: { color: "#E5E7EB" } }
                    }
                }
            });
        }

        // 4. CHART: Product Distribution Doughnut Chart
        if (execDistChartInstance) execDistChartInstance.destroy();
        const ctxDist = document.getElementById("execProductDistChart");
        if (ctxDist && summary.product_metrics) {
            const p = summary.product_metrics;
            const distLabels = ["Fiber", "Superbox", "ADSL"];
            const distValues = [p["Fiber"]?.total || 0, p["Superbox"]?.total || 0, p["ADSL"]?.total || 0];

            execDistChartInstance = new Chart(ctxDist.getContext("2d"), {
                type: "doughnut",
                data: {
                    labels: distLabels,
                    datasets: [{
                        data: distValues,
                        backgroundColor: ["#005BAC", "#FFC72C", "#7C3AED"],
                        borderWidth: 2,
                        borderColor: "#FFFFFF"
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "bottom", labels: { color: "#4B5563", font: { family: "Inter", size: 11 } } }
                    },
                    cutout: "65%"
                }
            });
        }

    } catch (e) {
        console.error("Executive Dashboard Data Error:", e);
    }
}

// Global Event Delegation for Dynamic Elements
document.addEventListener("click", async (event) => {
    // Modal background click to close
    if (event.target.classList.contains("modal-backdrop") || event.target.id === "modal-complaint-detail") {
        closeReviewDetailModal();
        closeComplaintDetailModal();
        closeReviewHistoryModal();
    }

    if (
        event.target.closest("#complaint-detail-close") ||
        event.target.closest("#complaint-detail-close-footer")
    ) {
        event.preventDefault();
        event.stopPropagation();
        closeComplaintDetailModal();
    }

    const reviewBtn = event.target.closest("[data-action='review-complaint']");
    if (reviewBtn) {
        const complaintId = reviewBtn.dataset.complaintId;
        if (complaintId) {
            await openReviewDetailModal(complaintId);
        }
    }

    const viewBtn = event.target.closest("[data-action='view-complaint']");
    if (viewBtn) {
        const complaintId = viewBtn.dataset.complaintId;
        if (complaintId) {
            await openComplaintDetailModal(complaintId);
        }
    }

    const historyBtn = event.target.closest("[data-action='view-history']");
    if (historyBtn) {
        const complaintId = historyBtn.dataset.complaintId;
        if (complaintId) {
            await openReviewHistoryModal(complaintId);
        }
    }
});

function closeComplaintDetailModal() {
    const modal = document.getElementById('modal-complaint-detail');
    if (!modal) return;
    modal.classList.add('hidden');
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
}

// Close Modals on ESC key
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        closeReviewDetailModal();
        closeComplaintDetailModal();
        closeReviewHistoryModal();
    }
});

async function openComplaintDetailModal(id) {
    try {
        const res = await fetch(`${API_BASE}/api/v1/complaints/${id}`);
        if (res.ok) {
            const data = await res.json();
            
            document.getElementById("cd-id").innerText = data.id || "-";
            document.getElementById("cd-date").innerText = data.sourcePublishedAt || data.reviewedAt || "-";
            
            document.getElementById("cd-platform").innerText = data.platform || data.source || "SIKAYETVAR";
            document.getElementById("cd-content-type").innerText = data.contentType || "COMPLAINT";
            document.getElementById("cd-business-unit").innerText = data.businessUnit || "INTERNET_SERVICES";
            document.getElementById("cd-brand").innerText = data.brand || "SUPERONLINE";
            document.getElementById("cd-brand-replied").innerText = data.brandReplied ? "Evet" : "Hayır";
            document.getElementById("cd-case-status").innerText = data.caseStatus || "NEW";
            
            document.getElementById("cd-status").innerText = data.reviewStatus || "PENDING";
            
            document.getElementById("cd-source-prod").innerText = data.sourceProduct || "-";
            document.getElementById("cd-ai-prod").innerText = (data.products && data.products.join(", ")) || data.primaryProduct || "-";
            document.getElementById("cd-final-prod").innerText = data.finalProduct || data.primaryProduct || "-";
            
            document.getElementById("cd-main-cat").innerText = data.mainCategory || data.topic || "-";
            document.getElementById("cd-sub-cat").innerText = data.subCategory || "-";
            document.getElementById("cd-sentiment").innerText = data.sentiment || "-";
            document.getElementById("cd-urgency").innerText = data.urgency || "-";
            document.getElementById("cd-confidence").innerText = data.confidence || "-";
            
            const urlElem = document.getElementById("cd-source-url");
            if (data.sourceUrl && (data.sourceUrl.startsWith("http://") || data.sourceUrl.startsWith("https://"))) {
                urlElem.href = data.sourceUrl;
                urlElem.innerText = data.sourceUrl;
                urlElem.style.pointerEvents = "auto";
                urlElem.style.textDecoration = "underline";
                urlElem.style.color = "var(--turkcell-blue)";
            } else {
                urlElem.href = "#";
                urlElem.innerText = "Kaynak bağlantısı bulunamadı.";
                urlElem.style.pointerEvents = "none";
                urlElem.style.textDecoration = "none";
                urlElem.style.color = "var(--text-muted)";
            }
            
            document.getElementById("cd-text").innerText = data.maskedText || data.masked_content || data.rawText || "-";

            const modal = document.getElementById("modal-complaint-detail");
            modal.classList.remove("hidden");
        } else {
            alert(`Şikâyet detayı yüklenemedi. HTTP ${res.status}`);
        }
    } catch (e) {
        console.error("openComplaintDetailModal error:", e);
        alert("Şikâyet detayı getirilirken bir hata oluştu.");
    }
}

// ================= REVIEWED COMPLAINTS LOGIC =================
let currentReviewedComplaints = [];

async function loadReviewedComplaints() {
    filterReviewedComplaints();
}

async function filterReviewedComplaints() {
    const prod = document.getElementById("rc-filter-product")?.value || "ALL";
    const status = document.getElementById("rc-filter-status")?.value || "ALL";
    const dateRange = document.getElementById("rc-filter-date")?.value || "ALL";

    try {
        const url = `${API_BASE}/api/v1/reviewed-complaints?product=${encodeURIComponent(prod)}&status=${encodeURIComponent(status)}&date_range=${encodeURIComponent(dateRange)}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error("API hatası");
        
        currentReviewedComplaints = await res.json();
        populateReviewedTable(currentReviewedComplaints);
        
        // Update KPIs
        document.getElementById("rc-kpi-total").innerText = currentReviewedComplaints.length;
        document.getElementById("rc-kpi-approved").innerText = currentReviewedComplaints.filter(c => c.reviewStatus === 'APPROVED').length;
        document.getElementById("rc-kpi-corrected").innerText = currentReviewedComplaints.filter(c => c.reviewStatus === 'CORRECTED').length;
        document.getElementById("rc-kpi-reanalyzed").innerText = currentReviewedComplaints.filter(c => c.reviewStatus === 'REANALYZED').length;
        
    } catch (e) {
        console.error("filterReviewedComplaints error", e);
    }
}

function populateReviewedTable(data) {
    const tbody = document.getElementById("rc-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;">İncelenen kayıt bulunamadı.</td></tr>`;
        return;
    }

    data.forEach(item => {
        const tr = document.createElement("tr");
        const statusColors = {
            'APPROVED': '#10B981',
            'CORRECTED': '#F59E0B',
            'REANALYZED': '#3B82F6',
            'REJECTED': '#EF4444'
        };
        const color = statusColors[item.reviewStatus] || '#6B7280';
        
        const aiProd = item.products ? item.products.join(", ") : item.primaryProduct;
        const finalProd = item.finalProduct || item.primaryProduct;
        
        tr.innerHTML = `
            <td><strong style="color: var(--turkcell-blue); cursor: pointer;" data-action="view-complaint" data-complaint-id="${item.id}">${item.id}</strong></td>
            <td>${item.sourceProduct || '-'}</td>
            <td>${aiProd}</td>
            <td><strong>${finalProd}</strong></td>
            <td><div style="font-weight:600;">${item.mainCategory}</div><div style="font-size:0.75rem;">${item.subCategory}</div></td>
            <td><span class="badge-sent ${item.urgency==='High'||item.urgency==='Critical'?'negative':'positive'}">${item.urgency}</span> / ${item.sentiment}</td>
            <td>${item.confidence}</td>
            <td><span style="color:${color}; font-weight:bold;">${item.reviewStatus}</span></td>
            <td><div style="font-size:0.8rem;">${item.reviewedAt || '-'}</div></td>
            <td>${item.reviewedBy || '-'}</td>
            <td style="display: flex; gap: 4px;">
                <button class="btn btn-outline" style="padding: 4px 8px; font-size: 0.75rem;" data-action="view-history" data-complaint-id="${item.id}">Geçmiş</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function openReviewHistoryModal(id) {
    try {
        const res = await fetch(`${API_BASE}/api/v1/complaints/${id}/review-history`);
        if (res.ok) {
            const history = await res.json();
            const content = document.getElementById("rh-content");
            if (history.length === 0) {
                content.innerHTML = "<p>Geçmiş bulunamadı.</p>";
            } else {
                content.innerHTML = history.map(h => `
                    <div style="border-left: 3px solid var(--turkcell-blue); padding-left: 12px; margin-bottom: 12px;">
                        <div style="font-size: 0.8rem; color: var(--text-muted);">${h.reviewed_at} - <strong>${h.action}</strong> (${h.reviewed_by})</div>
                        <div style="font-size: 0.9rem; margin-top: 4px;">Not: ${h.note || '-'}</div>
                        ${h.old_values ? `<div style="font-size: 0.8rem; color: #EF4444; margin-top:4px;">Eski: ${JSON.stringify(h.old_values)}</div>` : ''}
                        ${h.new_values ? `<div style="font-size: 0.8rem; color: #10B981;">Yeni: ${JSON.stringify(h.new_values)}</div>` : ''}
                    </div>
                `).join("");
            }
            document.getElementById("modal-review-history").classList.remove("hidden");
        }
    } catch (e) {
        console.error(e);
    }
}

function closeReviewHistoryModal() {
    const modal = document.getElementById("modal-review-history");
    if(modal) modal.classList.add("hidden");
}

async function loadSocialProvidersStatus() {
    const grid = document.getElementById("social-providers-grid");
    if (!grid) return;
    
    grid.innerHTML = "<div style='color: var(--text-muted);'>Yükleniyor...</div>";
    
    try {
        const res = await fetch(`${API_BASE}/api/v1/social/providers/status`);
        if (!res.ok) throw new Error("API hatası: " + res.status);
        const data = await res.json();
        
        grid.innerHTML = "";
        
        data.providers.forEach(p => {
            const isEnabled = p.enabled;
            const badgeClass = isEnabled ? (p.prototype ? "badge-prototype" : "badge-active") : "badge-disabled";
            const statusText = isEnabled ? (p.prototype ? "Prototype Ready" : "Active") : "Disabled";
            
            let iconSvg = '';
            if (p.platform === "X") {
                iconSvg = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>`;
            } else if (p.platform === "INSTAGRAM") {
                iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>`;
            } else if (p.platform === "FACEBOOK") {
                iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"></path></svg>`;
            } else if (p.platform === "TIKTOK") {
                iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5"></path></svg>`;
            } else {
                iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>`;
            }
            
            let buttonsHtml = `
                <button class="btn btn-ghost" disabled>Bağlantıyı Test Et</button>
                <button class="btn btn-outline" disabled>Ön İzleme</button>
                <button class="btn btn-primary" disabled>İçe Aktar</button>
            `;
            
            if (p.platform === "X" && isEnabled && p.prototype) {
                buttonsHtml = `
                    <button class="btn btn-ghost" onclick="previewXPrototype(this)">Bağlantıyı Test Et</button>
                    <button class="btn btn-outline" onclick="previewXPrototype(this)">Ön İzleme</button>
                    <button id="btn-import-x" class="btn btn-primary" onclick="importXPrototype()" disabled>İçe Aktar</button>
                `;
            }

            const methodStr = p.prototype ? 'Free Web Discovery' : 'Resmi API';
            const statusStr = isEnabled ? (p.prototype ? 'Beklemede' : 'Aktif') : 'Devre Dışı';
            
            grid.innerHTML += `
                <div class="social-card">
                    <div class="social-card-header">
                        <div class="social-card-icon">
                            ${iconSvg}
                            <h4 class="social-card-title">${p.platform}</h4>
                        </div>
                        <span class="status-badge ${badgeClass}">${statusText}</span>
                    </div>
                    
                    <div class="social-card-body" style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                        <div>
                            <div class="social-metric-label" style="font-size:12px; margin-bottom: 2px;">Yöntem</div>
                            <div class="social-metric-value" style="text-align: left;">${methodStr}</div>
                        </div>
                        <div>
                            <div class="social-metric-label" style="font-size:12px; margin-bottom: 2px;">Durum</div>
                            <div class="social-metric-value" style="text-align: left;">${statusStr}</div>
                        </div>
                        <div>
                            <div class="social-metric-label" style="font-size:12px; margin-bottom: 2px;">Son Senkronizasyon</div>
                            <div class="social-metric-value" style="text-align: left;">-</div>
                        </div>
                        <div>
                            <div class="social-metric-label" style="font-size:12px; margin-bottom: 2px;">Toplanan İçerik</div>
                            <div class="social-metric-value" style="text-align: left;">0</div>
                        </div>
                    </div>
                    
                    <div class="social-card-actions">
                        ${buttonsHtml}
                    </div>
                </div>
            `;
        });
        
        if (data.providers.length === 0) {
            grid.innerHTML = `
                <div style="grid-column: 1 / -1; display:flex; flex-direction:column; align-items:center; justify-content:center; padding: 40px; border: 1px dashed var(--border-color); border-radius: 12px; color: var(--text-muted);">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:12px; opacity: 0.5;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    <div style="font-size: 15px; font-weight: 500;">Henüz içerik bulunamadı</div>
                    <div style="font-size: 13px; margin-top: 4px;">Konfigürasyonları kontrol edin.</div>
                </div>
            `;
        }
        
    } catch (e) {
        grid.innerHTML = `<div style='color: #F87171;'>Sunucuya bağlanılamadı: ${e.message}</div>`;
        console.error("Provider status hatası:", e);
    }
}

let lastPreviewItems = [];

async function previewXPrototype(btnElement) {
    const btnImport = document.getElementById("btn-import-x");
    if (btnImport) btnImport.disabled = true;
    
    let btnPreview = btnElement || document.querySelector("button[onclick^='previewXPrototype']");
    let originalHtml = "Ön İzleme";
    if (btnPreview) {
        originalHtml = btnPreview.innerHTML;
        btnPreview.disabled = true;
        btnPreview.innerHTML = `<span class="spinner" style="margin-right: 8px;"></span> Lütfen bekleyin...`;
    }

    
    try {
        const res = await fetch(`${API_BASE}/api/v1/social/x/prototype/preview`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ max_results_per_query: 5 }) // Small limit for testing
        });
        
        if (!res.ok) {
            const err = await res.json();
            showEnterpriseModal("Hata", "Ön izleme hatası: " + (err.error || res.status));
            return;
        }
        
        const data = await res.json();
        
        if (data.new_count > 0 && data.preview_items && data.preview_items.length > 0) {
            lastPreviewItems = data.preview_items;
            if (btnImport) btnImport.disabled = false;
        }
        
        let statusIcon = '<span class="status-dot status-dot-warning" aria-label="Uyarı"></span>';
        if (data.total_found > 0) statusIcon = '<span class="status-dot status-dot-success" aria-label="Başarılı"></span>';
        if (data.access_status === "UNKNOWN_ERROR" || data.access_status === "CAPTCHA_DETECTED") {
            statusIcon = '<span class="status-dot status-dot-error" aria-label="Hata"></span>';
        }
        
        const htmlContent = `
            <div style="display: flex; flex-direction: column; gap: 12px;">
                <div class="social-metric"><span class="social-metric-label">Durum</span><span class="social-metric-value">${statusIcon} ${data.access_status === "NO_RESULTS" ? "Sonuç bulunamadı" : data.access_status}</span></div>
                <div class="social-metric"><span class="social-metric-label">Aranan sorgu</span><span class="social-metric-value">${data.scanned_queries}</span></div>
                <div class="social-metric"><span class="social-metric-label">Bulunan içerik</span><span class="social-metric-value">${data.total_found + (data.unreadable_count || 0)}</span></div>
                <div class="social-metric"><span class="social-metric-label">Duplicate</span><span class="social-metric-value">${data.duplicate_count}</span></div>
                <div class="social-metric"><span class="social-metric-label">Yeni kayıt</span><span class="social-metric-value">${data.new_count}</span></div>
                ${data.message ? `<div style="margin-top: 12px; padding: 12px; background: #F3F4F6; border-radius: 8px; font-size: 13px;"><strong>Sebep:</strong> ${data.message}</div>` : ''}
            </div>
        `;
        showEnterpriseModal("X Veri Toplama Sonucu", htmlContent, false, btnElement);
        
    } catch(e) {
        showEnterpriseModal("Hata", `Bağlantı hatası: ${e.message}`, false, btnElement);
    } finally {
        if(btnPreview) {
            btnPreview.disabled = false;
            btnPreview.innerHTML = originalHtml;
        }
    }
}

async function importXPrototype() {
    const btnImport = document.getElementById("btn-import-x");
    if (!lastPreviewItems || lastPreviewItems.length === 0) {
        showEnterpriseModal("Bilgi", "Aktarılacak yeni kayıt yok.", false, btnImport);
        return;
    }
    
    const originalHtml = btnImport.innerHTML;
    btnImport.disabled = true;
    btnImport.innerHTML = `<span class="spinner" style="margin-right: 8px;"></span> Aktarılıyor...`;
    
    try {
        const res = await fetch(`${API_BASE}/api/v1/social/x/prototype/import`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ items: lastPreviewItems })
        });
        
        const data = await res.json();
        if (res.ok) {
            showEnterpriseModal("Başarılı", `<div style="text-align:center; padding: 20px;"><svg style="color: #16A34A; width: 48px; height: 48px; margin-bottom: 12px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg><div>${data.message}</div></div>`, false, btnImport);
            lastPreviewItems = [];
        } else {
            showEnterpriseModal("Hata", "Aktarma hatası: " + data.error, false, btnImport);
            btnImport.disabled = false;
        }
    } catch(e) {
        showEnterpriseModal("Hata", "Bağlantı hatası: " + e.message, false, btnImport);
        btnImport.disabled = false;
    } finally {
        btnImport.innerHTML = originalHtml;
    }
}

let lastFocusedElement = null;

function showEnterpriseModal(title, htmlContent, showCancel = false, triggerElement = null) {
    const modal = document.getElementById("enterprise-alert-modal");
    if (!modal) return;
    
    if (triggerElement) {
        lastFocusedElement = triggerElement;
    } else {
        lastFocusedElement = document.activeElement;
    }
    
    document.getElementById("ea-title").innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
        <span>${title}</span>
    `;
    document.getElementById("ea-body").innerHTML = htmlContent;
    
    const cancelBtn = document.getElementById("ea-cancel-btn");
    if (showCancel) {
        cancelBtn.style.display = "inline-block";
    } else {
        cancelBtn.style.display = "none";
    }
    
    modal.classList.remove("hidden");
    
    const okBtn = document.getElementById("ea-ok-btn");
    if(okBtn) okBtn.focus();
    
    const escListener = (e) => {
        if (e.key === "Escape") {
            closeEnterpriseModal();
            document.removeEventListener("keydown", escListener);
        }
    };
    document.addEventListener("keydown", escListener);
    
    modal.onclick = (e) => {
        if (e.target === modal) {
            closeEnterpriseModal();
        }
    };
}

function closeEnterpriseModal() {
    const modal = document.getElementById("enterprise-alert-modal");
    if (modal) {
        modal.classList.add("hidden");
        modal.onclick = null;
    }
    if (lastFocusedElement) {
        lastFocusedElement.focus();
        lastFocusedElement = null;
    }
}
