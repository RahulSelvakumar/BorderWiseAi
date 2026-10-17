"""
Unit tests for FastAPI endpoints in backend/api/main.py
"""

from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)

def test_root_serves_web_app():
    response = client.get("/")
    assert response.status_code == 200
    assert "BorderWise AI" in response.text
    assert "Customs Act Sec 14" in response.text

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["statutory_tariff_lines"] > 6000

def test_exchange_rates_endpoint():
    response = client.get("/api/v1/exchange-rates")
    assert response.status_code == 200
    data = response.json()
    assert len(data["rates"]) >= 5
    currencies = [r["currency"] for r in data["rates"]]
    assert "USD" in currencies
    assert "JPY" in currencies

def test_tariff_search_endpoint():
    response = client.get("/api/v1/tariffs/search?q=keyboard")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] > 0
    assert any("8471" in r["hs_code"] for r in data["results"])

def test_analyze_product_endpoint():
    payload = {
        "title": "Keychron Q1 Pro Wireless Mechanical Keyboard",
        "specs": "Bluetooth 5.1, Hot-swappable, CNC aluminum body",
        "price_fob": 199.00,
        "currency": "USD",
        "shipping_foreign": 22.00,
        "domestic_price_inr": 26999.00,
        "shipping_mode": "express_courier",
        "is_personal_use": True
    }
    response = client.post("/api/v1/analyze-product", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "8471" in data["classification"]["hs_code"]
    assert data["landed_cost_waterfall"]["assessable_cif_inr"] > 18000
    assert data["regulatory_compliance"]["overall_status"] == "GREEN"
    assert data["price_arbitrage"]["verdict"] == "SAVE_BY_IMPORTING"
    assert data["performance"]["latency_ms"] < 10000

def test_extract_url_endpoint():
    response = client.post("/api/v1/extract-url", json={"url": "https://www.amazon.com/dp/B0BY2T5T7F/keychron-q1-pro"})
    assert response.status_code == 200
    data = response.json()
    assert "Keychron" in data["title"]
    assert data["currency"] == "USD"
    assert data["price"] > 0
    assert data["shipping"] > 0

def test_extract_fee_breakdown_text():
    sample_text = """
    Shipping & Fee Details
    Price        $1,059.99
    AmazonGlobal Shipping        $13.30
    Estimated Import Charges        $461.04
    Total        $1,534.33
    """
    response = client.post("/api/v1/extract-url", json={"url": sample_text})
    assert response.status_code == 200
    data = response.json()
    assert data["price"] == 1059.99
    assert data["shipping"] == 13.30
    assert data["currency"] == "USD"

def test_extract_macbook_laptop_url():
    url = "https://www.amazon.com/Apple-2024-MacBook-13-inch-256GB/dp/B0CX237P6F"
    response = client.post("/api/v1/extract-url", json={"url": url})
    assert response.status_code == 200
    data = response.json()
    assert data["price"] == 1059.99
    assert data["shipping"] == 13.30

def test_extract_amazon_asin_url():
    url = "https://www.amazon.com/dp/B0CX23727K"
    response = client.post("/api/v1/extract-url", json={"url": url})
    assert response.status_code == 200
    data = response.json()
    assert data["price"] == 1059.99
    assert data["shipping"] == 13.30
    assert "MacBook" in data["title"]

def test_extract_alibaba_url():
    url = "https://www.alibaba.com/product-detail/Custom-Wholesale-Mechanical-Keyboard-CNC-Case_1600123456789.html"
    response = client.post("/api/v1/extract-url", json={"url": url})
    assert response.status_code == 200
    data = response.json()
    assert "Mechanical Keyboard" in data["title"]
    assert data["currency"] == "USD"

def test_extract_asus_rog_strix_laptop_url():
    url = "https://www.amazon.com/ASUS-Strix-Gaming-Laptop-Nebula/dp/B0DW1ZPQXX/ref=sr_1_5?keywords=gaming+laptop"
    response = client.post("/api/v1/extract-url", json={"url": url})
    assert response.status_code == 200
    data = response.json()
    assert "ASUS" in data["title"] or "Strix" in data["title"]
    assert data["price"] > 1000.0
    assert data["shipping"] >= 0
    assert "RTX" in data["specs"] or "Intel" in data["specs"] or "i7" in data["specs"] or "Gaming" in data["title"]
    assert data["currency"] == "USD"

def test_download_extension_endpoint():
    response = client.get("/api/v1/download-extension")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert len(response.content) > 1000

def test_tablet_classification_and_amazon_deposit():
    response = client.post("/api/v1/analyze-product", json={
        "title": "Apple iPad Pro 13-Inch Tablet M4 Chip",
        "specs": "Wi-Fi, Ultra Retina XDR display, 256GB storage",
        "price_fob": 1299.74,
        "currency": "USD",
        "shipping_foreign": 13.37,
        "amazon_import_charges_foreign": 537.36,
        "domestic_price_inr": 129900.00,
        "shipping_mode": "express_courier",
        "is_personal_use": True
    })
    assert response.status_code == 200
    data = response.json()
    assert data["classification"]["hs_code"] in ["84713090", "84713010"]
    assert data["classification"]["effective_bcd"] == 0.0
    wf = data["landed_cost_waterfall"]
    assert wf["bcd_inr"] == 0.0
    assert wf["igst_rate"] == 0.18
    assert "amazon_comparison" in wf
    assert wf["amazon_comparison"]["amazon_deposit_foreign"] == 537.36
    assert wf["amazon_comparison"]["potential_refund_inr"] > 20000.0


def test_detention_risk_gauge_and_community_reports():
    response = client.post("/api/v1/analyze-product", json={
        "title": "Keychron Q1 Pro Wireless Mechanical Keyboard",
        "specs": "Bluetooth 5.1, Hot-swappable, CNC aluminum body",
        "price_fob": 199.00,
        "currency": "USD",
        "shipping_foreign": 22.00,
        "shipping_mode": "express_courier",
        "is_personal_use": True
    })
    assert response.status_code == 200
    data = response.json()
    
    # 1. Customs Detention Risk Gauge
    reg = data["regulatory_compliance"]
    assert "detention_risk" in reg
    risk = reg["detention_risk"]
    assert "score" in risk
    assert 0 <= risk["score"] <= 100
    assert risk["level"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]
    assert "inspection_likelihood" in risk
    assert isinstance(risk["risk_factors"], list)

    # 2. Community Crowdsourced Duty History
    assert "community_duty_history" in data
    history = data["community_duty_history"]
    assert isinstance(history, list)
    assert len(history) > 0
    first = history[0]
    assert "carrier" in first
    assert "duty_effective_pct" in first
    assert "verified" in first


def test_community_reports_standalone_endpoint():
    response = client.get("/api/v1/community-reports?q=Keyboard")
    assert response.status_code == 200
    data = response.json()
    assert "reports" in data
    assert len(data["reports"]) > 0


def test_gemini_extension_and_tool_endpoints():
    # Test OpenAPI 3.0 Extension Schema
    schema_res = client.get("/api/v1/gemini-extension/schema")
    assert schema_res.status_code == 200
    schema = schema_res.json()
    assert schema["openapi"].startswith("3.0")
    assert "/api/v1/gemini-tool/calculate" in schema["paths"]

    # Test Gemini Tool Definition
    tool_res = client.get("/api/v1/gemini-tool/definition")
    assert tool_res.status_code == 200
    tool = tool_res.json()["tool"]
    assert tool["name"] == "calculate_import_landed_cost"
    assert "parameters" in tool

    # Test Gemini Tool Calculation
    calc_res = client.post("/api/v1/gemini-tool/calculate", json={
        "product_name": "Keychron Q1 Pro Wireless Keyboard",
        "price": 199.00,
        "currency": "USD",
        "shipping_cost": 22.00,
        "shipping_mode": "express_courier"
    })
    assert calc_res.status_code == 200
    calc_data = calc_res.json()
    assert calc_data["success"] is True
    assert "conversational_summary" in calc_data
    assert "HS Code" in calc_data["conversational_summary"]
    assert "detention_risk_score" in calc_data






