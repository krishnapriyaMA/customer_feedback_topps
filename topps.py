import requests
import re
import json
from datetime import datetime
from config import TOPPS_HEADERS, TOPPS_BASE_URL


# =========================================================
# GET TOTAL REVIEW COUNT FROM PRODUCT HTML
# =========================================================

def get_topps_review_count_from_html(product_url):

    # Full browser-like headers to avoid 403 / Cloudflare blocks
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    try:
        session = requests.Session()
        response = session.get(
            product_url,
            headers=headers,
            timeout=30,
            allow_redirects=True,
        )
    except requests.RequestException as e:
        print(f"HTML fetch exception: {e}")
        return 0

    if response.status_code != 200:
        print(f"HTML fetch failed: {response.status_code} — URL: {product_url}")
        return 0

    html = response.text

    json_ld_blocks = re.findall(
        r'<script type="application/ld\+json".*?>(.*?)</script>',
        html,
        re.DOTALL,
    )

    for block in json_ld_blocks:
        try:
            data = json.loads(block.strip())
            if isinstance(data, dict) and "aggregateRating" in data:
                return int(
                    data["aggregateRating"].get("reviewCount", 0)
                )
        except Exception:
            continue

    # Fallback: look for reviewCount anywhere in the page JSON-LD
    # (some pages nest the schema inside a @graph array)
    for block in json_ld_blocks:
        try:
            data = json.loads(block.strip())
            if isinstance(data, dict) and "@graph" in data:
                for node in data["@graph"]:
                    if isinstance(node, dict) and "aggregateRating" in node:
                        return int(
                            node["aggregateRating"].get("reviewCount", 0)
                        )
        except Exception:
            continue

    print(f"No aggregateRating found in JSON-LD for: {product_url}")
    return 0


# =========================================================
# GET REVIEWS FROM BAZAARVOICE API
# =========================================================

def get_reviews(product_id):

    offset = 0
    limit = 50

    all_reviews = []
    seen_ids = set()

    while True:

        params = [
            ("resource", "reviews"),
            ("action", "REVIEWS_N_STATS"),
            ("filter", f"productid:eq:{product_id}"),
            ("filter", "contentlocale:eq:en_GB,en_GB"),
            ("filter", "isratingsonly:eq:false"),
            ("include", "authors,products,comments"),
            ("filteredstats", "reviews"),
            ("Stats", "Reviews"),
            ("limit", str(limit)),
            ("offset", str(offset)),
            ("sort", "submissiontime:desc"),
            ("apiversion", "5.5"),
            ("displaycode", "6987-en_gb"),
        ]

        try:

            response = requests.get(
                TOPPS_BASE_URL,
                params=params,
                headers=TOPPS_HEADERS,
                timeout=30,
            )

            if response.status_code != 200:
                print(f"Topps API error: {response.status_code}")
                break

            data = response.json()

            response_data = data.get("response", {})
            results = response_data.get("Results", [])

            if not results:
                break

            for r in results:

                review_id = r.get("Id")

                if r.get("ProductId") != product_id:
                    continue

                if review_id in seen_ids:
                    continue

                seen_ids.add(review_id)

                submission_time = r.get("SubmissionTime")
                if not submission_time:
                    continue

                review_date = datetime.fromisoformat(
                    submission_time.replace("Z", "+00:00")
                ).replace(tzinfo=None)

                all_reviews.append({
                    "date": review_date,
                    "rating": r.get("Rating"),
                    "comment": r.get("ReviewText", ""),
                })

            offset += limit

        except Exception as e:
            print(f"Topps API exception: {e}")
            break

    low_rating_reviews = [
        r for r in all_reviews
        if r["rating"] is not None and r["rating"] < 4
    ]

    total_low_reviews = len(low_rating_reviews)
    print(f"Topps reviews below 4 stars: {total_low_reviews}")

    return total_low_reviews, all_reviews