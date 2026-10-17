"""
Tests for BorderWise Valuation Engine (Customs Act Section 14 & Rule 10)
"""

import pytest
from decimal import Decimal
from backend.engine.valuation import ValuationEngine, round_currency


def test_round_currency():
    assert round_currency(Decimal("100.456")) == Decimal("100.46")
    assert round_currency(Decimal("100.454")) == Decimal("100.45")
    assert round_currency(Decimal("100.455")) == Decimal("100.46")


def test_calculate_cif_with_actual_freight_and_insurance():
    # $199.00 USD @ 84.50 INR/USD, actual freight $22.00, actual insurance $3.00
    res = ValuationEngine.calculate_cif(
        fob_price_foreign=199.00,
        forex_rate=84.50,
        freight_foreign=22.00,
        insurance_foreign=3.00
    )
    # FOB = 199.00 * 84.50 = 16815.50
    assert res["fob_inr"] == 16815.50
    # Freight = 22.00 * 84.50 = 1859.00
    assert res["freight_inr"] == 1859.00
    assert not res["is_freight_deemed"]
    # Insurance = 3.00 * 84.50 = 253.50
    assert res["insurance_inr"] == 253.50
    assert not res["is_insurance_deemed"]
    # Landing charge = 0.00
    assert res["landing_charges_inr"] == 0.00
    # CIF = 16815.50 + 1859.00 + 253.50 = 18928.00
    assert res["assessable_cif_inr"] == 18928.00


def test_calculate_cif_with_statutory_deemed_freight_and_insurance():
    # $100.00 USD @ 80.00 INR/USD, no freight provided (deemed 20%), no insurance (deemed 1.125%)
    res = ValuationEngine.calculate_cif(
        fob_price_foreign=100.00,
        forex_rate=80.00,
        freight_foreign=None,
        insurance_foreign=None
    )
    # FOB = 100 * 80 = 8000.00
    assert res["fob_inr"] == 8000.00
    # Deemed Freight = 8000 * 0.20 = 1600.00
    assert res["freight_inr"] == 1600.00
    assert res["is_freight_deemed"]
    # Deemed Insurance = 8000 * 0.01125 = 90.00
    assert res["insurance_inr"] == 90.00
    assert res["is_insurance_deemed"]
    # CIF = 8000 + 1600 + 90 = 9690.00
    assert res["assessable_cif_inr"] == 9690.00
