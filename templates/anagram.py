"""Anagram template handler.

Markdown entry format:
    With clues:    - word :: clue
    Without clues: - word

Mode is auto-detected: if any entry has a clue, "With clues" is selected.
"""

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from .base import fill_contenteditable, goto_create, set_title, save_activity, add_item


def create(page: Page, entries: list[dict], title: str = "") -> None:
    print("Looking for Anagram template...")
    goto_create(page, "Anagram")
    print(f"URL after selecting Anagram: {page.url}")

    set_title(page, title)

    has_clues = any(e["clue"] for e in entries)

    if has_clues:
        print("Selecting 'With clues' option...")
        try:
            page.click("label:has-text('With clues')", timeout=5000)
        except PlaywrightTimeout:
            try:
                page.locator("text=With clues").locator("..").locator("input[type='radio']").click(timeout=3000)
            except PlaywrightTimeout:
                print("WARNING: Could not find 'With clues' radio — taking screenshot.")
                page.screenshot(path="debug/debug_anagram_clues.png")
    else:
        print("Selecting 'Without clues' option...")
        try:
            page.click("label:has-text('Without clues')", timeout=5000)
        except PlaywrightTimeout:
            try:
                page.locator("text=Without clues").locator("..").locator("input[type='radio']").click(timeout=3000)
            except PlaywrightTimeout:
                print("WARNING: Could not find 'Without clues' radio — taking screenshot.")
                page.screenshot(path="debug/debug_anagram_no_clues.png")

    page.wait_for_load_state("networkidle")

    for i, entry in enumerate(entries):
        print(f"  Adding entry {i+1}: {entry['word']}")

        if i > 0:
            add_item(page)

        word_divs = page.locator("div.js-item-input[data-mobile-placeholder='Word']")

        try:
            fill_contenteditable(page, word_divs.nth(i), entry["word"])

            if has_clues and entry["clue"]:
                clue_divs = page.locator("div.js-item-input[data-mobile-placeholder='Clue']")
                fill_contenteditable(page, clue_divs.nth(i), entry["clue"])
        except Exception as e:
            print(f"  Warning: could not fill entry {i+1}: {e}")
            page.screenshot(path=f"debug/debug_anagram_entry_{i+1}.png")

    save_activity(page)
