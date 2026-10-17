"""
BorderWise AI: Google Gemini Function Calling & Vertex AI Extension Plugin
Enables Google Gemini (and Vertex AI Agent Engine) to natively invoke BorderWise
as an intelligent cross-border commerce tool during conversational user chats.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

# 1. Native Gemini Tool Function Calling Definition
GEMINI_TOOL_DECLARATION: Dict[str, Any] = {
    "name": "calculate_import_landed_cost",
    "description": (
        "Calculates exact Indian customs import duties (Customs Act Sec 14 CIF valuation, Basic Customs Duty BCD, "
        "Social Welfare Surcharge SWS, Integrated GST IGST, and courier clearance fees), domestic vs import price arbitrage, "
        "and regulatory clearance feasibility (WPC wireless, BIS electronics, EPR battery exemptions) for international goods."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "product_name": {
                "type": "string",
                "description": "The exact name, title, or brand of the product being imported (e.g. 'Keychron Q1 Pro Wireless Keyboard')"
            },
            "price": {
                "type": "number",
                "description": "Foreign FOB listed price of the item"
            },
            "currency": {
                "type": "string",
                "enum": ["USD", "JPY", "EUR", "GBP", "SGD", "AUD", "CNY"],
                "description": "Foreign currency code (defaults to USD)",
                "default": "USD"
            },
            "shipping_cost": {
                "type": "number",
                "description": "Estimated or actual international freight cost (optional, deemed 20% if omitted)"
            },
            "specs": {
                "type": "string",
                "description": "Technical specifications, frequency bands, materials, or features (e.g., 'Bluetooth 5.1, Aluminum body')"
            },
            "shipping_mode": {
                "type": "string",
                "enum": ["express_courier", "postal_ems", "prepaid_ddp"],
                "description": "Courier clearance mode: express_courier (DHL/FedEx), postal_ems (India Post), or prepaid_ddp (Amazon DDP)",
                "default": "express_courier"
            }
        },
        "required": ["product_name", "price"]
    }
}

# 2. OpenAPI 3.0 Specification for Vertex AI Extensions
VERTEX_AI_EXTENSION_SPEC: Dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "BorderWise AI Cross-Border Customs & Feasibility Extension",
        "description": "Vertex AI Extension enabling Gemini models to compute legal landed costs, HS codes, and customs compliance for retail e-commerce imports.",
        "version": "1.0.0"
    },
    "servers": [
        {
            "url": "https://borderwise-ai-vfqthqmtna-el.a.run.app",
            "description": "Google Cloud Run Production Gateway"
        }
    ],
    "paths": {
        "/api/v1/gemini-tool/calculate": {
            "post": {
                "summary": "Calculate Landed Cost, HS Code & Import Feasibility",
                "description": "Executes Section 14 customs valuation, regulatory compliance audits, and domestic arbitrage benchmarks.",
                "operationId": "calculate_import_landed_cost",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/GeminiToolInput"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Successful feasibility dossier with landed cost waterfall and regulatory verdict",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/GeminiToolOutput"
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "GeminiToolInput": {
                "type": "object",
                "required": ["product_name", "price"],
                "properties": {
                    "product_name": {"type": "string"},
                    "price": {"type": "number"},
                    "currency": {"type": "string", "default": "USD"},
                    "shipping_cost": {"type": "number"},
                    "specs": {"type": "string"},
                    "shipping_mode": {"type": "string", "default": "express_courier"}
                }
            },
            "GeminiToolOutput": {
                "type": "object",
                "properties": {
                    "summary_advice": {"type": "string"},
                    "verdict": {"type": "string"},
                    "savings_inr": {"type": "number"},
                    "total_landed_cost_inr": {"type": "number"},
                    "hs_code": {"type": "string"},
                    "effective_duty_pct": {"type": "number"},
                    "regulatory_status": {"type": "string"},
                    "detention_risk_score": {"type": "integer"}
                }
            }
        }
    }
}


class GeminiToolRequest(BaseModel):
    product_name: str = Field(..., description="Product title or description")
    price: float = Field(..., gt=0, description="Product FOB price")
    currency: str = Field("USD", description="Currency (USD, JPY, EUR, GBP, SGD, AUD, CNY)")
    shipping_cost: Optional[float] = Field(None, description="International shipping fee")
    specs: Optional[str] = Field("", description="Technical details")
    shipping_mode: str = Field("express_courier", description="express_courier, postal_ems, or prepaid_ddp")


def format_conversational_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synthesizes the technical analysis into a natural conversational summary
    that Gemini can read and present cleanly to end-users.
    """
    meta = data["product_meta"]
    cls = data["classification"]
    wf = data["landed_cost_waterfall"]
    reg = data["regulatory_compliance"]
    arb = data.get("price_arbitrage")
    risk = reg.get("detention_risk", {})

    total_landed = wf["total_landed_cost_inr"]
    fob_inr = wf["fob_inr"]
    duties_inr = wf["total_customs_duties_inr"]
    courier_inr = wf["courier_fee_inr"]

    verdict_text = "NEUTRAL"
    savings_str = "N/A"
    if arb:
        sav_pct = arb.get("savings_percentage", 0)
        if arb.get("verdict") == "SAVE_BY_IMPORTING":
            verdict_text = f"SAVE ₹{arb['net_savings_inr']:,.2f} ({sav_pct}%) by importing!"
            savings_str = f"₹{arb['net_savings_inr']:,.2f}"
        else:
            loss = abs(arb.get('net_savings_inr', 0))
            verdict_text = f"BUY DOMESTICALLY — importing is ₹{loss:,.2f} ({abs(sav_pct)}%) more expensive!"
            savings_str = f"-₹{loss:,.2f}"

    conversational_summary = (
        f"### 📦 Cross-Border Import Analysis: {meta['title']}\n\n"
        f"• **Doorstep Landed Cost:** **₹{total_landed:,.2f}**\n"
        f"  - Converted Price: ₹{fob_inr:,.2f} ({meta['currency']} {meta['foreign_price']})\n"
        f"  - Customs Duties (BCD + SWS + IGST @ {cls['igst_rate']*100:.0f}%): ₹{duties_inr:,.2f}\n"
        f"  - Courier Clearance & Terminal Fees: ₹{courier_inr:,.2f}\n"
        f"• **Statutory HS Code:** `{cls['hs_code']}` ({cls['description']})\n"
        f"• **Customs Detention Risk:** **{risk.get('score', 15)}/100 ({risk.get('level', 'LOW')})** — {risk.get('inspection_likelihood', '')}\n"
        f"• **Price Verdict:** **{verdict_text}**\n\n"
        f"🛡️ **Compliance Check:** {reg['overall_status']} (Exemptions apply for personal bona fide use under DGFT Notif 34/2015-20)."
    )

    return {
        "success": True,
        "conversational_summary": conversational_summary,
        "product_name": meta["title"],
        "total_landed_cost_inr": total_landed,
        "hs_code": cls["hs_code"],
        "effective_bcd_pct": round(cls["effective_bcd"] * 100, 2),
        "total_duties_inr": duties_inr,
        "detention_risk_score": risk.get("score", 15),
        "detention_risk_level": risk.get("level", "LOW"),
        "verdict": arb.get("verdict") if arb else "CHECK_DOMESTIC",
        "net_savings_inr": arb.get("net_savings_inr") if arb else 0,
        "raw_dossier": data
    }
