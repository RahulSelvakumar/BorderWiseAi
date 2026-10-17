"""
BorderWise AI: Domestic vs. Import Price Comparison & Arbitrage Engine
Calculates:
1. Net price arbitrage (Domestic Price - Total Landed Cost)
2. Percentage savings or loss
3. Clear consumer verdict (SAVE, BREAK_EVEN, BUY_DOMESTIC)
4. Qualitative trade-offs (Delivery timeline, local authorized warranty vs international)
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional
from .valuation import round_currency


class ArbitrageEngine:
    """
    Computes price arbitrage and consumer feasibility verdict.
    """

    @staticmethod
    def compare_prices(
        domestic_price_inr: float,
        import_landed_cost_inr: float,
        delivery_days_domestic: int = 2,
        delivery_days_import: int = 12,
        domestic_merchant: str = "Amazon India",
        warranty_domestic: str = "1-Year Authorized Indian Domestic Warranty",
        warranty_import: str = "Manufacturer International Warranty Only"
    ) -> Dict[str, Any]:
        """
        Calculates domestic vs. import comparison.
        """
        dom_dec = Decimal(str(domestic_price_inr))
        import_dec = Decimal(str(import_landed_cost_inr))

        net_difference_inr = round_currency(dom_dec - import_dec)
        savings_percentage = round_currency((net_difference_inr / dom_dec) * Decimal("100"))

        if net_difference_inr > Decimal("500.00"):
            verdict = "SAVE_BY_IMPORTING"
            badge_color = "green"
            verdict_text = f"SAVE ₹{net_difference_inr:,.2f} ({savings_percentage:.1f}%) BY IMPORTING!"
        elif net_difference_inr < Decimal("-500.00"):
            loss = abs(net_difference_inr)
            loss_pct = abs(savings_percentage)
            verdict = "BUY_DOMESTIC"
            badge_color = "red"
            verdict_text = f"BUY LOCALLY! Importing is ₹{loss:,.2f} ({loss_pct:.1f}%) more expensive."
        else:
            verdict = "BREAK_EVEN"
            badge_color = "yellow"
            verdict_text = "BREAK EVEN: Import and domestic prices are virtually identical."

        return {
            "domestic_merchant": domestic_merchant,
            "domestic_price_inr": float(dom_dec),
            "import_landed_cost_inr": float(import_dec),
            "net_savings_inr": float(net_difference_inr),
            "net_difference_inr": float(net_difference_inr),
            "savings_percentage": float(savings_percentage),
            "verdict": verdict,
            "badge_color": badge_color,
            "verdict_text": verdict_text,
            "tradeoffs": {
                "delivery_days_domestic": delivery_days_domestic,
                "delivery_days_import": delivery_days_import,
                "delivery_delta_days": delivery_days_import - delivery_days_domestic,
                "warranty_domestic": warranty_domestic,
                "warranty_import": warranty_import
            }
        }
