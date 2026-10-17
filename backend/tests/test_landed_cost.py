"""
Tests for BorderWise Cascading Total Landed Cost (TLC) Engine & Courier Modes
"""

import pytest
from backend.engine.landed_cost import LandedCostEngine
from backend.engine.arbitrage import ArbitrageEngine


def test_keychron_keyboard_ita1_zero_duty():
    """
    Keychron Q1 Pro: $199.00 USD @ 84.50, shipping $22.00, insurance unascertainable
    Under ITA-1 (HS 8471.60.40), BCD is 0.0%, SWS is 0.0%, IGST is 18%
    """
    res = LandedCostEngine.calculate_total_landed_cost(
        fob_price_foreign=199.00,
        forex_rate=84.50,
        bcd_rate=0.00,
        igst_rate=0.18,
        sws_rate=0.10,
        freight_foreign=22.00,
        insurance_foreign=None,
        shipping_mode="express_courier",
        hs_code="84716040",
        exemption_citation="Notification No. 24/2005-Customs, Sl. No. 13 (ITA-1 Bound)"
    )

    # CIF = FOB (16815.50) + Freight (1859.00) + Ins (16815.50 * 0.01125 = 189.17) = 18863.67
    assert res["assessable_cif_inr"] == 18863.67
    # BCD = 0.00
    assert res["bcd_inr"] == 0.00
    # SWS = 0.00
    assert res["sws_inr"] == 0.00
    # IGST = 18863.67 * 0.18 = 3395.46
    assert res["igst_inr"] == 3395.46
    # Total customs duties = 3395.46
    assert res["total_customs_duties_inr"] == 3395.46
    # Courier Express: min ₹600 advancement + ₹250 terminal = ₹850 + 18% GST (153) = ₹1003.00
    assert res["courier_fee_inr"] == 1003.00
    # Total landed cost = 18863.67 + 3395.46 + 1003.00 = 23262.13
    assert res["total_landed_cost_inr"] == 23262.13
    # Provenance hash must be present
    assert res["provenance_hash"].startswith("sha256:")


def test_sony_headphones_standard_duty():
    """
    Sony WH-1000XM5: $299.00 USD @ 84.50, shipping $25.00
    Headphones (HS 8518.30.00) have BCD 20%, SWS 10% of BCD, IGST 18%
    """
    res = LandedCostEngine.calculate_total_landed_cost(
        fob_price_foreign=299.00,
        forex_rate=84.50,
        bcd_rate=0.20,
        igst_rate=0.18,
        sws_rate=0.10,
        freight_foreign=25.00,
        shipping_mode="postal_ems",
        hs_code="85183000"
    )

    cif = res["assessable_cif_inr"]
    assert cif > 27000.00
    # BCD = 20% of CIF
    assert res["bcd_inr"] == round(cif * 0.20, 2)
    # SWS = 10% of BCD = 2% of CIF
    assert res["sws_inr"] == round(res["bcd_inr"] * 0.10, 2)
    # Courier Postal EMS must be flat ₹100
    assert res["courier_fee_inr"] == 100.00


def test_arbitrage_verdict():
    # Domestic price ₹26,999 vs Landed cost ₹22,785
    arb = ArbitrageEngine.compare_prices(
        domestic_price_inr=26999.00,
        import_landed_cost_inr=22785.91
    )
    assert arb["verdict"] == "SAVE_BY_IMPORTING"
    assert arb["badge_color"] == "green"
    assert arb["net_savings_inr"] == 4213.09
    assert arb["savings_percentage"] == 15.60
