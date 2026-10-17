"""
BorderWise AI: Hierarchical Tariff Classifier Agent
Orchestrates:
1. Input Guardrail Sanitization & Prompt Injection Defense
2. In-Memory SQLite candidate heading search
3. Gemini Flash / Heuristic Legal Reasoning
4. Output Guardrail Schema Validation & Tariff Registry Assertion
"""

import sqlite3
from typing import Dict, Any, Optional
from pathlib import Path

from backend.guardrails.input_sanitizer import InputSanitizer
from backend.guardrails.output_validator import OutputValidator
from backend.agents.gemini_client import GeminiClassifierClient

DB_PATH = Path(__file__).parent.parent / "db" / "borderwise_tariff.db"


class TariffClassifierAgent:
    """
    Agent responsible for classifying imported goods into verified 8-digit HS Codes.
    """

    def __init__(self, db_path: Path = DB_PATH, api_key: Optional[str] = None):
        self.db_path = db_path
        self.gemini_client = GeminiClassifierClient(api_key=api_key)

    def _find_candidate_headings(self, clean_title: str) -> list:
        """Looks up candidate 4-digit headings from in-memory SQLite tariff schedule."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        keywords = clean_title.split()[:5]

        candidates = []
        for kw in keywords:
            if len(kw) < 4:
                continue
            kw_clean = kw.lower().strip()
            if kw_clean == "tablet":
                cursor.execute("""
                    SELECT DISTINCT heading, description FROM tariffs 
                    WHERE heading IN ('8471', '8517') LIMIT 3
                """)
            else:
                cursor.execute("""
                    SELECT DISTINCT heading, description FROM tariffs 
                    WHERE description LIKE ? AND chapter NOT IN (28, 29, 30, 31, 32) LIMIT 3
                """, (f"%{kw}%",))
            for row in cursor.fetchall():
                candidates.append({"heading": row[0], "description": row[1]})
        conn.close()
        return candidates[:5]

    def classify(self, raw_title: str, raw_specs: str) -> Dict[str, Any]:
        """
        Executes complete classification pipeline with guardrails.
        """
        # Step 1: Input Guardrail Sanitization
        is_valid, err_msg, sanitized = InputSanitizer.sanitize(raw_title, raw_specs)
        if not is_valid:
            return {
                "success": False,
                "error": err_msg,
                "stage": "input_guardrail"
            }

        clean_title = sanitized["clean_title"]
        clean_specs = sanitized["clean_specs"]

        # Step 2: In-Memory Tariff Search for Candidate Headings
        candidate_headings = self._find_candidate_headings(clean_title)

        # Step 3: AI Legal Reasoning Layer (Gemini Flash / Resilient Fallback)
        raw_result = self.gemini_client.classify_product(
            clean_title=clean_title,
            clean_specs=clean_specs,
            candidate_headings=candidate_headings
        )

        # Step 4: Output Guardrail & Statutory Existence Assertion
        validated = OutputValidator.validate_and_enrich(raw_result, db_path=self.db_path)
        if not validated["is_valid"]:
            return {
                "success": False,
                "error": validated["error"],
                "stage": "output_guardrail"
            }

        return {
            "success": True,
            "classification": validated,
            "stage": "completed"
        }
