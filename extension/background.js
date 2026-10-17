/**
 * BorderWise AI: Service Worker (background.js)
 * Manages sidePanel lifecycle, active tab tracking, content script injection,
 * and cross-tab product metadata broadcasting.
 */

const SUPPORTED_PATTERNS = [
  "*://*.amazon.com/*",
  "*://*.amazon.in/*",
  "*://*.amazon.co.jp/*",
  "*://*.amazon.co.uk/*",
  "*://*.amazon.de/*",
  "*://*.amazon.ca/*",
  "*://*.amazon.com.au/*",
  "*://*.amazon.fr/*",
  "*://*.amazon.es/*",
  "*://*.amazon.it/*",
  "*://*.amazon.sg/*",
  "*://*.alibaba.com/*",
  "*://*.aliexpress.com/*",
  "*://*.aliexpress.us/*",
  "*://*.bhphotovideo.com/*",
  "*://*.ebay.com/*"
];

function isSupportedUrl(url) {
  if (!url) return false;
  return /amazon\.|alibaba\.|aliexpress\.|bhphotovideo\.|ebay\./i.test(url);
}

// Auto-open sidepanel on action click and inject into existing tabs on install/update
chrome.runtime.onInstalled.addListener(async () => {
  console.log("BorderWise AI Chrome Extension Installed / Updated.");
  try {
    await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  } catch (e) {
    console.debug("sidePanel.setPanelBehavior error:", e);
  }

  // Programmatically inject content.js into all existing matching tabs
  try {
    const tabs = await chrome.tabs.query({ url: SUPPORTED_PATTERNS });
    for (const tab of tabs) {
      if (tab.id && tab.url && isSupportedUrl(tab.url)) {
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ["content.js"]
        }).catch(err => console.debug("Script injection on install skipped for tab:", tab.id, err));
      }
    }
  } catch (err) {
    console.debug("Could not query tabs on install:", err);
  }
});

// Broadcast tab changes when user switches active tabs
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (tab && tab.url && isSupportedUrl(tab.url)) {
      chrome.tabs.sendMessage(tab.id, { type: "GET_CURRENT_PRODUCT" }, (res) => {
        if (chrome.runtime.lastError) {
          // Tab existed before extension install, inject content script now
          chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ["content.js"]
          }).catch(() => {});
        } else if (res && res.metadata && res.metadata.title) {
          chrome.storage.local.set({ "latest_product": res.metadata });
        }
      });
    }
  } catch (e) {
    console.debug("onActivated error:", e);
  }
});

// Broadcast when a tab finishes loading or URL changes
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab && tab.url && isSupportedUrl(tab.url)) {
    chrome.tabs.sendMessage(tabId, { type: "GET_CURRENT_PRODUCT" }, (res) => {
      if (chrome.runtime.lastError) {
        chrome.scripting.executeScript({
          target: { tabId: tabId },
          files: ["content.js"]
        }).catch(() => {});
      } else if (res && res.metadata && res.metadata.title) {
        chrome.storage.local.set({ "latest_product": res.metadata });
      }
    });
  }
});

// Handle messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "BORDERWISE_PRODUCT_DETECTED" && message.payload) {
    // Cache current product to storage
    chrome.storage.local.set({ "latest_product": message.payload }, () => {
      console.log("Cached product for sidepanel:", message.payload.title);
    });
    sendResponse({ received: true });
  }
  return true;
});
