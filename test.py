from playwright.sync_api import sync_playwright

URL = "https://www.toppstiles.co.uk/flooring/luxury-vinyl-tiles/pronto-avebury-grey-slate-luxury-vinyl-tile"

all_reviews = []

with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    page = browser.new_page(viewport={"width": 1600, "height": 900})

    page.goto(URL, wait_until="networkidle")

    page.wait_for_timeout(5000)

    # Accept cookies
    try:
        page.get_by_role("button", name="ACCEPT ALL COOKIES").click(timeout=3000)
        page.wait_for_timeout(2000)
    except:
        pass

    # Scroll to reviews
    page.locator("#reviews").scroll_into_view_if_needed()
    page.wait_for_timeout(3000)

    page_no = 1

    while True:

        print(f"\n========== PAGE {page_no} ==========\n")

        container = page.locator("div.b-a.b-col-4.b-w-2.bg-col-51")

        text = container.inner_text()

        # Split reviews
        reviews = text.split("Helpful?")

        for review in reviews:

            review = review.strip()

            if len(review) < 30:
                continue

            print("=" * 80)
            print(review)
            print()

            all_reviews.append(review)

        # Go to next page
        try:
            next_btn = page.get_by_role("button", name="Next Reviews")

            if not next_btn.is_enabled():
                break

            old_text = text

            next_btn.click()

            page.wait_for_function(
                """(oldText)=>{
                    return document
                    .querySelector("div.b-a.b-col-4.b-w-2.bg-col-51")
                    .innerText !== oldText
                }""",
                arg=old_text,
                timeout=10000
            )

            page_no += 1

        except Exception:
            print("No more pages.")
            break

    browser.close()

# Save all reviews
with open("reviews.txt", "w", encoding="utf-8") as f:

    for review in all_reviews:
        f.write(review)
        f.write("\n")
        f.write("=" * 120)
        f.write("\n\n")

print(f"\nDone. Saved {len(all_reviews)} review blocks.")