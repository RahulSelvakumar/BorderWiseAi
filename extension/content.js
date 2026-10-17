/**
 * BorderWise AI: Content Script (DOM Product Extractor)
 * Runs client-side inside the user's active browser tab.
 * Zero-scraping approach: Extracts visible product specs without triggering bot-detection WAFs.
 */

function extractProductMetadata() {
  const host = window.location.hostname;
  let title = "";
  let price = 0;
  let currency = "USD";
  let specs = "";
  let shipping = 0;
  let importCharges = 0;

  // 1. Amazon Extractor (Amazon US, JP, UK, DE)
  if (host.includes("amazon.")) {
    // Robust Title Extraction
    const titleEl = document.getElementById("productTitle") ||
                    document.getElementById("title") ||
                    document.querySelector("#productTitle") ||
                    document.querySelector("h1#title") ||
                    document.querySelector("#titleSection h1") ||
                    document.querySelector("h1.a-size-large") ||
                    document.querySelector("h1");
    if (titleEl) {
      title = titleEl.innerText.trim();
    }
    if (!title && document.title) {
      title = document.title
        .replace(/^Amazon\.[a-z.]+: /i, "")
        .replace(/Amazon\.com:\s*/i, "")
        .replace(/- Amazon\.[a-z.]+$/i, "")
        .trim();
    }

    // A. Check for Amazon Shipping & Fee Details table first (most authoritative on landed import fees)
    const feeTableEl = document.getElementById("amazonGlobal_feature_div") || 
                       document.getElementById("agsShippingAndIfdInsideBuyBox") ||
                       document.getElementById("spc-orders") ||
                       document.querySelector(".shipping-fee-details") ||
                       document.getElementById("exports_desktop_qualifiedBuybox_tlc_feature_div");
    if (feeTableEl) {
      const feeText = feeTableEl.innerText;
      // Price inside fee table: "Price $1,059.99"
      const pMatch = feeText.match(/(?:Price|List\s*Price|Item\s*Price|Items)\s*[:\s]*([\$£€¥₹￥]\s*[\d,]+(?:\.\d{2})?)/i);
      if (pMatch) {
        price = parseFloat(pMatch[1].replace(/[^0-9.]/g, "")) || price;
      }
      // Shipping inside fee table: "AmazonGlobal Shipping $13.30"
      const sMatch = feeText.match(/(?:AmazonGlobal\s+Shipping|Shipping\s*(?:&|and)?\s*Fee|Shipping\s*Cost|Delivery\s*Cost|Shipping|Delivery)\s*[:\s]*([\$£€¥₹￥]\s*[\d,]+(?:\.\d{2})?)/i);
      if (sMatch) {
        shipping = parseFloat(sMatch[1].replace(/[^0-9.]/g, "")) || shipping;
      }
      // Estimated Import Charges / Deposit: "Estimated Import Charges $537.36"
      const iMatch = feeText.match(/(?:Estimated\s+Import\s+Charges|Import\s+Fees\s+Deposit|Import\s+Charges)\s*[:\s]*([\$£€¥₹￥]\s*[\d,]+(?:\.\d{2})?)/i);
      if (iMatch) {
        importCharges = parseFloat(iMatch[1].replace(/[^0-9.]/g, "")) || importCharges;
      }
    }

    // B. Main buybox price extraction if not already set from fee table
    if (!price || price === 0) {
      const priceEl = document.querySelector("#corePriceDisplay_desktop_feature_div .priceToPay .a-offscreen") ||
                      document.querySelector("#corePriceDisplay_desktop_feature_div .a-price.aok-align-center .a-offscreen") ||
                      document.querySelector("#corePriceDisplay_desktop_feature_div .a-price .a-offscreen") ||
                      document.querySelector("#corePrice_desktop .priceToPay .a-offscreen") ||
                      document.querySelector("#corePrice_desktop .a-offscreen") ||
                      document.querySelector("#apex_desktop .priceToPay .a-offscreen") ||
                      document.querySelector("#apex_desktop .a-offscreen") ||
                      document.querySelector(".apexPriceToPay .a-offscreen") ||
                      document.getElementById("price_inside_buybox") ||
                      document.getElementById("newBuyBoxPrice") ||
                      document.querySelector("#buyNewSection .a-price .a-offscreen") ||
                      document.getElementById("priceblock_ourprice") || 
                      document.getElementById("priceblock_dealprice") ||
                      document.querySelector("#centerCol .a-price .a-offscreen") ||
                      document.querySelector("#desktop_buybox .a-price .a-offscreen") ||
                      document.querySelector(".a-price .a-offscreen");
      if (priceEl) {
        const priceText = priceEl.innerText.trim();
        price = parseFloat(priceText.replace(/[^0-9.]/g, "")) || 0;
        if (priceText.startsWith("$")) currency = "USD";
        else if (priceText.includes("￥") || host.includes(".co.jp")) currency = "JPY";
        else if (priceText.includes("£")) currency = "GBP";
        else if (priceText.includes("€")) currency = "EUR";
      }

      // Check whole + fraction spans if offscreen text didn't resolve
      if (price === 0) {
        const wholeEl = document.querySelector("#corePriceDisplay_desktop_feature_div .a-price-whole") ||
                        document.querySelector("#apex_desktop .a-price-whole") ||
                        document.querySelector("#centerCol .a-price-whole");
        const fracEl = document.querySelector("#corePriceDisplay_desktop_feature_div .a-price-fraction") ||
                       document.querySelector("#apex_desktop .a-price-fraction") ||
                       document.querySelector("#centerCol .a-price-fraction");
        if (wholeEl) {
          const w = wholeEl.innerText.replace(/[^0-9]/g, "");
          const f = fracEl ? fracEl.innerText.replace(/[^0-9]/g, "") : "00";
          if (w) price = parseFloat(`${w}.${f}`) || 0;
        }
      }
    }

    // C. Shipping extraction if not already set from fee table
    if (shipping === 0) {
      const delivEl = document.getElementById("deliveryBlockMessage") || 
                      document.getElementById("mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE") ||
                      document.getElementById("mir-layout-DELIVERY_BLOCK-slot-DELIVERY_MESSAGE") ||
                      document.getElementById("delivery-message") ||
                      document.getElementById("exports_desktop_qualifiedBuybox_tlc_feature_div");
      if (delivEl) {
        const delivText = delivEl.innerText;
        if (/FREE\s+Shipping|Free\s+Delivery|free\s+international\s+delivery/i.test(delivText)) {
          shipping = 0.0;
        } else {
          const sMatch = delivText.match(/(?:AmazonGlobal\s+Shipping|Shipping\s*(?:&|and)?\s*Fee|Shipping\s*Cost|Delivery\s*Cost|Shipping|Delivery)\s*[:\s]*([\$£€¥₹￥]\s*[\d,]+(?:\.\d{2})?)/i) ||
                         delivText.match(/([\$£€¥₹￥]\s*[\d,]+(?:\.\d{2})?)\s*(?:AmazonGlobal\s+Shipping|Shipping|Delivery)/i);
          if (sMatch) {
            shipping = parseFloat(sMatch[1].replace(/[^0-9.]/g, "")) || 0;
          }
        }
        // Also check if delivery block has import charges
        if (importCharges === 0) {
          const iMatch = delivText.match(/(?:Estimated\s+Import\s+Charges|Import\s+Fees\s+Deposit|Import\s+Charges)\s*[:\s]*([\$£€¥₹￥]\s*[\d,]+(?:\.\d{2})?)/i) ||
                         delivText.match(/([\$£€¥₹￥]\s*[\d,]+(?:\.\d{2})?)\s*(?:Estimated\s+Import\s+Charges|Import\s+Fees\s+Deposit|Import\s+Charges)/i);
          if (iMatch) {
            importCharges = parseFloat(iMatch[1].replace(/[^0-9.]/g, "")) || 0;
          }
        }
      }
    }

    // D. Full centerCol / buybox scan fallback if still missing
    if (price === 0 || shipping === 0) {
      const centerCol = document.getElementById("centerCol") || document.getElementById("desktop_buybox") || document.body;
      const textToScan = centerCol ? centerCol.innerText : "";
      if (price === 0) {
        const pMatch = textToScan.match(/(?:Price|List\s*Price|Item\s*Price)\s*[:\s]*([\$£€¥₹￥]\s*[\d,]+(?:\.\d{2})?)/i);
        if (pMatch) price = parseFloat(pMatch[1].replace(/[^0-9.]/g, "")) || 0;
      }
      if (shipping === 0) {
        const sMatch = textToScan.match(/(?:AmazonGlobal\s+Shipping|Shipping\s*(?:&|and)?\s*Fee|Shipping\s*Cost|Delivery\s*Cost)\s*[:\s]*([\$£€¥₹￥]\s*[\d,]+(?:\.\d{2})?)/i);
        if (sMatch) shipping = parseFloat(sMatch[1].replace(/[^0-9.]/g, "")) || 0;
      }
      if (importCharges === 0) {
        const iMatch = textToScan.match(/(?:Estimated\s+Import\s+Charges|Import\s+Fees\s+Deposit|Import\s+Charges)\s*[:\s]*([\$£€¥₹￥]\s*[\d,]+(?:\.\d{2})?)/i);
        if (iMatch) importCharges = parseFloat(iMatch[1].replace(/[^0-9.]/g, "")) || 0;
      }
    }

    // Technical specifications & feature bullets
    const bulletsEl = document.getElementById("feature-bullets");
    const techTable = document.getElementById("productDetails_techSpec_section_1") || 
                      document.getElementById("technicalSpecifications_section_1") ||
                      document.getElementById("prodDetails");
    const overviewTable = document.getElementById("poExpander") || document.querySelector(".product-overview-table");
    
    let bulletText = bulletsEl ? bulletsEl.innerText.replace(/\s+/g, " ").trim() : "";
    let tableText = techTable ? techTable.innerText.replace(/\s+/g, " ").trim() : "";
    let overviewText = overviewTable ? overviewTable.innerText.replace(/\s+/g, " ").trim() : "";
    specs = `${bulletText} ${overviewText} ${tableText}`.trim().slice(0, 3000);
  }

  // 2. AliExpress Extractor
  else if (host.includes("aliexpress.")) {
    const titleEl = document.querySelector("h1[data-pl='product-title']") || 
                    document.querySelector("h1.product-title-text") ||
                    document.querySelector("h1");
    if (titleEl) title = titleEl.innerText.trim();

    // Try JSON-LD first
    try {
      const ldScripts = document.querySelectorAll("script[type='application/ld+json']");
      for (const s of ldScripts) {
        const text = s.innerText.trim();
        if (text.includes('"Product"') || text.includes('"Offer"')) {
          const data = JSON.parse(text);
          const prodObj = Array.isArray(data) ? data.find(d => d && d["@type"] === "Product") : (data && data["@type"] === "Product" ? data : null);
          if (prodObj) {
            if (!title && prodObj.name) title = prodObj.name.trim();
            if (prodObj.offers) {
              const offer = Array.isArray(prodObj.offers) ? prodObj.offers[0] : prodObj.offers;
              const p = offer.price || offer.lowPrice;
              if (p) price = parseFloat(String(p).replace(/[^0-9.]/g, "")) || price;
              if (offer.priceCurrency) currency = offer.priceCurrency.toUpperCase();
            }
          }
        }
      }
    } catch (e) {}

    if (price === 0) {
      const priceEl = document.querySelector(".product-price-value") || 
                      document.querySelector(".product-price-current") ||
                      document.querySelector("[class*='product-price']") ||
                      document.querySelector("[class*='price--currentPrice']");
      if (priceEl) {
        const pText = priceEl.innerText;
        price = parseFloat(pText.replace(/[^0-9.]/g, "")) || 0;
        if (pText.includes("₹")) currency = "INR";
        else if (pText.includes("€")) currency = "EUR";
        else if (pText.includes("£")) currency = "GBP";
        else if (pText.includes("¥")) currency = "JPY";
        else currency = "USD";
      }
    }

    const descEl = document.querySelector("#product-description") || document.querySelector(".specification--wrapper");
    if (descEl) specs = descEl.innerText.slice(0, 2500);
  }

  // 3. Alibaba Wholesale Extractor
  else if (host.includes("alibaba.")) {
    // Title
    const titleEl = document.querySelector("h1.product-title") || 
                    document.querySelector("h1[data-role='title']") ||
                    document.querySelector(".product-title") ||
                    document.querySelector(".title--title--text") ||
                    document.querySelector(".header-title") ||
                    document.querySelector("h1");
    if (titleEl) {
      title = titleEl.innerText.trim();
    } else {
      const ogTitle = document.querySelector("meta[property='og:title']");
      if (ogTitle) title = ogTitle.content.split(" - ")[0].trim();
    }

    // A. Parse JSON-LD Structured Data first (authoritative on Alibaba)
    try {
      const ldScripts = document.querySelectorAll("script[type='application/ld+json']");
      for (const s of ldScripts) {
        const text = s.innerText.trim();
        if (text.includes('"Product"') || text.includes('"Offer"') || text.includes('"AggregateOffer"')) {
          const data = JSON.parse(text);
          let prodObj = null;
          if (Array.isArray(data)) {
            prodObj = data.find(d => d && (d["@type"] === "Product" || d["@type"] === "Offer"));
          } else if (data && data["@graph"] && Array.isArray(data["@graph"])) {
            prodObj = data["@graph"].find(d => d && (d["@type"] === "Product" || d["@type"] === "Offer"));
          } else if (data && (data["@type"] === "Product" || data["@type"] === "Offer")) {
            prodObj = data;
          }

          if (prodObj) {
            if (!title && prodObj.name) title = prodObj.name.trim();
            const offers = prodObj.offers || prodObj;
            if (offers) {
              const offerObj = Array.isArray(offers) ? offers[0] : offers;
              const rawP = offerObj.lowPrice || offerObj.price || offerObj.highPrice;
              if (rawP) {
                const parsed = parseFloat(String(rawP).replace(/[^0-9.]/g, ""));
                if (!isNaN(parsed) && parsed > 0) price = parsed;
              }
              if (offerObj.priceCurrency) {
                currency = offerObj.priceCurrency.toUpperCase();
              }
            }
          }
        }
      }
    } catch (e) {}

    // B. Check OpenGraph / Product Meta tags if price still 0
    if (price === 0) {
      const ogPrice = document.querySelector("meta[property='product:price:amount']") || 
                      document.querySelector("meta[property='og:price:amount']");
      const ogCurr = document.querySelector("meta[property='product:price:currency']") || 
                     document.querySelector("meta[property='og:price:currency']");
      if (ogPrice && ogPrice.content) {
        const parsed = parseFloat(ogPrice.content.replace(/[^0-9.]/g, ""));
        if (!isNaN(parsed) && parsed > 0) price = parsed;
      }
      if (ogCurr && ogCurr.content) {
        currency = ogCurr.content.toUpperCase();
      }
    }

    // C. Dedicated Price Elements & Currency-Anchored Regex (avoids matching MOQ "10 pieces")
    if (price === 0) {
      const priceContainers = [
        document.querySelector(".price-item .price"),
        document.querySelector(".price-item .num"),
        document.querySelector(".module-price .price"),
        document.querySelector(".module-price .num"),
        document.querySelector(".val-price"),
        document.querySelector(".price-wrap .num"),
        document.querySelector(".price-list .price"),
        document.querySelector(".price-item"),
        document.querySelector(".module-price"),
        document.querySelector(".product-price"),
        document.querySelector(".promotion-price"),
        document.querySelector("[data-role='price']"),
        document.querySelector(".price-wrap"),
        document.querySelector(".normal-price"),
        document.querySelector(".price")
      ];

      for (const el of priceContainers) {
        if (!el) continue;
        const pText = el.innerText.trim();
        if (!pText) continue;

        // Detect currency
        if (pText.includes("₹") || /INR|Rs\.?/i.test(pText)) currency = "INR";
        else if (pText.includes("€") || /EUR/i.test(pText)) currency = "EUR";
        else if (pText.includes("£") || /GBP/i.test(pText)) currency = "GBP";
        else if (pText.includes("¥") || pText.includes("￥") || /CNY|RMB/i.test(pText)) currency = "CNY";
        else if (pText.includes("$") || /USD|US\s*\$/i.test(pText)) currency = "USD";

        // Regex 1: Explicit currency symbol preceding number: "$15.00", "US $2.50", "₹1,250.00"
        const mCurr = pText.match(/(?:US\s*\$|USD|\$|₹|INR|Rs\.?|€|£|¥|￥)\s*([\d,]+(?:\.\d{2})?)/i);
        if (mCurr) {
          const val = parseFloat(mCurr[1].replace(/,/g, ""));
          if (!isNaN(val) && val > 0) {
            price = val;
            break;
          }
        }

        // Regex 2: Number followed by unit: "15.00 / piece", "2.50 / set" (rejects "10 pieces")
        const mUnit = pText.match(/([\d,]+(?:\.\d{2})?)\s*(?:\/|\s*(?:per|\/)\s*(?:piece|pc|unit|set|pair|carton|meter|kg))/i);
        if (mUnit) {
          const val = parseFloat(mUnit[1].replace(/,/g, ""));
          if (!isNaN(val) && val > 0) {
            price = val;
            break;
          }
        }

        // Regex 3: Decimal number inside a price container whose parent/context has a currency symbol
        const numOnly = pText.replace(/,/g, "").trim();
        if (/^\d+(?:\.\d{1,2})?$/.test(numOnly)) {
          const val = parseFloat(numOnly);
          const parentTxt = el.parentElement ? el.parentElement.innerText : "";
          if (!isNaN(val) && val > 0 && /(?:US\s*\$|USD|\$|₹|INR|Rs\.?|€|£|¥|￥)/i.test(parentTxt)) {
            price = val;
            break;
          }
        }
      }
    }

    // Shipping / Freight
    const shipEl = document.querySelector(".shipping-cost") ||
                   document.querySelector(".freight-cost") ||
                   document.querySelector(".shipping-fee") ||
                   document.querySelector("[class*='shipping-cost']") ||
                   document.querySelector("[class*='freight-cost']") ||
                   document.querySelector("[class*='shipping-price']") ||
                   document.querySelector("[data-role='shipping-price']") ||
                   document.querySelector(".logistics-cost") ||
                   document.querySelector("[class*='logistics-info']");
    if (shipEl) {
      const sText = shipEl.innerText;
      if (/free\s+shipping/i.test(sText)) {
        shipping = 0.0;
      } else {
        const mShip = sText.match(/(?:Shipping|Freight|Logistics|Delivery)?\s*[:\s]*(?:US\s*\$|USD|\$|₹|INR|€|£|¥|￥)?\s*([\d,]+(?:\.\d{2})?)/i) ||
                      sText.match(/(?:US\s*\$|USD|\$|₹|INR|€|£|¥|￥)\s*([\d,]+(?:\.\d{2})?)/i);
        if (mShip) {
          shipping = parseFloat(mShip[1].replace(/,/g, "")) || 0;
        }
      }
    }

    // Specifications & Attributes
    const specEl = document.querySelector(".product-attributes") ||
                   document.querySelector(".spec-list") ||
                   document.querySelector(".do-entry-item") ||
                   document.querySelector(".attribute-list") ||
                   document.querySelector("[class*='attributes']") ||
                   document.querySelector("[class*='attribute-item']") ||
                   document.querySelector("#J-rich-text-description");
    if (specEl) {
      specs = specEl.innerText.replace(/\s+/g, " ").trim().slice(0, 3000);
    }

    // Full-page scan fallback if price or shipping not found
    if (price === 0 || shipping === 0) {
      const bodyText = document.body ? document.body.innerText : "";
      if (price === 0) {
        const pMatch = bodyText.match(/(?:FOB\s*Price|Unit\s*Price|Price)\s*[:\s]*(?:US\s*\$|USD|\$|₹|INR|€|£|¥|￥)\s*([\d,]+(?:\.\d{2})?)/i);
        if (pMatch) price = parseFloat(pMatch[1].replace(/,/g, "")) || 0;
      }
      if (shipping === 0) {
        const sMatch = bodyText.match(/(?:Shipping|Freight|Logistics|Delivery)\s*[:\s]*(?:US\s*\$|USD|\$|₹|INR|€|£|¥|￥)\s*([\d,]+(?:\.\d{2})?)/i);
        if (sMatch) shipping = parseFloat(sMatch[1].replace(/,/g, "")) || 0;
      }
    }
  }

  // 4. Fallback generic meta extractor
  else {
    title = document.title;
    const ogPrice = document.querySelector("meta[property='product:price:amount']");
    const ogCurr = document.querySelector("meta[property='product:price:currency']");
    if (ogPrice) price = parseFloat(ogPrice.content) || 0;
    if (ogCurr) currency = ogCurr.content;
  }

  return {
    url: window.location.href,
    title,
    price,
    currency,
    shipping,
    import_charges: importCharges,
    specs,
    timestamp: Date.now()
  };
}

