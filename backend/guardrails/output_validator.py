"""
BorderWise AI: Output Guardrail & Schema Validation Layer
Enforces:
1. Pydantic v2 typed output schema
2. Tariff Existence Assertion (asserts 8-digit HS Code exists in SQLite tariff registry)
3. Duty Sanity Bounds (0.0 <= BCD <= 1.50, IGST in {0.0, 0.05, 0.12, 0.18, 0.28})
4. Fallback heading resolution if 8-digit code is unlisted
"""

import sqlite3
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "borderwise_tariff.db"


class ClassificationOutput(BaseModel):
    """
    Strict Pydantic v2 schema for HS Code Classification output.
    """
    hs_code: str = Field(..., description="8-digit or 6-digit Harmonized Tariff code, digits only")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score between 0.0 and 1.0")
    heading: str = Field(..., description="4-digit Chapter Heading, e.g. '8471'")
    reasoning: str = Field(..., description="Legal rationale citing General Rules of Interpretation (GRI)")
    statutory_notes_cited: List[str] = Field(default_factory=list, description="Section or Chapter notes referenced")
    alternative_candidates: List[str] = Field(default_factory=list, description="Secondary candidate HS codes")

    @field_validator("hs_code")
    @classmethod
    def clean_hs_code(cls, v: str) -> str:
        # Strip dots, spaces, dashes
        cleaned = "".join(c for c in v if c.isdigit())
        if len(cleaned) < 4:
            raise ValueError(f"HS Code must have at least 4 digits, got '{v}'")
        return cleaned


class OutputValidator:
    """
    Validates model output against statutory tariff registry and duty bounds.
    """

    @staticmethod
    def validate_and_enrich(
        raw_classification: Dict[str, Any],
        db_path: Path = DB_PATH
    ) -> Dict[str, Any]:
        """
        Validates classification schema and enriches with authoritative CBIC tariff database records.
        """
        # 1. Pydantic v2 Schema Enforcement
        parsed = ClassificationOutput(**raw_classification)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 2. Tariff Existence Assertion
        # First try exact match (padded to 8 digits if necessary)
        target_code = parsed.hs_code.ljust(8, '0')
        cursor.execute("""
            SELECT hs_code, chapter, heading, description, standard_bcd, effective_bcd,
                   exemption_notification, igst_rate, sws_rate, import_policy
            FROM tariffs WHERE hs_code = ?
        """, (target_code,))
        row = cursor.fetchone()

        # If exact 8-digit match not found, fallback to 6-digit subheading or 4-digit heading
        is_fallback = False
        if not row:
            is_fallback = True
            subheading_pattern = parsed.hs_code[:6] + "%"
            cursor.execute("""
                SELECT hs_code, chapter, heading, description, standard_bcd, effective_bcd,
                       exemption_notification, igst_rate, sws_rate, import_policy
                FROM tariffs WHERE hs_code LIKE ? LIMIT 1
            """, (subheading_pattern,))
            row = cursor.fetchone()

        if not row:
            heading_pattern = parsed.hs_code[:4] + "%"
            cursor.execute("""
                SELECT hs_code, chapter, heading, description, standard_bcd, effective_bcd,
                       exemption_notification, igst_rate, sws_rate, import_policy
                FROM tariffs WHERE hs_code LIKE ? LIMIT 1
            """, (heading_pattern,))
            row = cursor.fetchone()

        conn.close()

        if not row:
            # Absolute fallback if heading is completely uncataloged
            return {
                "is_valid": False,
                "error": f"Statutory Violation: Proposed HS Code '{parsed.hs_code}' does not exist in official CBIC registry.",
                "data": None
            }

        # 3. Duty Sanity Bounds Check
        standard_bcd = float(row[4])
        effective_bcd = float(row[5])
        igst_rate = float(row[7])

        assert 0.0 <= effective_bcd <= 1.50, f"BCD sanity violation: {effective_bcd}"
        assert igst_rate in [0.0, 0.03, 0.05, 0.12, 0.18, 0.28], f"IGST sanity violation: {igst_rate}"

        return {
            "is_valid": True,
            "is_fallback": is_fallback,
            "hs_code": row[0],
            "chapter": row[1],
            "heading": row[2],
            "description": row[3],
            "standard_bcd": standard_bcd,
            "effective_bcd": effective_bcd,
            "exemption_notification": row[6],
            "igst_rate": igst_rate,
            "sws_rate": float(row[8]),
            "import_policy": row[9],
            "confidence": parsed.confidence if not is_fallback else min(parsed.confidence, 0.75),
            "reasoning": parsed.reasoning,
            "statutory_notes_cited": parsed.statutory_notes_cited,
            "provenance_asserted": True
        }
