#!/usr/bin/env python3
"""
Wordwall template automation bot.
Reads wordwall_templates.md and wordwall_auth.env, then creates templates on wordwall.net.
"""

import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
CLUE_PLACEHOLDER = "??"


def parse_env(path: str) -> dict:
    env = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        env[key.strip()] = value.strip()
    return env


def parse_markdown(path: str) -> tuple[str, list[dict]]:
    """
    Returns (folder_name, templates) where:
      - folder_name is the H1 heading (e.g. "Masha"), or "" if absent
      - templates is a list of:
        [{"type": "HangMan", "title": "My generated activity #1", "entries": [...]}]

    Each # sets the folder name.
    Each ## sets the current template type.
    Each ### starts a new activity with that type.
    """
    folder_name = ""
    templates = []
    current_type = ""
    current = None

    for line in Path(path).read_text().splitlines():
        # H1 heading = folder name (e.g. Masha)
        h1 = re.match(r"^#\s+(.+)$", line)
        if h1:
            folder_name = h1.group(1).strip()
            continue

        # H2 heading = template type (e.g. HangMan)
        h2 = re.match(r"^##\s+(.+)$", line)
        if h2:
            if current:
                templates.append(current)
                current = None
            current_type = h2.group(1).strip()
            continue

        # H3 heading = new activity with the current type
        h3 = re.match(r"^###\s+(.+)$", line)
        if h3 and current_type:
            if current:
                templates.append(current)
            current = {"type": current_type, "title": h3.group(1).strip(), "entries": []}
            continue

        # List item: "- word :: clue"
        item = re.match(r"^-\s+(.+?)\s*::\s*(.+)$", line)
        if item and current is not None:
            current["entries"].append({"word": item.group(1).strip(), "clue": item.group(2).strip()})

    if current:
        templates.append(current)

    return folder_name, templates


def login(page, email: str, password: str):
    print("Navigating to wordwall.net...")
    page.goto("https://wordwall.net/")
    page.wait_for_load_state("networkidle")

    print("Clicking Log in...")
    page.click("text=Log in")
    page.wait_for_load_state("networkidle")

    print("Filling credentials...")
    page.fill('input[type="email"], input[name="email"], #email', email)
    page.fill('input[type="password"], input[name="password"], #password', password)
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_load_state("networkidle")

    print(f"Current URL after login: {page.url}")


def create_hangman(page, entries: list[dict], title: str = ""):
    """Create a HangMan activity on wordwall.net."""
    print("Navigating to create new activity...")
    page.goto("https://wordwall.net/create")
    page.wait_for_load_state("networkidle")

    print("Looking for HangMan template...")
    try:
        page.click("text=Hangman", timeout=5000)
    except PlaywrightTimeout:
        hangman = page.locator('[class*="template"]:has-text("Hang"), [class*="activity"]:has-text("Hang")')
        hangman.first.click()

    page.wait_for_load_state("networkidle")
    print(f"URL after selecting HangMan: {page.url}")

    # Set activity title if provided
    if title:
        print(f"Setting title: {title}")
        try:
            title_input = page.locator("input[type='text']").first
            title_input.click(timeout=3000)
            title_input.fill(title)
        except PlaywrightTimeout:
            print("WARNING: could not set title — taking screenshot.")
            page.screenshot(path="debug/debug_title.png")

    # Select "With clues" radio button
    print("Selecting 'With clues' option...")
    try:
        page.click("label:has-text('With clues')", timeout=5000)
    except PlaywrightTimeout:
        try:
            # Fallback: find radio input next to the text
            page.locator("text=With clues").locator("..").locator("input[type='radio']").click(timeout=3000)
        except PlaywrightTimeout:
            print("WARNING: Could not find 'With clues' radio button — taking screenshot.")
            page.screenshot(path="debug/debug_with_clues.png")
            return

    page.wait_for_load_state("networkidle")

    def fill_contenteditable(locator, text: str):
        """Clear and fill a contenteditable div."""
        locator.click()
        page.keyboard.press("Control+a")
        page.keyboard.type(text)

    # Fill in entries row by row.
    # Only 1 row exists initially; click "+ Add a word" before each entry after the first.
    for i, entry in enumerate(entries):
        print(f"  Adding entry {i+1}: {entry['word']} / {entry['clue']}")

        if i > 0:
            add_btn = page.locator(".js-add-item, [class*='add-item'], [class*='add-word']").first
            try:
                add_btn.click(timeout=3000)
            except PlaywrightTimeout:
                # Fallback: find by text inside any clickable element
                page.locator("//*[contains(text(),'Add a word')]").first.click(timeout=3000)
            page.wait_for_timeout(400)

        # Contenteditable word/clue divs, in order of appearance
        word_divs = page.locator("div.js-item-input[data-mobile-placeholder='Word']")
        clue_divs = page.locator("div.js-item-input[data-mobile-placeholder='Clue']")

        print(f"    Word divs: {word_divs.count()}, Clue divs: {clue_divs.count()}")

        try:
            if entry["clue"] == CLUE_PLACEHOLDER:
                print(f"  WARNING: clue for '{entry['word']}' is still '??'. Run wordwall_generate_clues.py first.")
                continue

            fill_contenteditable(word_divs.nth(i), entry["word"])

            image_match = re.match(r"^<image:(.+)>$", entry["clue"])
            if image_match:
                image_path = image_match.group(1)
                print(f"    Uploading image: {image_path}")
                # Step 1: click "Add Image" span to open the modal
                image_btn = clue_divs.nth(i).locator(
                    "xpath=ancestor::div[contains(@class,'double-inner')]"
                ).locator("span.js-item-image-placeholder")
                image_btn.click(timeout=5000)
                # Step 2: wait for modal, then click Upload and set file
                with page.expect_file_chooser() as fc:
                    page.locator("a#upload_image_button").click(timeout=5000)
                fc.value.set_files(image_path)
                page.wait_for_timeout(500)
            else:
                fill_contenteditable(clue_divs.nth(i), entry["clue"])
        except Exception as e:
            print(f"  Warning: could not fill entry {i+1}: {e}")
            page.screenshot(path=f"debug/debug_entry_{i+1}.png")

    # Save / Done
    print("Saving activity...")
    try:
        page.click("text=Done", timeout=5000)
    except PlaywrightTimeout:
        try:
            page.click("text=Save", timeout=5000)
        except PlaywrightTimeout:
            print("Could not find Save/Done button — taking screenshot for debugging.")
            page.screenshot(path="debug/debug_save.png")
            return

    page.wait_for_load_state("networkidle")
    print(f"Activity saved. URL: {page.url}")


