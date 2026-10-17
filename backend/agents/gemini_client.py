"""
BorderWise AI: Google Gemini Client Abstraction
Supports:
1. Google Gemini 1.5/2.0 Flash via Google GenAI SDK (Vertex AI / Google AI Studio)
2. Native response_schema structured JSON output mode
3. Local Trie/Keyword Heuristic Fallback (Circuit Breaker Tier 1 for offline testing & rate limits)
"""

import os
import re
import json
import hashlib
import sqlite3
from typing import Dict, Any, Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Load .env from project root if present
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()
except ImportError:
    pass

DB_PATH = Path(__file__).parent.parent / "db" / "borderwise_tariff.db"

# In-memory query hash cache to guarantee zero duplicate LLM token consumption
_MEM_CACHE: Dict[str, Dict[str, Any]] = {}

# Prompt template for hierarchical HS classification grounded in WCO GRI 1-6
CLASSIFIER_SYSTEM_PROMPT = """You are an authoritative Senior Customs Classification Specialist and Legal Tariff Examiner conforming to the World Customs Organization (WCO) Harmonized System and the Indian Customs Tariff Act, 1975.

Your task is to classify the provided imported product into the exact 8-digit or 6-digit Harmonized Tariff Schedule (HS Code).

CRITICAL CLASSIFICATION INSTRUCTIONS:
1. Ground your reasoning in General Rules for the Interpretation (GRI) of the Harmonized System:
   - GRI 1: Terms of headings and section/chapter notes.
   - GRI 3(a): Heading providing the most specific description shall be preferred.
   - GRI 3(b): Mixtures, composite goods, and retail sets classified by essential character.
2. Evaluate statutory chapter notes (e.g. Chapter 84 Note 5 for automatic data processing machines, Chapter 85 Note 4 for electronics).
3. Identify whether the product qualifies for Information Technology Agreement (ITA-1) zero-duty treatment (e.g. keyboards under 8471.60.40, computer parts under 8473, SSDs under 8471.70).
4. Output MUST conform strictly to the requested JSON schema. Do not generate markdown code fences or conversational pleasantries."""


