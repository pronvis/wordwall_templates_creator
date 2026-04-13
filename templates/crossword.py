"""Crossword template handler (text clues only).

Markdown entry format:
    - word :: clue
"""

from playwright.sync_api import Page

from .base import fill_contenteditable, goto_create, set_title, save_activity, add_item


def create(page: Page, entries: list[dict], title: str = "") -> None:
    print("Looking for Crossword template...")
    goto_create(page, "Crossword")
    print(f"URL after selecting Crossword: {page.url}")

    set_title(page, title)
    page.wait_for_load_state("networkidle")

    for i, entry in enumerate(entries):
        print(f"  Adding entry {i+1}: {entry['word']} / {entry['clue']}")

        if i > 0:
            add_item(page)

        word_divs = page.locator("div.js-item-input[data-mobile-placeholder='Answer']")
        clue_divs = page.locator("div.js-item-input[data-mobile-placeholder='Clue']")

        try:
            fill_contenteditable(page, word_divs.nth(i), entry["word"])
            if entry["clue"]:
                fill_contenteditable(page, clue_divs.nth(i), entry["clue"])
        except Exception as e:
            print(f"  Warning: could not fill entry {i+1}: {e}")
            page.screenshot(path=f"debug/debug_crossword_entry_{i+1}.png")

    save_activity(page)
