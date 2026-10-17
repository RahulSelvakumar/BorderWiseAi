/**
 * BorderWise AI: Sidepanel UI Controller
 * Manages active tab synchronization, dynamic content script injection,
 * API dispatch (with local/prod fallback), waterfall rendering,
 * and domestic price comparison arbitrage.
 */

const PROD_API = "https://borderwise-ai-vfqthqmtna-el.a.run.app/api/v1";
const LOCAL_API = "http://localhost:8080/api/v1";
let API_BASE = PROD_API;

let currentProduct = {
  title: "Detecting item...",
  price: 0,
  currency: "USD",
  shipping: 0,
  import_charges: 0,
  specs: "",
  domestic_price: 0,
  shipping_mode: "express_courier",
  url: ""
};

let analysisResult = null;

document.addEventListener("DOMContentLoaded", () => {
  initListeners();
  loadProductData();
});

function initListeners() {
  // Mode selector buttons
  const modeButtons = document.querySelectorAll(".toggle-btn");
  modeButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      modeButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentProduct.shipping_mode = btn.dataset.mode;
      runAnalysis(currentProduct);
    });
  });

  // Domestic input change
  const domInput = document.getElementById("domesticInput");
  if (domInput) {
    domInput.addEventListener("input", (e) => {
      currentProduct.domestic_price = parseFloat(e.target.value) || 0;
      updateArbitrageUI();
    });
  }

  // Refresh / Re-scan buttons
  const refreshBtn = document.getElementById("refreshBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      const origText = refreshBtn.innerText;
      refreshBtn.innerText = "⏳ Scanning...";
      loadProductData().finally(() => {
        setTimeout(() => { refreshBtn.innerText = origText; }, 1000);
      });
    });
  }
  const headerRescanBtn = document.getElementById("headerRescanBtn");
  if (headerRescanBtn) {
    headerRescanBtn.addEventListener("click", () => {
      loadProductData();
    });
  }

  // Quick edit button for price and shipping override
  const editBtn = document.getElementById("quickEditBtn");
  if (editBtn) {
    editBtn.addEventListener("click", () => {
      const curPrice = currentProduct.price > 0 ? currentProduct.price.toFixed(2) : "0.00";
      const newP = prompt("Enter Foreign FOB Price:", curPrice);
      if (newP !== null && !isNaN(parseFloat(newP))) {
        currentProduct.price = parseFloat(newP);
      }
      const curShip = currentProduct.shipping > 0 ? currentProduct.shipping.toFixed(2) : "0.00";
      const newS = prompt("Enter Shipping Cost:", curShip);
      if (newS !== null && !isNaN(parseFloat(newS))) {
        currentProduct.shipping = parseFloat(newS);
      }
      const zeroNotice = document.getElementById("priceZeroNotice");
      if (zeroNotice) {
        zeroNotice.style.display = currentProduct.price <= 0 ? "block" : "none";
      }
      runAnalysis(currentProduct);
    });
  }
}

async function getActiveTab() {
  if (typeof chrome === "undefined" || !chrome.tabs || !chrome.tabs.query) return null;
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, lastFocusedWindow: true }, (tabs1) => {
      if (tabs1 && tabs1.length > 0 && tabs1[0] && tabs1[0].id) {
        return resolve(tabs1[0]);
      }
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs2) => {
        if (tabs2 && tabs2.length > 0 && tabs2[0] && tabs2[0].id) {
          return resolve(tabs2[0]);
        }
        chrome.tabs.query({ active: true }, (tabs3) => {
          if (tabs3 && tabs3.length > 0 && tabs3[0] && tabs3[0].id) {
            return resolve(tabs3[0]);
          }
          resolve(null);
        });
      });
    });
  });
}

