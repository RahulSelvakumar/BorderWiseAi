-- BorderWise AI: Customs Tariff, Valuation & Regulatory Database Schema
-- Conforms to Customs Tariff Act, 1975 & Central Board of Indirect Taxes and Customs (CBIC)

CREATE TABLE IF NOT EXISTS tariffs (
    hs_code TEXT PRIMARY KEY,               -- 8-digit tariff code, e.g., '84716040'
    chapter INTEGER NOT NULL,               -- 2-digit chapter, e.g., 84
    heading TEXT NOT NULL,                  -- 4-digit heading, e.g., '8471'
    subheading TEXT NOT NULL,               -- 6-digit subheading, e.g., '847160'
    description TEXT NOT NULL,              -- Statutory description
    standard_bcd REAL NOT NULL,             -- Standard Basic Customs Duty rate (e.g., 0.10 for 10%)
    effective_bcd REAL NOT NULL,            -- Effective BCD after notifications (e.g., 0.00)
    exemption_notification TEXT,            -- Applicable gazette notification (e.g., 'Notif 24/2005-Cus')
    igst_rate REAL NOT NULL DEFAULT 0.18,   -- Integrated GST rate (e.g., 0.18 for 18%)
    sws_rate REAL NOT NULL DEFAULT 0.10,    -- Social Welfare Surcharge (10% of BCD)
    import_policy TEXT NOT NULL DEFAULT 'FREE', -- 'FREE', 'RESTRICTED', 'PROHIBITED'
    unit TEXT DEFAULT 'u'                   -- Standard unit of measurement (u, kg, etc.)
);

CREATE INDEX IF NOT EXISTS idx_tariffs_heading ON tariffs(heading);
CREATE INDEX IF NOT EXISTS idx_tariffs_chapter ON tariffs(chapter);

CREATE TABLE IF NOT EXISTS exchange_rates (
    currency TEXT PRIMARY KEY,              -- 'USD', 'JPY', 'EUR', 'GBP', 'SGD', 'AUD', 'CNY'
    rate_inr REAL NOT NULL,                 -- Conversion rate to INR
    effective_date DATE NOT NULL,           -- CBIC notified date
    notification_no TEXT NOT NULL           -- CBIC exchange rate gazette notification
);

CREATE TABLE IF NOT EXISTS exemption_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_no TEXT NOT NULL,
    sl_no TEXT NOT NULL,
    hs_code TEXT NOT NULL,
    effective_bcd REAL NOT NULL,
    conditions TEXT,
    statutory_authority TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS regulatory_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,                 -- 'wireless', 'it_electronics', 'batteries', 'drones'
    keyword_patterns TEXT NOT NULL,         -- JSON array of keywords, e.g. '["bluetooth", "2.4ghz", "wifi"]'
    wpc_required BOOLEAN NOT NULL DEFAULT 0,
    bis_required BOOLEAN NOT NULL DEFAULT 0,
    epr_required BOOLEAN NOT NULL DEFAULT 0,
    policy_status TEXT NOT NULL DEFAULT 'FREE', -- 'FREE', 'RESTRICTED', 'PROHIBITED'
    advisory_note TEXT NOT NULL,
    personal_exemption_note TEXT
);

CREATE TABLE IF NOT EXISTS domestic_price_benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_keywords TEXT NOT NULL,
    domestic_asin TEXT,
    domestic_merchant TEXT NOT NULL DEFAULT 'Amazon India',
    domestic_price_inr REAL NOT NULL,
    delivery_days_domestic INTEGER DEFAULT 2,
    warranty_type TEXT DEFAULT 'Authorized Indian Domestic Warranty'
);
