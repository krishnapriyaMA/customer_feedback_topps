import re
import datetime
import pandas as pd
from playwright.sync_api import sync_playwright

def extract_rating(review_text: str) -> int:
    match = re.search(r"(\d)\s+out\s+of\s+5\s+stars", review_text, re.IGNORECASE)
    return int(match.group(1)) if match else 5

def extract_review_date_str(review_text: str) -> str:
    for line in review_text.split("\n"):
        if "ago" in line.lower():
            return line.strip()
    return "Recent"


NOISE_PATTERNS = [
    r"\d\s+stars?\s+stars(\s+\d\s+stars?\s+stars)*",          # star breakdown bar
    r"[\w /]+,\s*\d\.\d\s+out of 5",                          # sub-ratings e.g. "Quality of product, 3.0 out of 5"
    r"\bOverall look/style of product\b",
    r"\bQuality of product\b",
    r"\bValue for money\b",
    r"\bCustomer Images and Videos\b",
    r"\bReport\b",
    r"\bHelpful\?\b",
    r"\bRating\b",
    r"\b(purchase|quality|cutting|installation|product availability|cleaning|shortcoming|closing|ease of use|finish)\b",
]
import re
import re


def extract_comment_body(review_text: str) -> str:
    """
    Isolates and extracts ONLY the core review comment text block.
    Anchors on the reviewer's own rating marker ("X out of 5 stars.")
    and the date that immediately follows it, then captures everything
    after that up to the next known stop marker (Q&A, recommend
    footer, or a seller response block).
    """
    m = re.search(
        r"\d\s+out\s+of\s+5\s+stars\.\s*.*?"
        r"(?:\d+\s+)?(?:day|week|month|year)s?\s+ago\s*(.*)",
        review_text, re.IGNORECASE | re.DOTALL
    )
    if not m:
        return "Empty Comment"
 
    comment = m.group(1)
 
    stop_match = re.search(
        r"(Q:|Yes, I recommend|No, I do not recommend|Response from|Originally posted on)",
        comment, re.IGNORECASE
    )
    if stop_match:
        comment = comment[:stop_match.start()]
 
    comment = re.sub(r"\s+", " ", comment).strip()
    return comment if comment else "Empty Comment"
def extract_originally_posted_product(review_text: str):
    """
    If this review carries an 'Originally posted on <product>' footer,
    return that product name. Returns None if the review is native to
    the current page (no syndication footer at all).
    """
    match = re.search(r"Originally posted on\s+(.+)", review_text, re.IGNORECASE)
    if not match:
        return None
    name = match.group(1)
    # cut at the block separator / next junk section if present
    name = re.split(r"={5,}|\n\(0\)|\nReport\b", name)[0]
    return name.strip()
 
def normalize_product_name(name: str) -> str:
    if not name:
        return ""
    name = name.lower()
    name = name.replace("™", "").replace("®", "")
    name = re.sub(r"\s+", " ", name).strip()
    return name
def extract_review_datetime_obj(date_str: str) -> datetime.date:
    today = datetime.date.today()
    clean_text = date_str.lower()
    
    # 1. Matches "a year ago" or "2 years ago"
    if "year" in clean_text: 
        match = re.search(r"(\d+)", clean_text)
        years = int(match.group(1)) if match else 1
        return today - datetime.timedelta(days=365 * years)
        
    # 2. Matches "7 months ago" or "a month ago"
    if "month" in clean_text:
        match = re.search(r"(\d+)", clean_text)
        months = int(match.group(1)) if match else 1
        return today - datetime.timedelta(days=30 * months)
        
    # 3. Matches "3 weeks ago" or "a week ago"
    if "week" in clean_text:
        match = re.search(r"(\d+)", clean_text)
        weeks = int(match.group(1)) if match else 1
        return today - datetime.timedelta(days=7 * weeks)
        
    # 4. Matches "4 days ago" or "yesterday"
    if "day" in clean_text or "yesterday" in clean_text:
        match = re.search(r"(\d+)", clean_text)
        days = int(match.group(1)) if match else 1
        return today - datetime.timedelta(days=days)
        
    # Default fallback if format doesn't match standard terms
    return today

def pass_rating_filter(rating: int, rating_type: str, threshold: int = None, selected_ratings: list = None) -> bool:
    if rating_type == "all": return True
    if rating_type == "negative": return rating in [1, 2]
    if rating_type == "threshold" and threshold: return rating <= threshold
    if rating_type == "custom" and selected_ratings: return rating in selected_ratings
    return True

def pass_date_filter(review_date: datetime.date, start_date: datetime.date, end_date: datetime.date) -> bool:
    if start_date and review_date < start_date: return False
    if end_date and review_date > end_date: return False
    return True

def run_scraper_to_memory(input_path: str, start_date_str: str, end_date_str: str, rating_type: str, threshold: int, selected_ratings: list):
    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None
    end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None

    try:
        df = pd.read_excel(input_path)
    except Exception as e:
        return False, f"Failed reading Excel: {str(e)}"

    scraped_records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for index, row in df.iterrows():
            url = str(row["Website Link"]).strip()
            sku = str(row.get("SKU", "N/A"))
            supplier = str(row.get("Supplier Code", "Unknown Supplier")) 
            
            if not url or url == "nan" or not url.startswith("http"):
                continue

            print(f"🚀 Working Row {index+1}: [SKU: {sku}] -> {url}")
            context = browser.new_context(viewport={"width": 1600, "height": 900})
            page = context.new_page()
            product_name = "Unknown Product"

            try:
                page.goto(url, wait_until="networkidle")
                page.wait_for_timeout(4000)

                try:
                    page.get_by_role("button", name="ACCEPT ALL COOKIES").click(timeout=2000)
                    page.wait_for_timeout(1000)
                except: pass

                page.locator("#reviews").scroll_into_view_if_needed()
                page.wait_for_timeout(2000)

                try: product_name = page.locator("h1").inner_text().strip()
                except: pass

                page_no = 1
                while True:
                    container = page.locator("div.b-a.b-col-4.b-w-2.bg-col-51")
                    if not container.is_visible(timeout=2000): 
                        break

                    text = container.inner_text()
                    review_blocks = text.split("Helpful?")

                    for block in review_blocks:
                        block = block.strip()
                        if len(block) < 30 or "out of 5 stars" not in block: continue

                        rating = extract_rating(block)
                        if not pass_rating_filter(rating, rating_type, threshold, selected_ratings): continue

                        raw_date_str = extract_review_date_str(block)
                        date_obj = extract_review_datetime_obj(raw_date_str)
                        if not pass_date_filter(date_obj, start_date, end_date): continue
                        origin_product = extract_originally_posted_product(block)
                        if origin_product and normalize_product_name(origin_product) != normalize_product_name(product_name):
                            continue

                        comment = extract_comment_body(block)

                        scraped_records.append({
                            "SKU": sku,
                            "Supplier Code": supplier,
                            "Product Name": product_name,
                            "rating_num": rating,
                            "Rating": f"{rating} ★",
                            "Date Context": raw_date_str,
                            "Comment Body": comment
                        })

                    try:
                        next_btn = page.locator("#reviews a.next[role='button']").first
                        if not next_btn.is_visible(timeout=2000):
                            break
                        btn_class = next_btn.get_attribute("class") or ""
                        if "disabled" in btn_class:
                            break
 
                        next_btn.click()
                        page.wait_for_timeout(3000)
                        page_no += 1
                    except:
                        break

            except Exception as e:
                print(f"⚠️ Row Exception handled: {str(e)}")
            finally:
                context.close()
                
        browser.close()

    return True, scraped_records