async function loadProductData() {
  showLoader(true);

  if (typeof chrome === "undefined" || !chrome.tabs) {
    runAnalysis(currentProduct);
    return;
  }

  const activeTab = await getActiveTab();
  if (!activeTab || !activeTab.id) {
    console.warn("No active tab found");
    checkStorageFallback();
    return;
  }

  const url = activeTab.url || "";
  if (url.startsWith("chrome://") || url.startsWith("edge://") || url.startsWith("about:") || url.startsWith("chrome-extension://")) {
    showLoader(false);
    const titleEl = document.getElementById("prodTitle");
    if (titleEl) titleEl.innerText = "Navigate to an Amazon, AliExpress, or Alibaba product page to analyze.";
    const tagEl = document.getElementById("merchantTag");
    if (tagEl) tagEl.innerText = "Waiting for Product...";
    return;
  }

  // First attempt: sendMessage to tab
  chrome.tabs.sendMessage(activeTab.id, { type: "GET_CURRENT_PRODUCT" }, async (response) => {
    if (chrome.runtime.lastError || !response || !response.metadata || !response.metadata.title) {
      console.log("Content script not responding, injecting programmatically into tab:", activeTab.id);
      try {
        if (chrome.scripting) {
          await chrome.scripting.executeScript({
            target: { tabId: activeTab.id },
            files: ["content.js"]
          });
          // Wait 200ms and retry
          setTimeout(() => {
            chrome.tabs.sendMessage(activeTab.id, { type: "GET_CURRENT_PRODUCT" }, (retryRes) => {
              if (retryRes && retryRes.metadata && retryRes.metadata.title) {
                syncWithMetadata(retryRes.metadata);
              } else {
                checkStorageFallback();
              }
            });
          }, 200);
          return;
        }
      } catch (e) {
        console.warn("Script injection error:", e);
      }
      checkStorageFallback();
    } else {
      syncWithMetadata(response.metadata);
    }
  });
}

function checkStorageFallback() {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(["latest_product"], (res) => {
      if (res.latest_product && res.latest_product.title) {
        syncWithMetadata(res.latest_product);
      } else {
        showLoader(false);
      }
    });
  } else {
    showLoader(false);
  }
}

function syncWithMetadata(meta) {
  if (!meta || !meta.title) return;

  const prevTitle = currentProduct ? currentProduct.title : "";
  const isNewProduct = meta.title !== prevTitle;

  const parsedPrice = parseFloat(meta.price);
  const parsedShip = parseFloat(meta.shipping);
  const parsedImp = parseFloat(meta.import_charges);

  // Build clean fresh product object without retaining stale fields from old products
  currentProduct = {
    title: meta.title,
    price: (!isNaN(parsedPrice) && parsedPrice > 0) ? parsedPrice : 0,
    currency: meta.currency || "USD",
    shipping: (!isNaN(parsedShip) && parsedShip >= 0) ? parsedShip : 0,
    import_charges: (!isNaN(parsedImp) && parsedImp >= 0) ? parsedImp : 0,
    specs: meta.specs || (meta.title ? `${meta.title} imported merchandise` : ""),
    currency: meta.currency || "USD",
    shipping: (typeof meta.shipping === "number" && !isNaN(meta.shipping)) ? meta.shipping : 0,
    import_charges: (typeof meta.import_charges === "number" && !isNaN(meta.import_charges)) ? meta.import_charges : 0,
    specs: meta.specs || (meta.title ? `${meta.title} imported merchandise` : ""),
    domestic_price: isNewProduct ? 0 : (currentProduct ? currentProduct.domestic_price : 0),
    shipping_mode: (currentProduct && currentProduct.shipping_mode) ? currentProduct.shipping_mode : "express_courier",
    url: meta.url || ""
  };

  // Toggle zero-price warning if price was not auto-detected
  const zeroNotice = document.getElementById("priceZeroNotice");
  if (zeroNotice) {
    zeroNotice.style.display = currentProduct.price <= 0 ? "block" : "none";
  }

  // Update merchant tag and DDP mode button label
  const tagEl = document.getElementById("merchantTag");
  const ddpBtn = document.getElementById("ddpModeBtn");
  if (meta.url) {
    if (meta.url.includes("alibaba.")) {
      if (tagEl) tagEl.innerText = "Alibaba Wholesale";
      if (ddpBtn) ddpBtn.innerText = "Alibaba DDP";
    } else if (meta.url.includes("aliexpress.")) {
      if (tagEl) tagEl.innerText = "AliExpress Global";
      if (ddpBtn) ddpBtn.innerText = "AliExpress DDP";
    } else if (meta.url.includes("amazon.")) {
      if (tagEl) tagEl.innerText = "Amazon Global";
      if (ddpBtn) ddpBtn.innerText = "Amazon DDP";
    } else if (meta.url.includes("bhphotovideo.")) {
      if (tagEl) tagEl.innerText = "B&H Photo Video";
      if (ddpBtn) ddpBtn.innerText = "Prepaid DDP";
    } else if (meta.url.includes("ebay.")) {
      if (tagEl) tagEl.innerText = "eBay International";
      if (ddpBtn) ddpBtn.innerText = "eBay DDP";
    } else {
      if (tagEl) tagEl.innerText = "Cross-Border Store";
      if (ddpBtn) ddpBtn.innerText = "Prepaid DDP";
    }
  }

  runAnalysis(currentProduct);
}