// Function to send metadata if valid product detected
let lastSentHash = "";
function notifyIfDetected() {
  try {
    const meta = extractProductMetadata();
    // Notify if title is detected (even if price is hydrating, so sidepanel switches away from old product)
    if (meta && meta.title && meta.title.length > 3) {
      const hash = `${window.location.pathname}_${meta.title}_${meta.price}_${meta.shipping}_${meta.import_charges}`;
      if (hash !== lastSentHash) {
        lastSentHash = hash;
        chrome.runtime.sendMessage({
          type: "BORDERWISE_PRODUCT_DETECTED",
          payload: meta
        }).catch(() => {});
      }
    }
  } catch (e) {}
}

// Run immediately and poll during initial dynamic page hydration
notifyIfDetected();
setTimeout(notifyIfDetected, 400);
setTimeout(notifyIfDetected, 1200);
setTimeout(notifyIfDetected, 2500);

// Detect SPA (Single-Page App) URL changes (e.g. clicking different product variants on Amazon)
try {
  const origPush = history.pushState;
  history.pushState = function() {
    origPush.apply(this, arguments);
    setTimeout(notifyIfDetected, 400);
    setTimeout(notifyIfDetected, 1200);
  };
  const origReplace = history.replaceState;
  history.replaceState = function() {
    origReplace.apply(this, arguments);
    setTimeout(notifyIfDetected, 400);
    setTimeout(notifyIfDetected, 1200);
  };
  window.addEventListener("popstate", () => {
    setTimeout(notifyIfDetected, 400);
  });
  window.addEventListener("hashchange", () => {
    setTimeout(notifyIfDetected, 400);
  });
} catch (e) {}

// Observe dynamic DOM changes (e.g. Amazon AJAX buybox loading) with debouncing
try {
  let debounceTimer = null;
  const domObserver = new MutationObserver(() => {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      notifyIfDetected();
    }, 400);
  });
  if (document.body) {
    domObserver.observe(document.body, { childList: true, subtree: true });
  }
} catch (e) {}

// Listen for on-demand fetch requests from sidepanel
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "GET_CURRENT_PRODUCT" || request.type === "RESCAN_PRODUCT") {
    try {
      const meta = extractProductMetadata();
      sendResponse({ success: true, metadata: meta });
    } catch (e) {
      console.warn("Error extracting product metadata:", e);
      sendResponse({ success: false, error: e ? e.message : "Extraction error" });
    }
  }
  return false;
});