TEMPLATE_HANDLERS = {
    "hangman": create_hangman,
}


def move_to_folder(page, folder_name: str, titles: list[str]):
    """Navigate to My Activity, create a folder if needed, and move the given activities into it."""
    if not folder_name or not titles:
        return

    print(f"\nNavigating to My Activity to move templates into folder '{folder_name}'...")
    try:
        page.goto("https://wordwall.net/myactivities", wait_until="commit")
        page.wait_for_load_state("networkidle")
    except Exception:
        # Fallback: click "My Activities" link in the nav
        page.goto("https://wordwall.net", wait_until="commit")
        page.wait_for_load_state("networkidle")
        page.get_by_text("My Activities").first.click(timeout=5000)
        page.wait_for_load_state("networkidle")
    print(f"My Activities URL: {page.url}")

    # Try to find existing folder or create a new one
    existing_folder = page.locator(f"[class*='folder']:has-text('{folder_name}'), [class*='group']:has-text('{folder_name}')")
    if existing_folder.count() == 0:
        print(f"Creating new folder '{folder_name}'...")
        try:
            # Click "+ New folder" button
            page.locator("button.js-create-folder").click(timeout=5000)
            page.wait_for_timeout(500)
            # Fill folder name in the modal input
            page.locator(".js-modal-content input.js-input-text").fill(folder_name)
            # Click "Create" button in the modal
            page.get_by_role("button", name="Create").click(timeout=5000)
            page.wait_for_timeout(1000)
        except PlaywrightTimeout:
            print(f"WARNING: Could not create folder '{folder_name}' — taking screenshot.")
            page.screenshot(path="debug/debug_create_folder.png")
            return

    # Move each activity into the folder
    for title in titles:
        print(f"  Moving '{title}' into folder '{folder_name}'...")
        try:
            # Find the card that contains this title and has a ⋮ menu, click the menu
            card = page.locator(f"*:has-text('{title}'):has(.js-item-menu)").last
            card.locator(".js-item-menu").first.click(timeout=5000)
            page.wait_for_timeout(300)

            # Click "Move"
            page.locator("a.js-move-to").click(timeout=5000)
            page.wait_for_timeout(300)

            # Select the target folder by name
            page.locator(f".js-destination-folder-name:text('{folder_name}')").click(timeout=5000)
            page.wait_for_timeout(500)
            print(f"    Moved '{title}' successfully.")
        except Exception as e:
            print(f"  WARNING: Could not move '{title}': {e}")
            page.screenshot(path=f"debug/debug_move_{title[:20].replace(' ', '_')}.png")


def main():
    env_path = "wordwall_auth.env"
    md_path = sys.argv[1] if len(sys.argv) > 1 else "wordwall_templates.md"

    env = parse_env(env_path)
    email = env.get("login", "")
    password = env.get("password", "")

    if not email or not password:
        print("ERROR: Could not read login/password from wordwall_auth.env")
        sys.exit(1)

    folder_name, templates = parse_markdown(md_path)
    if not templates:
        print("ERROR: No templates found in wordwall_templates.md")
        sys.exit(1)

    if folder_name:
        print(f"Folder: '{folder_name}'")
    print(f"Found {len(templates)} template(s) to create:")
    for t in templates:
        print(f"  - {t['type']}: {t['title']} ({len(t['entries'])} entries)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        context = browser.new_context()
        page = context.new_page()

        login(page, email, password)

        created_titles = []
        for template in templates:
            ttype = template["type"].lower()
            handler = TEMPLATE_HANDLERS.get(ttype)
            if handler is None:
                print(f"WARNING: No handler for template type '{template['type']}' — skipping.")
                continue
            print(f"\nCreating '{template['type']}' template: {template['title']}...")
            handler(page, template["entries"], template.get("title", ""))
            created_titles.append(template["title"])

        if folder_name and created_titles:
            move_to_folder(page, folder_name, created_titles)

        print("\nAll done! Press Enter to close the browser.")
        input()
        browser.close()


if __name__ == "__main__":
    main()