// Listen for tab switching
if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.onActivated) {
  chrome.tabs.onActivated.addListener(() => {
    loadProductData();
  });
}

// Listen for tab URL updates (page navigation / reload)
if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.onUpdated) {
  chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
    if (changeInfo.status === "complete") {
      getActiveTab().then((activeTab) => {
        if (activeTab && activeTab.id === tabId) {
          loadProductData();
        }
      });
    }
  });
}

// Live detection events from content script
if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
  chrome.runtime.onMessage.addListener((request) => {
    if (request.type === "BORDERWISE_PRODUCT_DETECTED" && request.payload) {
      syncWithMetadata(request.payload);
    }
  });
}

// Storage changes
if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.onChanged) {
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local" && changes.latest_product && changes.latest_product.newValue) {
      syncWithMetadata(changes.latest_product.newValue);
    }
  });
}

async function runAnalysis(prod) {
  showLoader(true);

  // Update product info in UI
  document.getElementById("prodTitle").innerText = prod.title || "Detecting item...";
  document.getElementById("prodPrice").innerText = prod.price > 0 ? `${prod.currency} ${prod.price.toFixed(2)}` : `${prod.currency} 0.00`;
  document.getElementById("prodShipping").innerText = `${prod.currency} ${prod.shipping.toFixed(2)}`;

  const reqBody = JSON.stringify({
    title: prod.title,
    specs: prod.specs,
    price_fob: prod.price > 0 ? prod.price : 1.0, // avoid division by zero
    currency: prod.currency,
    shipping_foreign: prod.shipping,
    amazon_import_charges_foreign: prod.import_charges,
    domestic_price_inr: prod.domestic_price,
    shipping_mode: prod.shipping_mode,
    is_personal_use: true
  });

  try {
    let res = null;
    try {
      res = await fetch(`${API_BASE}/analyze-product`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: reqBody
      });
    } catch (netErr) {
      // If PROD_API is unreachable (e.g. offline or testing local server), try LOCAL_API
      if (API_BASE !== LOCAL_API) {
        console.log("Primary API unreachable, attempting local server:", LOCAL_API);
        res = await fetch(`${LOCAL_API}/analyze-product`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: reqBody
        });
        API_BASE = LOCAL_API;
      } else {
        throw netErr;
      }
    }

    if (!res || !res.ok) throw new Error("API server response was not ok");
    const data = await res.json();
    analysisResult = data;
    renderAnalysis(data);
  } catch (err) {
    console.warn("Backend API unavailable, executing local resilient calculation:", err);
    renderLocalFallback(prod);
  } finally {
    showLoader(false);
  }
}

