"""
Distressed-Infrastructure Scanner -- STEP 3: INTERPRET  (the AI step)
=====================================================================
Steps 1 and 2 sourced the data and judged it in plain code. NOW the local
AI earns its keep: for each company we hand Llama 3 the numbers AND the
distress flags, and it writes a short plain-English note.

Key design choices (straight from your framework):
  * The AI does NOT decide the rating -- your code already did. It only
    EXPLAINS. That stops the model "wandering" off the facts.
  * We tell it to use ONLY the numbers we give it and invent nothing.
  * It all runs on your LOCAL Llama 3, so this costs $0.

Before running: make sure the Ollama app is OPEN (the model has to be live).
Run it with:   python infra_scanner_step3.py
(Heads-up: this is SLOW -- the local model thinks for a few seconds per company.)
"""

import time
from langchain_ollama import ChatOllama

# Reuse everything we already built and tested.
from infra_scanner_step1 import get_cik_map, get_company_facts, WATCHLIST
from infra_scanner_step2 import value_only, score_company

# The local model. temperature=0.2 keeps it factual and consistent, not creative.
llm = ChatOllama(model="llama3", temperature=0.2)


def collect_numbers(facts):
    """Grab the headline figures so the AI has real substance to talk about."""
    return {
        "Cash": value_only(facts, "CashAndCashEquivalentsAtCarryingValue"),
        "Net income (loss)": value_only(facts, "NetIncomeLoss"),
        "Total liabilities": value_only(facts, "Liabilities"),
        "Revenue": value_only(facts, "Revenues"),
    }


def write_interpretation(ticker, name, rating, flags, numbers):
    """Ask the local model to turn the data into a short analyst note."""
    facts_text = "\n".join(
        f"  - {label}: {val:,.0f}" if isinstance(val, (int, float))
        else f"  - {label}: not reported"
        for label, val in numbers.items()
    )
    flags_text = "\n".join(f"  - {f}" for f in flags) if flags else "  - none"

    prompt = f"""You are a financial analyst assistant. Using ONLY the data below, write a short note (3-4 sentences) on this company's financial health. Do NOT invent any numbers or facts that are not provided. Do NOT give buy/sell investment advice.

Company: {name} ({ticker})
Distress rating (already determined): {rating}
Reported figures (USD):
{facts_text}
Distress signals found:
{flags_text}

Write the note now:"""

    response = llm.invoke(prompt)
    return response.content.strip()


def main():
    print("Looking up company IDs from the SEC...\n")
    cik_map = get_cik_map()

    for ticker in WATCHLIST:
        cik = cik_map.get(ticker.upper())
        if not cik:
            print(f"{ticker}: not found -- skipping.\n")
            continue
        facts = get_company_facts(cik)
        if facts is None:
            print(f"{ticker}: no data -- skipping.\n")
            time.sleep(0.2)
            continue

        rating, flags = score_company(facts)
        numbers = collect_numbers(facts)
        name = facts.get("entityName", "Unknown")

        print(f"=== {ticker}  ({name})  -->  DISTRESS: {rating} ===")
        print("(asking Llama 3 to interpret -- give it a few seconds...)\n")
        note = write_interpretation(ticker, name, rating, flags, numbers)
        print(note)
        print("\n" + "-" * 60 + "\n")

        time.sleep(0.2)


if __name__ == "__main__":
    main()
