"""Balloon Pop template handler.

Minimum 5 items required.

Markdown entry formats:
    - keyword :: definition         (both text)
    - <image:path> :: definition    (image keyword, text definition)

Note: in wordwall_templates.md use '<image> :: description' as placeholder;
wordwall_generate_clues.py will replace '<image>' with '<image:path>'.
"""

import re
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from .base import fill_contenteditable, goto_create, set_title, save_activity, add_item, upload_image


def create(page: Page, entries: list[dict], title: str = "") -> None:
    if len(entries) < 5:
        print(f"WARNING: Balloon Pop requires at least 5 items, got {len(entries)}. Skipping.")
        return

    print("Looking for Balloon Pop template...")
    goto_create(page, "Balloon pop")
    print(f"URL after selecting Balloon Pop: {page.url}")

    set_title(page, title)
    page.wait_for_load_state("networkidle")

    for i, entry in enumerate(entries):
        print(f"  Adding entry {i+1}: {entry['word']} / {entry['clue']}")

        if i > 0:
            add_item(page)

        keyword_divs = page.locator("div.js-item-input[data-mobile-placeholder='Keyword']")
        definition_divs = page.locator("div.js-item-input[data-mobile-placeholder='Matching definition']")

        try:
            # Keyword: may be an image or text
            image_match = re.match(r"^<image:(.+)>$", entry["word"] or "")
            if image_match:
                image_path = image_match.group(1)
                print(f"    Uploading keyword image: {image_path}")
                image_btn = keyword_divs.nth(i).locator(
                    "xpath=ancestor::div[contains(@class,'double-inner')]"
                ).locator("span.js-item-image-placeholder")
                image_btn.click(timeout=5000)
                upload_image(page, image_path)
            else:
                fill_contenteditable(page, keyword_divs.nth(i), entry["word"])

            # Definition: may be an image or text
            if entry["clue"]:
                def_image_match = re.match(r"^<image:(.+)>$", entry["clue"])
                if def_image_match:
                    def_image_path = def_image_match.group(1)
                    print(f"    Uploading definition image: {def_image_path}")
                    image_btn = definition_divs.nth(i).locator(
                        "xpath=ancestor::div[contains(@class,'double-inner')]"
                    ).locator("span.js-item-image-placeholder")
                    image_btn.click(timeout=5000)
                    upload_image(page, def_image_path)
                else:
                    fill_contenteditable(page, definition_divs.nth(i), entry["clue"])

        except Exception as e:
            print(f"  Warning: could not fill entry {i+1}: {e}")
            page.screenshot(path=f"debug/debug_balloon_entry_{i+1}.png")

    save_activity(page)