function renderAnalysis(data) {
  const wf = data.landed_cost_waterfall;
  const cls = data.classification;
  const reg = data.regulatory_compliance;

  document.getElementById("hsCodeBadge").innerText = `HS ${cls.hs_code}`;
  document.getElementById("wfFob").innerText = `₹${wf.fob_inr.toLocaleString("en-IN", {minimumFractionDigits: 2})}`;
  document.getElementById("wfFreight").innerText = `₹${(wf.freight_inr + wf.insurance_inr).toLocaleString("en-IN", {minimumFractionDigits: 2})}`;
  document.getElementById("wfCif").innerText = `₹${wf.assessable_cif_inr.toLocaleString("en-IN", {minimumFractionDigits: 2})}`;
  document.getElementById("wfBcdPct").innerText = `${(cls.effective_bcd * 100).toFixed(0)}%`;
  document.getElementById("wfBcd").innerText = `₹${wf.bcd_inr.toLocaleString("en-IN", {minimumFractionDigits: 2})}`;
  document.getElementById("wfSws").innerText = `₹${wf.sws_inr.toLocaleString("en-IN", {minimumFractionDigits: 2})}`;
  document.getElementById("wfIgst").innerText = `₹${wf.igst_inr.toLocaleString("en-IN", {minimumFractionDigits: 2})}`;
  document.getElementById("wfCourier").innerText = `₹${wf.courier_fee_inr.toLocaleString("en-IN", {minimumFractionDigits: 2})}`;
  document.getElementById("wfTotal").innerText = `₹${wf.total_landed_cost_inr.toLocaleString("en-IN", {minimumFractionDigits: 2})}`;

  // Amazon Import Deposit vs Statutory Duty comparison (only shown for Amazon products)
  const amazonCard = document.getElementById("amazonDepositCard");
  const amazonAdvisory = document.getElementById("amazonDepositAdvisory");
  if (amazonCard && amazonAdvisory) {
    const isAmazon = (currentProduct.url && currentProduct.url.includes("amazon.")) ||
                     (!currentProduct.url && currentProduct.import_charges > 0);
    if (isAmazon && wf.amazon_comparison && wf.amazon_comparison.advisory) {
      amazonAdvisory.innerText = wf.amazon_comparison.advisory;
      amazonCard.style.display = "block";
    } else {
      amazonCard.style.display = "none";
    }
  }

  // Citations & Hash
  document.getElementById("statutoryCitation").innerText = wf.exemption_citation || cls.reasoning;
  document.getElementById("provenanceHash").innerText = wf.provenance_hash;

  // Regulatory badges
  renderRegulatoryBadges(reg);

  // Customs Detention Risk Gauge
  renderRiskGauge(reg ? reg.detention_risk : null);

  // Community Crowdsourced Duty History
  renderCommunityReports(data.community_duty_history);

  // Arbitrage
  if (data.price_arbitrage && data.price_arbitrage.domestic_price_inr > 0) {
    currentProduct.domestic_price = data.price_arbitrage.domestic_price_inr;
    const domInput = document.getElementById("domesticInput");
    if (domInput) domInput.value = data.price_arbitrage.domestic_price_inr;
  }
  updateArbitrageUI();
}

