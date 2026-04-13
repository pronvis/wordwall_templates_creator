#!/usr/bin/env python3
"""
Wordwall template automation bot.
Reads a wordwall markdown file and wordwall_auth.env, then creates templates on wordwall.net.
"""

import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from templates import TEMPLATE_HANDLERS


def parse_env(path: str) -> dict:
    env = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        env[key.strip()] = value.strip()
    return env


def parse_markdown(path: str) -> list[tuple[str, list[dict]]]:
    """
    Returns a list of (folder_name, templates) groups, one per H1 section.
      - folder_name is the H1 heading (e.g. "Masha"), or "" if no H1 precedes the templates
      - templates is a list of:
        [{"type": "HangMan", "title": "My generated activity #1", "entries": [...]}]

    Entry formats supported:
      - word :: clue   →  {"word": "word", "clue": "clue"}
      - word           →  {"word": "word", "clue": None}

    Each # starts a new folder group.
    Each ## sets the current template type.
    Each ### starts a new activity with that type.
    """
    groups: list[tuple[str, list[dict]]] = []
    current_folder = ""
    current_group: list[dict] = []
    current_type = ""
    current: dict | None = None

    def flush_template() -> None:
        nonlocal current
        if current:
            current_group.append(current)
            current = None

    def flush_group() -> None:
        nonlocal current_folder, current_group
        flush_template()
        if current_group:
            groups.append((current_folder, current_group))
        current_folder = ""
        current_group = []

    for line in Path(path).read_text().splitlines():
        h1 = re.match(r"^#\s+(.+)$", line)
        if h1:
            flush_group()
            current_folder = h1.group(1).strip()
            continue

        h2 = re.match(r"^##\s+(.+)$", line)
        if h2:
            flush_template()
            current_type = h2.group(1).strip()
            continue

        h3 = re.match(r"^###\s+(.+)$", line)
        if h3 and current_type:
            flush_template()
            current = {"type": current_type, "title": h3.group(1).strip(), "entries": []}
            continue

        if current is None:
            continue

        # Entry with clue: "- word :: clue"
        item_with_clue = re.match(r"^-\s+(.+?)\s*::\s*(.+)$", line)
        if item_with_clue:
            current["entries"].append({
                "word": item_with_clue.group(1).strip(),
                "clue": item_with_clue.group(2).strip(),
            })
            continue

        # Entry without clue: "- word"
        item_no_clue = re.match(r"^-\s+(.+)$", line)
        if item_no_clue:
            current["entries"].append({
                "word": item_no_clue.group(1).strip(),
                "clue": None,
            })

    flush_group()
    return groups


def login(page, email: str, password: str) -> None:
    print("Navigating to wordwall.net...")
    page.goto("https://wordwall.net/", wait_until="commit")
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


def _folder_exists(page, first_title: str, folder_name: str) -> bool:
    """Open the move dialog for the first activity to check if the folder already exists."""
    try:
        card = page.locator(f"*:has-text('{first_title}'):has(.js-item-menu)").last
        card.locator(".js-item-menu").first.click(timeout=5000)
        page.wait_for_timeout(300)
        page.locator("a.js-move-to").click(timeout=5000)
        page.wait_for_timeout(300)
        exists = page.locator(f".js-destination-folder-name:text('{folder_name}')").count() > 0
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        return exists
    except Exception as e:
        print(f"  WARNING: could not check folder existence: {e}")
        return False


def move_to_folder(page, folder_name: str, titles: list[str]) -> None:
    """Navigate to My Activity, create a folder if needed, and move the given activities into it."""
    if not folder_name or not titles:
        return

    print(f"\nNavigating to My Activity to move templates into folder '{folder_name}'...")
    page.wait_for_timeout(1500)
    try:
        page.goto("https://wordwall.net/myactivities", wait_until="commit")
        page.wait_for_load_state("networkidle")
    except Exception as e:
        print(f"  Direct navigation failed ({e}), trying homepage fallback...")
        try:
            page.wait_for_timeout(1000)
            page.goto("https://wordwall.net", wait_until="commit")
            page.wait_for_load_state("networkidle")
            page.get_by_text("My Activities").first.click(timeout=5000)
            page.wait_for_load_state("networkidle")
        except Exception as e2:
            print(f"  WARNING: Could not navigate to My Activities: {e2}")
            page.screenshot(path="debug/debug_myactivities_nav.png")
            return
    print(f"My Activities URL: {page.url}")

    if _folder_exists(page, titles[0], folder_name):
        print(f"Folder '{folder_name}' already exists, skipping creation.")
    else:
        print(f"Creating new folder '{folder_name}'...")
        try:
            page.locator("button.js-create-folder").click(timeout=5000)
            page.wait_for_timeout(500)
            page.locator(".js-modal-content input.js-input-text").fill(folder_name)
            page.get_by_role("button", name="Create").click(timeout=5000)
            page.wait_for_timeout(1000)
        except PlaywrightTimeout:
            print(f"WARNING: Could not create folder '{folder_name}' — taking screenshot.")
            page.screenshot(path="debug/debug_create_folder.png")
            return

    for title in titles:
        print(f"  Moving '{title}' into folder '{folder_name}'...")
        try:
            card = page.locator(f"*:has-text('{title}'):has(.js-item-menu)").last
            card.locator(".js-item-menu").first.click(timeout=5000)
            page.wait_for_timeout(300)

            page.locator("a.js-move-to").click(timeout=5000)
            page.wait_for_timeout(300)

            page.locator(f".js-destination-folder-name:text('{folder_name}')").click(timeout=5000)
            page.wait_for_timeout(500)
            print(f"    Moved '{title}' successfully.")
        except Exception as e:
            print(f"  WARNING: Could not move '{title}': {e}")
            page.screenshot(path=f"debug/debug_move_{title[:20].replace(' ', '_')}.png")


def main() -> None:
    env_path = "wordwall_auth.env"
    md_path = sys.argv[1] if len(sys.argv) > 1 else "wordwall_templates.md"

    env = parse_env(env_path)
    email = env.get("login", "")
    password = env.get("password", "")

    if not email or not password:
        print("ERROR: Could not read login/password from wordwall_auth.env")
        sys.exit(1)

    groups = parse_markdown(md_path)
    if not groups:
        print("ERROR: No templates found in the markdown file")
        sys.exit(1)

    total = sum(len(templates) for _, templates in groups)
    print(f"Found {len(groups)} group(s), {total} template(s) total:")
    for folder_name, templates in groups:
        label = f"'{folder_name}'" if folder_name else "(no folder)"
        print(f"  {label}:")
        for t in templates:
            print(f"    - {t['type']}: {t['title']} ({len(t['entries'])} entries)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        context = browser.new_context()
        page = context.new_page()

        login(page, email, password)

        for folder_name, templates in groups:
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
