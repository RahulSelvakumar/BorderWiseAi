"""
BorderWise AI: Input Guardrail & Sanitization Layer
Enforces:
1. Payload size limits (max 10,000 chars)
2. Prompt injection & jailbreak pattern detection
3. PII redaction (credit cards, phone numbers, email addresses)
4. Safe XML delimiter framing
"""

import re
from typing import Dict, Any, Tuple


PROMPT_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous|above)\s+instructions",
    r"(?i)disregard\s+(all\s+)?prior\s+prompts",
    r"(?i)system\s*:\s*you\s+are",
    r"(?i)you\s+are\s+now\s+(in\s+)?DAN\s+mode",
    r"(?i)bypass\s+all\s+(filters|rules)",
    r"(?i)new\s+role\s*:",
    r"(?i)jailbreak",
    r"(?i)do\s+not\s+follow\s+customs\s+rules",
    r"(?i)set\s+(duty|tax|bcd)\s+to\s+0",
]

# Regex patterns for basic PII redaction
EMAIL_PATTERN = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
PHONE_PATTERN = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
CREDIT_CARD_PATTERN = r"\b(?:\d{4}[-\s]?){3}\d{4}\b"


class InputSanitizer:
    """
    Validates and sanitizes incoming product DOM payload.
    """

    MAX_PAYLOAD_CHARS = 10000

    @classmethod
    def sanitize(cls, raw_title: str, raw_specs: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates and sanitizes user input.

        Returns:
            (is_valid: bool, error_message: str, sanitized_data: Dict[str, Any])
        """
        combined = f"{raw_title} {raw_specs}"

        # 1. Size Cap Assertion
        if len(combined) > cls.MAX_PAYLOAD_CHARS:
            return False, f"Payload size {len(combined)} exceeds maximum limit of {cls.MAX_PAYLOAD_CHARS} chars.", {}

        # 2. Prompt Injection Defense
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, combined):
                return False, f"Security Violation: Adversarial prompt injection pattern detected: '{pattern}'", {}

        # 3. PII Redaction
        clean_title = re.sub(EMAIL_PATTERN, "[REDACTED_EMAIL]", raw_title)
        clean_title = re.sub(PHONE_PATTERN, "[REDACTED_PHONE]", clean_title)
        clean_title = re.sub(CREDIT_CARD_PATTERN, "[REDACTED_CARD]", clean_title)

        clean_specs = re.sub(EMAIL_PATTERN, "[REDACTED_EMAIL]", raw_specs)
        clean_specs = re.sub(PHONE_PATTERN, "[REDACTED_PHONE]", clean_specs)
        clean_specs = re.sub(CREDIT_CARD_PATTERN, "[REDACTED_CARD]", clean_specs)

        # 4. Strip dangerous script and delimiter tags
        clean_title = re.sub(r"<[^>]*script[^>]*>", "", clean_title, flags=re.IGNORECASE)
        clean_specs = re.sub(r"<[^>]*script[^>]*>", "", clean_specs, flags=re.IGNORECASE)

        # 5. XML Safe Framing for LLM Context
        framed_prompt = (
            f"<product_submission>\n"
            f"  <title>{clean_title.strip()}</title>\n"
            f"  <specifications>{clean_specs.strip()}</specifications>\n"
            f"</product_submission>"
        )

        return True, "", {
            "clean_title": clean_title.strip(),
            "clean_specs": clean_specs.strip(),
            "framed_prompt": framed_prompt
        }