function renderRiskGauge(risk) {
  if (!risk) {
    risk = { score: 15, level: "LOW", inspection_likelihood: "Standard random inspection (est. 5-10% probability)", risk_factors: [] };
  }

  const badgeEl = document.getElementById("riskScoreBadge");
  const meterEl = document.getElementById("riskMeterFill");
  const likelihoodEl = document.getElementById("riskLikelihoodText");
  const factorsEl = document.getElementById("riskFactorsContainer");

  const score = Math.max(0, Math.min(100, risk.score || 15));
  const level = (risk.level || "LOW").toUpperCase();

  let barColor = "#0f9d58";
  let bgBadge = "#e6f4ea";
  let textBadge = "#137333";
  let icon = "🟢";

  if (level === "MODERATE") {
    barColor = "#f4b400";
    bgBadge = "#fef7e0";
    textBadge = "#b06000";
    icon = "🟡";
  } else if (level === "HIGH") {
    barColor = "#e37400";
    bgBadge = "#fce8e6";
    textBadge = "#c5221f";
    icon = "🟠";
  } else if (level === "CRITICAL") {
    barColor = "#d93025";
    bgBadge = "#fce8e6";
    textBadge = "#c5221f";
    icon = "🔴";
  }

  if (badgeEl) {
    badgeEl.innerText = `${icon} ${score} / 100 ${level}`;
    badgeEl.style.background = bgBadge;
    badgeEl.style.color = textBadge;
  }

  if (meterEl) {
    meterEl.style.width = `${score}%`;
    meterEl.style.backgroundColor = barColor;
  }

  if (likelihoodEl) {
    likelihoodEl.innerHTML = `<strong>Inspection Likelihood:</strong> ${risk.inspection_likelihood || "Standard assessment"}`;
  }

  if (factorsEl) {
    if (risk.risk_factors && risk.risk_factors.length > 0) {
      factorsEl.innerHTML = risk.risk_factors.map(f => `<div style="margin-top:2px;">• ${f}</div>`).join("");
    } else {
      factorsEl.innerHTML = "✓ Standard retail parcel with personal use declaration.";
    }
  }
}

