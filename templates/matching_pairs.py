"""Matching Pairs template handler.

Two modes (auto-detected from entries):

    Identical items — list of text (no '::'):
        - word

    Pairs of different items — text + image (with '::'):
        - definition :: <image:path/to/image.png>
"""

import re
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from .base import fill_contenteditable, goto_create, set_title, save_activity, add_item, upload_image


def create(page: Page, entries: list[dict], title: str = "") -> None:
    print("Looking for Matching Pairs template...")
    goto_create(page, "Matching pairs")
    print(f"URL after selecting Matching Pairs: {page.url}")

    set_title(page, title)

    has_pairs = any(e["clue"] for e in entries)

    if has_pairs:
        print("Selecting 'Pairs of different items' option...")
        try:
            page.click("label:has-text('Pairs of different items'), label:has-text('Different')", timeout=5000)
        except PlaywrightTimeout:
            print("WARNING: Could not find 'Pairs of different items' radio — taking screenshot.")
            page.screenshot(path="debug/debug_matching_pairs_mode.png")
    else:
        print("Selecting 'Identical items' option...")
        try:
            page.click("label:has-text('Identical items'), label:has-text('Identical')", timeout=5000)
        except PlaywrightTimeout:
            print("WARNING: Could not find 'Identical items' radio — taking screenshot.")
            page.screenshot(path="debug/debug_matching_pairs_identical.png")

    page.wait_for_load_state("networkidle")

    for i, entry in enumerate(entries):
        print(f"  Adding entry {i+1}: {entry['word']}")

        if i > 0:
            add_item(page)

        # All inputs have data-mobile-placeholder="" — use global nth indexing
        all_inputs = page.locator("div.js-item-input[data-mobile-placeholder='']")

        try:
            if has_pairs:
                # 2 inputs per item: left = i*2, right = i*2+1
                fill_contenteditable(page, all_inputs.nth(i * 2), entry["word"])

                image_match = re.match(r"^<image:(.+)>$", entry["clue"] or "")
                if image_match:
                    image_path = image_match.group(1)
                    print(f"    Uploading pair image: {image_path}")
                    image_btn = all_inputs.nth(i * 2 + 1).locator(
                        "xpath=ancestor::div[contains(@class,'double-inner')]"
                    ).locator("span.js-item-image-placeholder")
                    image_btn.click(timeout=5000)
                    upload_image(page, image_path)
                elif entry["clue"]:
                    fill_contenteditable(page, all_inputs.nth(i * 2 + 1), entry["clue"])
            else:
                # 1 input per item: index = i
                fill_contenteditable(page, all_inputs.nth(i), entry["word"])

        except Exception as e:
            print(f"  Warning: could not fill entry {i+1}: {e}")
            page.screenshot(path=f"debug/debug_matching_entry_{i+1}.png")

    save_activity(page)
