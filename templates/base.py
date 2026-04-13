"""Shared helpers used by all template handlers."""

import re
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout


def fill_contenteditable(page: Page, locator, text: str) -> None:
    locator.click()
    page.keyboard.press("Control+a")
    page.keyboard.type(text)


def goto_create(page: Page, template_name: str) -> None:
    # Wait for any in-progress navigation (e.g. post-save redirect) to settle
    page.wait_for_timeout(1000)
    for attempt in range(3):
        try:
            page.goto("https://wordwall.net/create", wait_until="commit")
            break
        except Exception:
            if attempt == 2:
                raise
            page.wait_for_timeout(1000)
    page.wait_for_load_state("networkidle")
    try:
        page.click(f"text={template_name}", timeout=5000)
    except PlaywrightTimeout:
        # Fall back to matching the template preview image by src keyword
        keyword = template_name.lower().replace(" ", "")
        page.locator(f'img.preview[src*="{keyword}"]').click(timeout=5000)
    page.wait_for_load_state("networkidle")


def set_title(page: Page, title: str) -> None:
    if not title:
        return
    try:
        title_input = page.locator("input[type='text']").first
        title_input.click(timeout=3000)
        title_input.fill(title)
    except PlaywrightTimeout:
        print("WARNING: could not set title — taking screenshot.")
        page.screenshot(path="debug/debug_title.png")


def save_activity(page: Page) -> None:
    try:
        page.click("text=Done", timeout=5000)
    except PlaywrightTimeout:
        try:
            page.click("text=Save", timeout=5000)
        except PlaywrightTimeout:
            print("Could not find Save/Done button — taking screenshot.")
            page.screenshot(path="debug/debug_save.png")
            return
    page.wait_for_load_state("networkidle")
    print(f"Activity saved. URL: {page.url}")


def add_item(page: Page) -> None:
    """Click the '+ Add item' button and wait for a new row to appear."""
    add_btn = page.locator(".js-add-item, [class*='add-item'], [class*='add-word']").first
    try:
        add_btn.click(timeout=3000)
    except PlaywrightTimeout:
        page.locator("//*[contains(text(),'Add')]").first.click(timeout=3000)
    page.wait_for_timeout(400)


def upload_image(page: Page, image_path: str) -> None:
    """Open the image modal and upload a file."""
    with page.expect_file_chooser() as fc:
        page.locator("a#upload_image_button").click(timeout=5000)
    fc.value.set_files(image_path)
    page.wait_for_timeout(500)


def parse_answers(answers_str: str) -> list[tuple[str, bool]]:
    """Parse 'ans1 : +ans2 : ans3' → [(text, is_correct), ...].

    A leading '+' marks the answer as correct.
    """
    parts = [p.strip() for p in answers_str.split(":")]
    result = []
    for p in parts:
        if p.startswith("+"):
            result.append((p[1:].strip(), True))
        else:
            result.append((p, False))
    return result