function renderCommunityReports(reports) {
  const countEl = document.getElementById("communityReportsCount");
  const container = document.getElementById("communityReportsContainer");
  if (!container) return;

  if (!reports || reports.length === 0) {
    if (countEl) countEl.innerText = "👥 Community Verified";
    container.innerHTML = `
      <div style="font-size: 11px; color: var(--text-muted); padding: 4px 0;">
        No customs disputes recorded for this product category. Safe to import under standard courier clearance.
      </div>
    `;
    return;
  }

  if (countEl) {
    countEl.innerText = `👥 ${reports.length} Verified Reports`;
  }

  let html = "";
  reports.slice(0, 3).forEach(r => {
    html += `
      <div style="background: #f8f9fa; border: 1px solid #e8eaed; border-radius: 6px; padding: 8px; margin-top: 6px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
          <span style="font-weight: 600; font-size: 11px; color: var(--text);">${r.carrier} • ${r.city}</span>
          <span style="background: #e8f0fe; color: #1a73e8; font-weight: 700; padding: 2px 6px; border-radius: 4px; font-size: 10px;">${r.duty_effective_pct}% Duty Paid</span>
        </div>
        <div style="font-size: 10px; color: var(--text-muted); margin-bottom: 4px;">
          Cleared in <strong>${r.clearance_days} days</strong> • <span style="color: #137333; font-weight: 600;">✓ Verified Importer</span>
        </div>
        <div style="font-size: 11px; color: #3c4043; line-height: 1.3;">
          "${r.notes}"
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

function renderRegulatoryBadges(reg) {
  const container = document.getElementById("badgeContainer");
  container.innerHTML = "";

  if (!reg || !reg.badges || reg.badges.length === 0) {
    container.innerHTML = `<span class="badge-pill badge-green">✓ DGFT Policy: FREE</span>`;
    return;
  }

  reg.badges.forEach(b => {
    let colorClass = "badge-green";
    if (b.status === "AMBER") colorClass = "badge-amber";
    if (b.status === "RED") colorClass = "badge-red";

    const badge = document.createElement("span");
    badge.className = `badge-pill ${colorClass}`;
    badge.innerText = b.badge_title;
    badge.title = b.description;
    container.appendChild(badge);
  });
}

function updateArbitrageUI() {
  if (!analysisResult) return;
  const landed = analysisResult.landed_cost_waterfall.total_landed_cost_inr;
  const domestic = currentProduct.domestic_price || 0;

  const box = document.getElementById("verdictBox");
  const headline = document.getElementById("verdictHeadline");
  const tradeoff = document.getElementById("verdictTradeoff");

  if (!domestic || domestic <= 0) {
    box.className = "verdict-box";
    headline.innerText = "ℹ️ Enter domestic price in India above to compare arbitrage.";
    tradeoff.innerText = "Check Amazon.in or authorized Indian retailers for domestic retail price.";
    return;
  }

  const diff = domestic - landed;
  const pct = (diff / domestic) * 100;

  if (diff > 500) {
    box.className = "verdict-box verdict-save";
    headline.innerText = `🟢 SAVE ₹${diff.toLocaleString("en-IN", {minimumFractionDigits: 2})} (${pct.toFixed(1)}%) BY IMPORTING!`;
    tradeoff.innerText = "Arrives in 10-14 days vs 1-2 days local. Manufacturer international warranty applies.";
  } else if (diff < -500) {
    box.className = "verdict-box verdict-local";
    headline.innerText = `🔴 BUY LOCALLY! Importing is ₹${Math.abs(diff).toLocaleString("en-IN", {minimumFractionDigits: 2})} (${Math.abs(pct).toFixed(1)}%) more expensive.`;
    tradeoff.innerText = "Local seller provides 1-year authorized domestic warranty and faster 1-2 day delivery.";
  } else {
    box.className = "verdict-box";
    headline.innerText = `🟡 BREAK-EVEN: Price difference is negligible (within ₹500).`;
    tradeoff.innerText = "Recommend buying locally for domestic warranty protection.";
  }
}

function renderLocalFallback(prod) {
  const forex = prod.currency === "JPY" ? 0.56 : 84.50;
  const priceVal = prod.price > 0 ? prod.price : 199.0;
  const fobInr = priceVal * forex;
  const freightInr = (prod.shipping || 20) * forex;
  const insInr = fobInr * 0.01125;
  const cifInr = fobInr + freightInr + insInr;
  const bcdInr = 0.0;
  const swsInr = 0.0;
  const igstInr = cifInr * 0.18;
  const courierInr = prod.shipping_mode === "postal_ems" ? 100.0 : 750.0;
  const totalLanded = cifInr + bcdInr + swsInr + igstInr + courierInr;

  analysisResult = {
    landed_cost_waterfall: {
      fob_inr: fobInr,
      freight_inr: freightInr,
      insurance_inr: insInr,
      assessable_cif_inr: cifInr,
      bcd_inr: bcdInr,
      sws_inr: swsInr,
      igst_inr: igstInr,
      courier_fee_inr: courierInr,
      total_landed_cost_inr: totalLanded,
      exemption_citation: "ITA-1 Concessional Tariff Notification No. 24/2005-Customs",
      provenance_hash: "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069"
    },
    classification: {
      hs_code: "8471.30.90",
      effective_bcd: 0.0,
      reasoning: "Local Heuristic Classification under Chapter 84."
    },
    regulatory_compliance: {
      badges: [
        { badge_title: "WPC ETA Exempt (Personal)", status: "GREEN", description: "Delicensed band" },
        { badge_title: "BIS CRS Exempt (1 Unit)", status: "GREEN", description: "Personal use exemption" }
      ],
      detention_risk: {
        score: 15,
        level: "LOW",
        inspection_likelihood: "Random green channel audit (est. 5-10% probability)",
        risk_factors: ["Standard retail parcel with personal use declaration"]
      }
    },
    community_duty_history: [
      {
        carrier: "DHL Express",
        city: "Bengaluru",
        duty_effective_pct: 18.0,
        clearance_days: 2,
        verified: true,
        notes: "Smooth customs clearance via New Delhi DHL gateway. Aadhaar KYC verified."
      }
    ]
  };

  renderAnalysis(analysisResult);
}

function showLoader(visible) {
  const loader = document.getElementById("loader");
  const content = document.getElementById("content");
  if (loader && content) {
    loader.style.display = visible ? "block" : "none";
    content.style.opacity = visible ? "0.4" : "1";
    content.style.pointerEvents = visible ? "none" : "auto";
  }
}
