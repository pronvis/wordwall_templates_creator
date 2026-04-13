"""HangMan template handler.

Markdown entry format:
    - word :: text clue
    - word :: <image:path/to/image.png>
"""

import re
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from .base import fill_contenteditable, goto_create, set_title, save_activity, add_item, upload_image

CLUE_PLACEHOLDER = "??"


def create(page: Page, entries: list[dict], title: str = "") -> None:
    print("Looking for HangMan template...")
    goto_create(page, "Hangman")
    print(f"URL after selecting HangMan: {page.url}")

    set_title(page, title)

    print("Selecting 'With clues' option...")
    try:
        page.click("label:has-text('With clues')", timeout=5000)
    except PlaywrightTimeout:
        try:
            page.locator("text=With clues").locator("..").locator("input[type='radio']").click(timeout=3000)
        except PlaywrightTimeout:
            print("WARNING: Could not find 'With clues' radio button — taking screenshot.")
            page.screenshot(path="debug/debug_with_clues.png")
            return

    page.wait_for_load_state("networkidle")

    for i, entry in enumerate(entries):
        print(f"  Adding entry {i+1}: {entry['word']} / {entry['clue']}")

        if i > 0:
            add_item(page)

        word_divs = page.locator("div.js-item-input[data-mobile-placeholder='Word']")
        clue_divs = page.locator("div.js-item-input[data-mobile-placeholder='Clue']")

        print(f"    Word divs: {word_divs.count()}, Clue divs: {clue_divs.count()}")

        try:
            if entry["clue"] == CLUE_PLACEHOLDER:
                print(f"  WARNING: clue for '{entry['word']}' is still '??'. Run wordwall_generate_clues.py first.")
                continue

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
            page.screenshot(path=f"debug/debug_entry_{i+1}.png")

    save_activity(page)
