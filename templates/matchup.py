"""Match Up template handler (word → image).

Markdown entry format:
    - word :: <image:path/to/image.png>
"""

import re
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from .base import fill_contenteditable, goto_create, set_title, save_activity, add_item, upload_image


def create(page: Page, entries: list[dict], title: str = "") -> None:
    if len(entries) < 3:
        print(f"WARNING: Match Up requires at least 3 items, got {len(entries)}. Skipping.")
        return

    print("Looking for Match Up template...")
    goto_create(page, "Match up")
    print(f"URL after selecting Match Up: {page.url}")

    set_title(page, title)
    page.wait_for_load_state("networkidle")

    for i, entry in enumerate(entries):
        print(f"  Adding entry {i+1}: {entry['word']} / {entry['clue']}")

        if i > 0:
            add_item(page)

        word_divs = page.locator("div.js-item-input[data-mobile-placeholder='Keyword']")
        clue_divs = page.locator("div.js-item-input[data-mobile-placeholder='Matching definition']")

        try:
            fill_contenteditable(page, word_divs.nth(i), entry["word"])

            image_match = re.match(r"^<image:(.+)>$", entry["clue"] or "")
            if image_match:
                image_path = image_match.group(1)
                print(f"    Uploading image: {image_path}")
                image_btn = clue_divs.nth(i).locator(
                    "xpath=ancestor::div[contains(@class,'double-inner')]"
                ).locator("span.js-item-image-placeholder")
                image_btn.click(timeout=5000)
                upload_image(page, image_path)
            else:
                fill_contenteditable(page, clue_divs.nth(i), entry["clue"])
        except Exception as e:
            print(f"  Warning: could not fill entry {i+1}: {e}")
            page.screenshot(path=f"debug/debug_matchup_entry_{i+1}.png")

    save_activity(page)
