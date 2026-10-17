"""
BorderWise AI: Automated Quality Benchmark Evaluation Suite
Runs golden test cases through the end-to-end pipeline:
1. Input Guardrail
2. Tariff Classifier Agent
3. Deterministic Landed Cost Engine
4. Regulatory Compliance Agent
5. Domestic Price Comparison Arbitrage
"""

import json
import sqlite3
import time
from pathlib import Path
from decimal import Decimal
from typing import Dict, Any, List

from backend.agents.classifier import TariffClassifierAgent
from backend.agents.regulatory import RegulatoryComplianceAgent
from backend.engine.landed_cost import LandedCostEngine
from backend.engine.arbitrage import ArbitrageEngine

EVAL_DIR = Path(__file__).parent
DATASET_PATH = EVAL_DIR / "golden_dataset.json"
DB_PATH = Path(__file__).parent.parent / "backend" / "db" / "borderwise_tariff.db"


def get_forex_rate(currency: str) -> float:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT rate_inr FROM exchange_rates WHERE currency = ?", (currency.upper(),))
    row = cur.fetchone()
    conn.close()
    if row:
        return float(row[0])
    return 84.50


def run_benchmark() -> Dict[str, Any]:
    with open(DATASET_PATH, "r") as f:
        dataset = json.load(f)

    classifier = TariffClassifierAgent(db_path=DB_PATH)
    regulatory = RegulatoryComplianceAgent(db_path=DB_PATH)

    total_cases = len(dataset)
    heading_matches = 0
    math_errors = 0
    regulatory_matches = 0
    latencies: List[float] = []

    print(f"\n================ BORDERWISE AI BENCHMARK EVALUATION ================")
    print(f"Total Test Cases: {total_cases} golden products")
    print("-" * 88)
    print(f"{'ID':<10} | {'Heading':<8} | {'Duty%':<6} | {'Total Landed':<14} | {'Verdict':<10} | {'Status':<6} | {'Time (ms)'}")
    print("-" * 88)

    for item in dataset:
        start_time = time.perf_counter()

        # Step 1: Classification & Guardrail
        class_res = classifier.classify(item["title"], item["specs"])
        if not class_res["success"]:
            # Check if this was a known prohibited item blocked at guardrail
            if item["expected_regulatory_status"] == "RED":
                heading_matches += 1
                regulatory_matches += 1
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                latencies.append(elapsed_ms)
                print(f"{item['id']:<10} | {'BLOCKED':<8} | {'N/A':<6} | {'N/A':<14} | {'BLOCKED':<10} | {'RED':<6} | {elapsed_ms:>6.2f}ms")
                continue
            else:
                print(f"Failed classification for {item['id']}: {class_res['error']}")
                continue

        classification = class_res["classification"]
        hs_code = classification["hs_code"]

        # Assert Heading Match
        expected_headings = item.get("acceptable_headings", [item["expected_hs_heading"]])
        if any(hs_code.startswith(h) for h in expected_headings):
            heading_matches += 1

        # Step 2: Deterministic Landed Cost Calculation
        forex_rate = get_forex_rate(item["currency"])
        calc_res = LandedCostEngine.calculate_total_landed_cost(
            fob_price_foreign=item["price_fob"],
            forex_rate=forex_rate,
            bcd_rate=classification["effective_bcd"],
            igst_rate=classification["igst_rate"],
            sws_rate=classification["sws_rate"],
            freight_foreign=item["shipping"],
            hs_code=hs_code
        )

        # Check math consistency
        cif = Decimal(str(calc_res["assessable_cif_inr"]))
        duties = Decimal(str(calc_res["total_customs_duties_inr"]))
        fees = Decimal(str(calc_res["courier_fee_inr"]))
        total = Decimal(str(calc_res["total_landed_cost_inr"]))

        if (cif + duties + fees) != total:
            math_errors += 1

        # Step 3: Regulatory Audit
        reg_res = regulatory.audit(item["title"], item["specs"], hs_code=hs_code, is_personal_use=True)
        if reg_res["overall_status"] == item["expected_regulatory_status"]:
            regulatory_matches += 1

        # Step 4: Domestic Arbitrage
        arb_res = ArbitrageEngine.compare_prices(
            domestic_price_inr=item["domestic_price_inr"],
            import_landed_cost_inr=float(total)
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        latencies.append(elapsed_ms)

        duty_pct = f"{int(classification['effective_bcd'] * 100)}%"
        landed_str = f"INR {total:,.2f}"
        print(f"{item['id']:<10} | {hs_code[:4]:<8} | {duty_pct:<6} | {landed_str:<14} | {arb_res['verdict']:<10} | {reg_res['overall_status']:<6} | {elapsed_ms:>6.2f}ms")

    print("-" * 88)
    heading_acc = (heading_matches / total_cases) * 100
    reg_recall = (regulatory_matches / total_cases) * 100
    math_err_rate = (math_errors / total_cases) * 100
    avg_latency = sum(latencies) / len(latencies)

    print(f"RESULTS SUMMARY:")
    print(f"• HS Code Heading Accuracy: {heading_acc:.1f}% (Target: >= 90.0%)")
    print(f"• Regulatory Compliance Recall: {reg_recall:.1f}% (Target: >= 99.0%)")
    print(f"• Mathematical Invariance Error Rate: {math_err_rate:.2f}% (Target: 0.00%)")
    print(f"• Mean End-to-End Latency: {avg_latency:.2f}ms (Target: < 2500ms)")
    print("=" * 88 + "\n")

    return {
        "heading_accuracy": heading_acc,
        "regulatory_recall": reg_recall,
        "math_error_rate": math_err_rate,
        "mean_latency_ms": avg_latency
    }


if __name__ == "__main__":
    results = run_benchmark()
    assert results["heading_accuracy"] >= 90.0, "Heading accuracy below 90%"
    assert results["math_error_rate"] == 0.0, "Math error occurred!"
    assert results["regulatory_recall"] >= 90.0, "Regulatory recall below threshold"
