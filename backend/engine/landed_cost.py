"""
BorderWise AI: Cascading Total Landed Cost (TLC) Engine
Computes:
1. Basic Customs Duty (BCD) under Customs Tariff Act, 1975
2. Social Welfare Surcharge (SWS @ 10% of BCD) under Finance Act, 2018
3. Integrated Goods and Services Tax (IGST) under IGST Act, 2017 Sec 3(7)
4. Courier Customs Clearance Fees (Express DHL/FedEx vs. Postal EMS vs. Amazon DDP)
5. Zero-hallucination deterministic math using decimal.Decimal
6. Cryptographic SHA-256 provenance hash for legal auditability
"""

from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from typing import Dict, Any, Optional

from .valuation import round_currency, ValuationEngine


class LandedCostEngine:
    """
    Zero-Hallucination Deterministic Customs Duty & Landed Cost Calculator.
    """

    @staticmethod
    def calculate_courier_fee(
        total_customs_duties_inr: Decimal,
        shipping_mode: str = "express_courier"
    ) -> Dict[str, Any]:
        """
        Calculates courier handling and customs clearance fee.

        Modes:
        - 'express_courier' (DHL / FedEx / UPS / Aramex):
            Disbursement fee = Max(₹600, 2.5% of duties) + ₹250 terminal cargo charge + 18% GST
        - 'postal_ems' (India Post / USPS / Royal Mail):
            Statutory FPO customs presentation fee = ₹100.00 flat
        - 'prepaid_ddp' (Amazon Global Store / DDP):
            Doorstep courier charge = ₹0.00 (absorbed/pre-collected)
        """
        if shipping_mode == "express_courier":
            # Advancement/Disbursement fee
            pct_fee = total_customs_duties_inr * Decimal("0.025")
            base_disbursement = max(Decimal("600.00"), pct_fee)
            terminal_handling = Decimal("250.00")
            subtotal = base_disbursement + terminal_handling
            gst_on_courier = round_currency(subtotal * Decimal("0.18"))
            total_courier_fee = round_currency(subtotal + gst_on_courier)
            note = f"Express Courier: Advancement fee (Max(₹600, 2.5% of duties) = ₹{base_disbursement:.2f}) + ₹250 terminal fee + 18% GST (₹{gst_on_courier:.2f})"
        elif shipping_mode == "postal_ems":
            total_courier_fee = Decimal("100.00")
            note = "India Post EMS: Statutory Foreign Post Office (FPO) presentation fee of ₹100 flat"
        elif shipping_mode == "prepaid_ddp":
            total_courier_fee = Decimal("0.00")
            note = "Prepaid DDP (Amazon Global): Courier clearance fee absorbed by merchant at checkout"
        else:
            total_courier_fee = Decimal("500.00")
            note = "Standard estimated courier handling charge"

        return {
            "shipping_mode": shipping_mode,
            "courier_fee_inr": float(total_courier_fee),
            "breakdown_note": note
        }

    @classmethod
    def calculate_total_landed_cost(
        cls,
        fob_price_foreign: float,
        forex_rate: float,
        bcd_rate: float,
        igst_rate: float = 0.18,
        sws_rate: float = 0.10,
        freight_foreign: Optional[float] = None,
        insurance_foreign: Optional[float] = None,
        shipping_mode: str = "express_courier",
        hs_code: str = "84716040",
        exemption_citation: Optional[str] = None,
        amazon_import_charges_foreign: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Full Landed Cost Waterfall Calculation.
        All financial additions and multiplications are 100% deterministic.
        """
        # 1. Compute CIF Valuation
        cif_data = ValuationEngine.calculate_cif(
            fob_price_foreign=fob_price_foreign,
            forex_rate=forex_rate,
            freight_foreign=freight_foreign,
            insurance_foreign=insurance_foreign
        )
        cif_dec = Decimal(str(cif_data["assessable_cif_inr"]))

        # 2. Basic Customs Duty (BCD)
        bcd_rate_dec = Decimal(str(bcd_rate))
        bcd_inr = round_currency(cif_dec * bcd_rate_dec)

        # 3. Social Welfare Surcharge (SWS @ 10% of BCD)
        sws_rate_dec = Decimal(str(sws_rate))
        sws_inr = round_currency(bcd_inr * sws_rate_dec)

        # 4. Integrated GST (IGST on CIF + BCD + SWS)
        igst_base = cif_dec + bcd_inr + sws_inr
        igst_rate_dec = Decimal(str(igst_rate))
        igst_inr = round_currency(igst_base * igst_rate_dec)

        # 5. Total Customs Duties & Taxes
        total_customs_duties = round_currency(bcd_inr + sws_inr + igst_inr)

        # 6. Courier Clearance Handling Fee
        courier_data = cls.calculate_courier_fee(
            total_customs_duties_inr=total_customs_duties,
            shipping_mode=shipping_mode
        )
        courier_fee_dec = Decimal(str(courier_data["courier_fee_inr"]))

        # 7. Total All-Inclusive Landed Cost
        total_landed_cost = round_currency(cif_dec + total_customs_duties + courier_fee_dec)

        # 8. Cryptographic Provenance Hash (Ensures zero-tamper auditability)
        provenance_payload = {
            "hs_code": hs_code,
            "cif_inr": str(cif_dec),
            "bcd_rate": str(bcd_rate_dec),
            "bcd_inr": str(bcd_inr),
            "sws_inr": str(sws_inr),
            "igst_rate": str(igst_rate_dec),
            "igst_inr": str(igst_inr),
            "total_landed_cost": str(total_landed_cost),
            "citation": exemption_citation or "Standard Tariff Schedule"
        }
        provenance_str = json.dumps(provenance_payload, sort_keys=True)
        provenance_hash = hashlib.sha256(provenance_str.encode("utf-8")).hexdigest()

        # 9. Amazon Estimated Import Fees Deposit Comparison
        amazon_deposit_inr = None
        amazon_deposit_foreign = None
        potential_refund_inr = None
        amazon_advisory = None

        if amazon_import_charges_foreign is not None and amazon_import_charges_foreign > 0:
            amazon_deposit_foreign = float(amazon_import_charges_foreign)
            amazon_deposit_inr = float(round_currency(Decimal(str(amazon_import_charges_foreign)) * Decimal(str(forex_rate))))
            diff = Decimal(str(amazon_deposit_inr)) - total_customs_duties
            if diff > 0:
                potential_refund_inr = float(diff)
                amazon_advisory = (
                    f"Amazon pre-collects ${amazon_deposit_foreign:.2f} (₹{amazon_deposit_inr:,.2f}) as an Import Fees Deposit under Heading 9804 (~41% personal courier baggage rate). "
                    f"Under statutory ITA-1 rules (HS {hs_code}), actual duty is only ₹{total_customs_duties:,.2f} (18% IGST). "
                    f"You are eligible for an estimated refund of ₹{potential_refund_inr:,.2f} (${float(diff)/forex_rate:.2f}) from Amazon after customs clearance!"
                )
            else:
                amazon_advisory = f"Amazon pre-collects an Import Fees Deposit of ${amazon_deposit_foreign:.2f} (₹{amazon_deposit_inr:,.2f})."
        elif shipping_mode == "prepaid_ddp":
            est_amazon_pct = Decimal("0.4092")
            est_dep = round_currency(cif_dec * est_amazon_pct)
            diff = est_dep - total_customs_duties
            if diff > 0:
                potential_refund_inr = float(diff)
                amazon_deposit_inr = float(est_dep)
                amazon_deposit_foreign = float(round_currency(est_dep / Decimal(str(forex_rate))))
                amazon_advisory = (
                    f"Amazon pre-collects ~41% (est. ₹{amazon_deposit_inr:,.2f} / ${amazon_deposit_foreign:.2f}) under Heading 9804 (personal courier deposit). "
                    f"Under statutory HS {hs_code}, actual duty is only ₹{total_customs_duties:,.2f} (18% IGST). "
                    f"Potential refund from Amazon: ₹{potential_refund_inr:,.2f}."
                )

        return {
            "hs_code": hs_code,
            "fob_inr": cif_data["fob_inr"],
            "freight_inr": cif_data["freight_inr"],
            "insurance_inr": cif_data["insurance_inr"],
            "assessable_cif_inr": float(cif_dec),
            "bcd_rate": float(bcd_rate_dec),
            "bcd_inr": float(bcd_inr),
            "sws_rate": float(sws_rate_dec),
            "sws_inr": float(sws_inr),
            "igst_rate": float(igst_rate_dec),
            "igst_base_inr": float(igst_base),
            "igst_inr": float(igst_inr),
            "total_customs_duties_inr": float(total_customs_duties),
            "courier_mode": shipping_mode,
            "courier_fee_inr": float(courier_fee_dec),
            "total_landed_cost_inr": float(total_landed_cost),
            "effective_tax_pct": float(round_currency((total_customs_duties / cif_dec) * Decimal("100"))),
            "exemption_citation": exemption_citation or "Standard CBIC Tariff Schedule",
            "provenance_hash": f"sha256:{provenance_hash}",
            "calculation_engine": "BorderWise Deterministic Python Engine (Section 14 Compliant)",
            "amazon_comparison": {
                "amazon_deposit_foreign": amazon_deposit_foreign,
                "amazon_deposit_inr": amazon_deposit_inr,
                "potential_refund_inr": potential_refund_inr,
                "advisory": amazon_advisory
            } if amazon_advisory else None
        }
