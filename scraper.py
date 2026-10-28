"""
Semantic e-commerce product scraper.

Reads a product listing page the way a human would - by meaning, not by
memorized CSS selectors - and extracts structured product data matching
schemas.ProductList.
"""

import asyncio
import csv
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from browser_use import Agent, ChatGoogle, BrowserProfile

from schemas import ProductList

GEMINI_MODEL = "gemini-2.5-flash"


def build_llm() -> ChatGoogle:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Copy .env.example to .env and fill it in."
        )
    return ChatGoogle(model=GEMINI_MODEL, api_key=api_key, max_output_tokens=32768)


def build_task(url: str, paginate: bool = False) -> str:
    base = (
        f"Go to {url}. This is an e-commerce product listing page. "
        "Identify every product shown on this page (do not navigate to individual "
        "product detail pages - only extract what's visible on the listing page itself). "
        "For each product, extract: name, price (the current price a customer would "
        "actually pay), original_price (the crossed-out/strikethrough price if the item "
        "is on sale, otherwise leave it null), rating (star rating if shown, otherwise "
        "null), image_url (the main product image URL), and availability "
        "('in_stock', 'out_of_stock', or 'unknown' if not indicated). "
        "\n\nUse ONLY the `extract` tool to read product data from the page. Do NOT use "
        "`evaluate`, custom JavaScript, or `find_elements` to parse product names/prices - "
        "those approaches are unreliable on this site and waste time. Call `extract` at most "
        "twice per page (once, and if it reports missed/truncated products, once more with "
        "`already_collected` set to the names you already have). Then move on with whatever "
        "you have - do not keep retrying extraction on the same page. "
    )
    if paginate:
        base += (
            "\n\nAfter extracting products from a page, look for a pagination control "
            "(a 'Next' button, page number links, or similar affordance identified by its "
            "text/aria-label/role - not by any specific CSS class). If one exists and is not "
            "disabled, click it and repeat extraction (via `extract`) on the next page. "
            "Continue until there is no next page, or you have covered a maximum of 3 pages. "
            "Combine all products from every page into a single final result. "
        )
    base += (
        "\n\nIMPORTANT - handling ambiguous fields: some products may show BOTH a "
        "strikethrough/crossed-out price AND a regular price close together, or a price that "
        "could plausibly be read two different ways. If `extract` alone leaves a product's "
        "price or rating unclear, take ONE screenshot of just that product's region to check "
        "it visually. If it's still unclear after that, do NOT guess - instead set that "
        "product's needs_review field to a short explanation of exactly why it's ambiguous, "
        "and still include your best-guess values for the other fields. "
        "Return the result as structured data matching the required schema as soon as you "
        "have covered all pages (or hit the 3-page cap) - do not over-verify."
    )
    return base


async def scrape_page(url: str, paginate: bool = False) -> ProductList:
    llm = build_llm()
    browser_profile = BrowserProfile(headless=True, chromium_sandbox=False)
    agent = Agent(
        task=build_task(url, paginate=paginate),
        llm=llm,
        output_model_schema=ProductList,
        use_vision=True,
        browser_profile=browser_profile,
        max_failures=3,
    )
    max_steps = 20 if paginate else 10
    timeout = 240 if paginate else 90
    try:
        history = await asyncio.wait_for(agent.run(max_steps=max_steps), timeout=timeout)
    except asyncio.TimeoutError:
        raise RuntimeError(
            f"Scraping timed out after {timeout} seconds. The page might be too complex "
            "or the AI is taking too long to reason."
        )
    result = history.structured_output
    if result is None:
        raise RuntimeError("Agent did not return structured output.")
    return result


def write_csv(products: ProductList, path: str) -> None:
    fieldnames = ["name", "price", "original_price", "rating", "image_url", "availability", "needs_review"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in products.products:
            writer.writerow(p.model_dump())


async def main():
    args = [a for a in sys.argv[1:] if a != "--paginate"]
    paginate = "--paginate" in sys.argv
    url = args[0] if len(args) > 0 else "https://demo.saleor.io/en/default"
    output_path = args[1] if len(args) > 1 else "output.csv"

    print(f"Scraping: {url} (paginate={paginate})")
    result = await scrape_page(url, paginate=paginate)

    print(f"\nExtracted {len(result.products)} products:")
    for p in result.products:
        flag = f" | ⚠️ NEEDS REVIEW: {p.needs_review}" if p.needs_review else ""
        print(f"  - {p.name} | price={p.price} | original={p.original_price} | "
              f"rating={p.rating} | availability={p.availability}{flag}")

    write_csv(result, output_path)
    print(f"\nWritten to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())