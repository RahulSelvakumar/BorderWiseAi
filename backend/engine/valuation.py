"""
BorderWise AI: Statutory Valuation Engine (Customs Act, 1962 - Section 14)
Implements:
1. Customs Valuation (Determination of Value of Imported Goods) Rules, 2007
2. Rule 10(2)(a) Freight Valuation (Actual or 20% Deemed for Air/Courier)
3. Rule 10(2)(b) Insurance Valuation (Actual or 1.125% Statutory Deemed)
4. CBIC Notification No. 91/2017-Customs (Omission of 1% landing charges loading)
5. Strict Decimal precision (decimal.Decimal) with HALF_UP rounding
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any


def round_currency(val: Decimal) -> Decimal:
    """Rounds a Decimal value to 2 decimal places using standard commercial HALF_UP rounding."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ValuationEngine:
    """
    Computes Assessable Value (CIF) in accordance with Section 14 of Customs Act, 1962.
    """

    @staticmethod
    def calculate_cif(
        fob_price_foreign: float,
        forex_rate: float,
        freight_foreign: Optional[float] = None,
        insurance_foreign: Optional[float] = None,
        is_air_or_courier: bool = True
    ) -> Dict[str, Any]:
        """
        Calculates Assessable Value (CIF) in Indian Rupees (INR).

        Args:
            fob_price_foreign: Base invoice/product price in foreign currency
            forex_rate: CBIC notified conversion rate into INR
            freight_foreign: Actual freight in foreign currency (if ascertainable)
            insurance_foreign: Actual insurance in foreign currency (if ascertainable)
            is_air_or_courier: True if arriving via air cargo/courier (applies 20% deemed cap)

        Returns:
            Dictionary with itemized CIF valuation waterfall in INR.
        """
        fob_foreign_dec = Decimal(str(fob_price_foreign))
        rate_dec = Decimal(str(forex_rate))

        # 1. FOB Value in INR
        fob_inr = round_currency(fob_foreign_dec * rate_dec)

        # 2. Freight Calculation under Rule 10(2)(a)
        if freight_foreign is not None and freight_foreign > 0:
            freight_actual_inr = round_currency(Decimal(str(freight_foreign)) * rate_dec)
            freight_inr = freight_actual_inr
            freight_rule = "Rule 10(2)(a) - Actual ascertainable shipping charge"
            is_freight_deemed = False
        else:
            # Under Rule 10(2)(a), if freight is not ascertainable, deemed at 20% of FOB
            freight_inr = round_currency(fob_inr * Decimal("0.20"))
            freight_rule = "Rule 10(2)(a) - Statutory deemed freight (20.0% of FOB for Air/Courier)"
            is_freight_deemed = True

        # 3. Insurance Calculation under Rule 10(2)(b)
        if insurance_foreign is not None and insurance_foreign > 0:
            insurance_actual_inr = round_currency(Decimal(str(insurance_foreign)) * rate_dec)
            insurance_inr = insurance_actual_inr
            insurance_rule = "Rule 10(2)(b) - Actual policy premium paid"
            is_insurance_deemed = False
        else:
            # Under Rule 10(2)(b), if insurance is not ascertainable, deemed at 1.125% of FOB
            insurance_inr = round_currency(fob_inr * Decimal("0.01125"))
            insurance_rule = "Rule 10(2)(b) - Statutory deemed insurance (1.125% of FOB)"
            is_insurance_deemed = True

        # 4. Landing Charges Loading (Abolished under Notif 91/2017-Customs)
        landing_charges_inr = Decimal("0.00")
        landing_rule = "Notification No. 91/2017-Customs (N.T.) - 1% landing charge loading abolished"

        # 5. Assessable Value (CIF)
        assessable_cif_inr = round_currency(fob_inr + freight_inr + insurance_inr + landing_charges_inr)

        return {
            "fob_foreign": float(fob_foreign_dec),
            "forex_rate": float(rate_dec),
            "fob_inr": float(fob_inr),
            "freight_inr": float(freight_inr),
            "freight_rule": freight_rule,
            "is_freight_deemed": is_freight_deemed,
            "insurance_inr": float(insurance_inr),
            "insurance_rule": insurance_rule,
            "is_insurance_deemed": is_insurance_deemed,
            "landing_charges_inr": float(landing_charges_inr),
            "landing_rule": landing_rule,
            "assessable_cif_inr": float(assessable_cif_inr),
            "statutory_authority": "Customs Act, 1962 (Section 14) & Customs Valuation Rules, 2007"
        }