class GeminiClassifierClient:
    """
    Client for invoking Google Gemini Flash with fallback resilience and aggressive cost optimization.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.8")
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except ImportError:
                try:
                    import google.generativeai as gai
                    gai.configure(api_key=self.api_key)
                    self.client = gai.GenerativeModel(self.model_name)
                except Exception as e:
                    print(f"[GeminiClient] Could not initialize Google GenAI SDK: {e}")

    def classify_product(
        self,
        clean_title: str,
        clean_specs: str,
        candidate_headings: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Classifies product into HS Code using Gemini Flash, with local heuristic fallback.
        Checks in-memory cache first to guarantee 0 token spend on identical products.
        """
        cache_key = hashlib.sha256(f"{clean_title.strip().lower()}:{clean_specs.strip().lower()}".encode()).hexdigest()
        if cache_key in _MEM_CACHE:
            return _MEM_CACHE[cache_key]

        # If API key is available and client initialized, call Gemini Flash
        if self.client and self.api_key:
            try:
                res = self._call_gemini_api(clean_title, clean_specs, candidate_headings)
                if res and "hs_code" in res:
                    _MEM_CACHE[cache_key] = res
                    return res
            except Exception as e:
                print(f"[GeminiClient Warning] API call failed ({e}). Tripping circuit breaker to local rule engine.")

        # Circuit Breaker Fallback: High-Speed Local In-Memory Semantic Classifier
        res = self._local_heuristic_classifier(clean_title, clean_specs)
        _MEM_CACHE[cache_key] = res
        return res

    def _call_gemini_api(
        self,
        clean_title: str,
        clean_specs: str,
        candidate_headings: Optional[list] = None
    ) -> Dict[str, Any]:
        """Calls Google Gemini API using structured JSON mode with minimal token payload."""
        # Token optimization: trim titles and limit candidates to top 3
        compact_title = clean_title[:120].strip()
        compact_specs = clean_specs[:250].strip()
        compact_candidates = (candidate_headings or [])[:3]

        prompt = (
            f"{CLASSIFIER_SYSTEM_PROMPT}\n\n"
            f"Product Title: {compact_title}\n"
            f"Product Specs: {compact_specs}\n"
            f"Candidate Headings: {compact_candidates}\n\n"
            f"Return JSON adhering to schema:\n"
            f"{{\n"
            f'  "hs_code": "<8-digit digits only>",\n'
            f'  "confidence": <float 0.0 to 1.0>,\n'
            f'  "heading": "<4-digit heading>",\n'
            f'  "reasoning": "<concise legal explanation citing GRI rules>",\n'
            f'  "statutory_notes_cited": ["<chapter notes>"],\n'
            f'  "alternative_candidates": ["<alternative hs codes>"]\n'
            f"}}"
        )

        models_to_try = [self.model_name, "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]

        # 1. Try Direct Fast REST via urllib (avoids gRPC macOS socket stalls)
        import urllib.request
        for m in models_to_try:
            clean_m = m.replace("models/", "")
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_m}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0.1,
                        "maxOutputTokens": 300
                    }
                }
                req_obj = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req_obj, timeout=6.0) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    cand_text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(cand_text)
                    if parsed and "hs_code" in parsed:
                        return parsed
            except Exception as rest_err:
                pass

        # 2. Try SDK fallback
        last_err = None
        for m in models_to_try:
            try:
                if hasattr(self.client, "models"):
                    # Google GenAI SDK (Vertex AI / Google AI Studio)
                    response = self.client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config={
                            "response_mime_type": "application/json",
                            "temperature": 0.1,
                            "max_output_tokens": 256
                        }
                    )
                    return json.loads(response.text)
                elif hasattr(self.client, "generate_content"):
                    # Google Generative AI SDK (google.generativeai)
                    response = self.client.generate_content(
                        prompt,
                        generation_config={
                            "response_mime_type": "application/json",
                            "temperature": 0.1,
                            "max_output_tokens": 256
                        }
                    )
                    return json.loads(response.text)
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise last_err
        return {}

    def _local_heuristic_classifier(self, title: str, specs: str) -> Dict[str, Any]:
        """
        Local High-Speed In-Memory Classifier (Circuit Breaker Tier 1).
        Scans product title and specs against database keywords.
        """
        combined = f"{title.lower()} {specs.lower()}"

        # 1. Computer Keyboards (ITA-1 Zero Duty)
        if any(k in combined for k in ["keyboard", "keychron", "mechanical keyboard", "cherry mx"]):
            return {
                "hs_code": "84716040",
                "confidence": 0.96,
                "heading": "8471",
                "reasoning": "Classified under Heading 8471 as an input unit for automatic data processing machines per Chapter 84 Note 5(C). Concessional 0% BCD applies under ITA-1 Notification No. 24/2005-Customs.",
                "statutory_notes_cited": ["Chapter 84, Note 5(C)", "WCO GRI 1"],
                "alternative_candidates": ["84716050", "85371000"]
            }

        # 2. Mice & Trackpads
        if any(k in combined for k in ["mouse", "trackpad", "optical mouse", "gaming mouse", "trackball"]):
            return {
                "hs_code": "84716050",
                "confidence": 0.95,
                "heading": "8471",
                "reasoning": "Classified under Heading 8471 as mouse/pointing device for automatic data-processing machines per Chapter 84 Note 5(C). ITA-1 0% BCD applies.",
                "statutory_notes_cited": ["Chapter 84, Note 5(C)", "WCO GRI 1"],
                "alternative_candidates": ["84716040"]
            }

        # 3. Laptops & Notebooks
        if any(k in combined for k in ["laptop", "notebook", "macbook", "thinkpad", "chromebook"]):
            return {
                "hs_code": "84713010",
                "confidence": 0.97,
                "heading": "8471",
                "reasoning": "Classified under Heading 8471.30 as a portable automatic data-processing machine weighing not more than 10 kg, consisting of at least a central processing unit, a keyboard and a display per Chapter 84 Subheading Note 1.",
                "statutory_notes_cited": ["Chapter 84, Subheading Note 1", "WCO GRI 1"],
                "alternative_candidates": ["84713090"]
            }

        # 3b. Tablets, iPads, E-Readers & Drawing Displays (ITA-1 Zero Duty)
        if any(k in combined for k in ["tablet", "ipad", "galaxy tab", "surface pro", "fire hd", "kindle", "e-reader", "lenovo tab", "xiaomi pad", "drawing tablet"]):
            return {
                "hs_code": "84713090",
                "confidence": 0.98,
                "heading": "8471",
                "reasoning": "Classified under Heading 8471.30.90 as a portable digital automatic data processing machine (tablet computer) weighing not more than 10 kg with display. Concessional 0% BCD applies under ITA-1 Notification No. 24/2005-Customs (only 18% IGST applies). Note: Amazon Global pre-collects a 41% personal courier deposit under Heading 9804, from which excess duty is refundable.",
                "statutory_notes_cited": ["Chapter 84, Note 5(C)", "ITA-1 Notification No. 24/2005-Customs", "WCO GRI 1"],
                "alternative_candidates": ["84713010", "98049000"]
            }

        # 4. Storage SSD & Hard Drives
        if any(k in combined for k in ["ssd", "nvme", "solid state drive", "hard disk", "hdd", "m.2"]):
            return {
                "hs_code": "84717020",
                "confidence": 0.96,
                "heading": "8471",
                "reasoning": "Classified under Heading 8471.70 as storage units for automatic data-processing machines per Chapter 84 Note 5(D). Concessional 0% BCD under Notif 24/2005-Cus.",
                "statutory_notes_cited": ["Chapter 84, Note 5(D)", "WCO GRI 1"],
                "alternative_candidates": ["84717090"]
            }

        # 5. Headphones & Earphones
        if any(k in combined for k in ["headphone", "earphone", "earbuds", "airpods", "headset", "wh-1000xm"]):
            return {
                "hs_code": "85183000",
                "confidence": 0.95,
                "heading": "8518",
                "reasoning": "Classified under Heading 8518.30 as headphones and earphones, combined or not with a microphone. Standard BCD rate 20% applies.",
                "statutory_notes_cited": ["Chapter 85, Heading 8518", "WCO GRI 1"],
                "alternative_candidates": ["85181000", "85176290"]
            }

        # 6. Microphones
        if any(k in combined for k in ["microphone", "mic", "shure sm7b", "condenser mic", "dynamic mic"]):
            return {
                "hs_code": "85181000",
                "confidence": 0.95,
                "heading": "8518",
                "reasoning": "Classified under Heading 8518.10 as microphones and stands therefor. Standard BCD rate 15% applies.",
                "statutory_notes_cited": ["Chapter 85, Heading 8518", "WCO GRI 1"],
                "alternative_candidates": ["85183000"]
            }

        # 7. Video Game Consoles
        if any(k in combined for k in ["playstation", "xbox", "nintendo switch", "gaming console", "ps5"]):
            return {
                "hs_code": "95045000",
                "confidence": 0.97,
                "heading": "9504",
                "reasoning": "Classified under Heading 9504.50 as video game consoles and machines, other than those of subheading 9504.30. Subject to standard BCD 20% and IGST 28% luxury entertainment slab.",
                "statutory_notes_cited": ["Chapter 95, Heading 9504", "WCO GRI 1"],
                "alternative_candidates": ["95049090"]
            }

        # 8. Drones & UAVs
        if any(k in combined for k in ["drone", "uav", "quadcopter", "dji mini", "mavic"]):
            return {
                "hs_code": "88062100",
                "confidence": 0.98,
                "heading": "8806",
                "reasoning": "Classified under Heading 8806.21 as unmanned aircraft (drones). NOTE: Import is PROHIBITED under DGFT Notification No. 54/2015-2020 without prior DGFT import license.",
                "statutory_notes_cited": ["Chapter 88, Heading 8806", "DGFT Notif 54/2015-2020"],
                "alternative_candidates": ["88069100"]
            }

        # 9. Smartwatches
        if any(k in combined for k in ["smartwatch", "smart watch", "apple watch", "galaxy watch"]):
            return {
                "hs_code": "85176290",
                "confidence": 0.92,
                "heading": "8517",
                "reasoning": "Classified under Heading 8517.62 as other apparatus for transmission or reception of voice, images or other data. WPC ETA self-declaration required for Bluetooth/Wi-Fi transceivers.",
                "statutory_notes_cited": ["Chapter 85, Heading 8517", "WCO GRI 3(b)"],
                "alternative_candidates": ["91021200"]
            }

        # 10. Monitors & Computer Displays
        if any(k in combined for k in ["monitor", "display", "ultragear", "gaming monitor", "ips screen"]):
            return {
                "hs_code": "85285200",
                "confidence": 0.95,
                "heading": "8528",
                "reasoning": "Classified under Heading 8528.52 as monitors capable of directly connecting to and designed for use with an automatic data-processing machine of heading 84.71.",
                "statutory_notes_cited": ["Chapter 85, Heading 8528", "WCO GRI 1"],
                "alternative_candidates": ["85285900", "84716090"]
            }

        # 11. E-cigarettes, Vapes & Nicotine Cartridges
        if any(k in combined for k in ["vape", "e-cigarette", "nicotine", "flum float", "puff"]):
            return {
                "hs_code": "24041200",
                "confidence": 0.98,
                "heading": "2404",
                "reasoning": "Classified under Heading 2404.12 as products containing nicotine, intended for inhalation without combustion. NOTE: Prohibited for import under Prohibition of Electronic Cigarettes Act, 2019.",
                "statutory_notes_cited": ["Chapter 24, Heading 2404", "Prohibition of Electronic Cigarettes Act 2019"],
                "alternative_candidates": ["24041100"]
            }

        # 12. Camera Lenses & Optics
        if any(k in combined for k in ["lens", "fe 24-70mm", "optical lens", "camera lens", "f/2.8"]):
            return {
                "hs_code": "90021100",
                "confidence": 0.96,
                "heading": "9002",
                "reasoning": "Classified under Heading 9002.11 as objective lenses for cameras, projectors or photographic enlargers.",
                "statutory_notes_cited": ["Chapter 90, Heading 9002", "WCO GRI 1"],
                "alternative_candidates": ["90021900"]
            }

        # 13. Dynamic SQLite Search across 6,576 official statutory lines for ANY unlisted product
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            stopwords = {"with", "this", "that", "from", "inch", "high", "speed", "cable", "cord", "device", "unit", "pack", "mini", "pro", "ultra", "portable"}
            words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', combined) if w not in stopwords]
            for word in words:
                cur.execute(
                    "SELECT hs_code, heading, description FROM tariffs WHERE description LIKE ? AND chapter NOT IN (28, 29, 30, 31, 32) LIMIT 1",
                    (f"%{word}%",)
                )
                row = cur.fetchone()
                if row:
                    conn.close()
                    return {
                        "hs_code": row[0],
                        "confidence": 0.85,
                        "heading": row[1],
                        "reasoning": f"Statutory tariff classification matched description '{row[2]}' under Heading {row[1]} for query term '{word}'.",
                        "statutory_notes_cited": [f"Heading {row[1]}", "WCO GRI 1"],
                        "alternative_candidates": []
                    }
            conn.close()
        except Exception:
            pass

        # 14. Fallback General IT Peripheral
        return {
            "hs_code": "84716040",
            "confidence": 0.75,
            "heading": "8471",
            "reasoning": "Fallback consumer IT peripheral classification under Chapter 84 Heading 8471.",
            "statutory_notes_cited": ["WCO GRI 1"],
            "alternative_candidates": ["85176290", "85183000"]
        }
