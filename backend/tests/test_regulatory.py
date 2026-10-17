"""
Unit tests for RegulatoryComplianceAgent
"""

from backend.agents.regulatory import RegulatoryComplianceAgent

def test_personal_wireless_keyboard_compliance():
    agent = RegulatoryComplianceAgent()
    audit = agent.audit(
        title="Keychron Q1 Pro Mechanical Keyboard",
        specs="Bluetooth 5.1, Hot-swappable, 4000mAh Lithium battery",
        hs_code="84716040",
        is_personal_use=True
    )
    assert audit["overall_status"] == "GREEN"
    assert audit["import_policy"] == "FREE"
    assert audit["requires_special_clearance"] is False
    badge_titles = [b["badge_title"] for b in audit["badges"]]
    assert "Personal Wireless Exemption" in badge_titles
    assert "BIS Personal Exemption" in badge_titles
    assert "EPR Personal Exemption" in badge_titles

def test_commercial_wireless_keyboard_compliance():
    agent = RegulatoryComplianceAgent()
    audit = agent.audit(
        title="Keychron Q1 Pro Mechanical Keyboard",
        specs="Bluetooth 5.1, Hot-swappable, 4000mAh Lithium battery",
        hs_code="84716040",
        is_personal_use=False
    )
    assert audit["overall_status"] == "AMBER"
    assert audit["requires_special_clearance"] is True
    badge_titles = [b["badge_title"] for b in audit["badges"]]
    assert "WPC ETA Required" in badge_titles
    assert "BIS CRS Registration Required" in badge_titles

def test_prohibited_goods():
    agent = RegulatoryComplianceAgent()
    audit = agent.audit(
        title="Flum Float Disposable Vape Pod",
        specs="Nicotine e-cigarette, 3000 puffs",
        hs_code="24041200",
        is_personal_use=True
    )
    assert audit["overall_status"] == "RED"
    assert audit["import_policy"] == "PROHIBITED"
    assert audit["requires_special_clearance"] is True
