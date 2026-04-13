"""Gameshow Quiz template handler.

Markdown entry format:
    - question_text :: answer1 : +answer2 : answer3 : +answer4

Answers prefixed with '+' are marked as correct.
The "Add more answers" button adds 2 answer fields at a time.
"""

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from .base import fill_contenteditable, goto_create, set_title, save_activity, parse_answers


def create(page: Page, entries: list[dict], title: str = "") -> None:
    print("Looking for Gameshow Quiz template...")
    goto_create(page, "Gameshow quiz")
    print(f"URL after selecting Gameshow Quiz: {page.url}")

    set_title(page, title)
    page.wait_for_load_state("networkidle")

    initial_count = page.locator("div.quiz-item").count()
    print(f"  Template started with {initial_count} pre-existing question slot(s)")

    for q_idx, entry in enumerate(entries):
        print(f"  Adding question {q_idx+1}: {entry['word']}")

        if q_idx >= initial_count:
            try:
                page.locator(".js-editor-add-item").click(timeout=3000)
                page.wait_for_timeout(400)
            except PlaywrightTimeout:
                print(f"  WARNING: could not add question {q_idx+1}")
                page.screenshot(path=f"debug/debug_gsquiz_add_q_{q_idx+1}.png")
                continue

        try:
            question_item = page.locator("div.quiz-item").nth(q_idx)

            fill_contenteditable(page, question_item.locator(".js-question-box div.js-item-input"), entry["word"])

            if not entry["clue"]:
                print(f"  WARNING: no answers provided for question '{entry['word']}'")
                continue

            answers = parse_answers(entry["clue"])
            _fill_answers(page, question_item, answers)

        except Exception as e:
            print(f"  Warning: could not fill question {q_idx+1}: {e}")
            page.screenshot(path=f"debug/debug_gsquiz_q_{q_idx+1}.png")

    _save_activity(page)


def _save_activity(page: Page) -> None:
    """Save activity, confirming the 'less than 5 questions' popup if it appears."""
    from .base import save_activity
    save_activity(page)
    try:
        page.locator("button.js-yes-button").click(timeout=3000)
        page.wait_for_load_state("networkidle")
        print(f"Confirmed low-question popup. URL: {page.url}")
    except PlaywrightTimeout:
        pass  # popup did not appear


def _fill_answers(page: Page, question_item, answers: list[tuple[str, bool]]) -> None:
    """Ensure enough answer fields exist, fill them, and mark correct ones.

    Answers use an alternating two-column layout:
      column1: visual positions 0, 2, 4, … (even indices)
      column2: visual positions 1, 3, 5, … (odd indices)
    """
    answer_boxes = question_item.locator("div.answer-box")
    current_count = answer_boxes.count()

    while current_count < len(answers):
        try:
            question_item.locator(".js-editor-add-answer").click(timeout=3000)
            page.wait_for_timeout(300)
            current_count = answer_boxes.count()
        except PlaywrightTimeout:
            print(f"  WARNING: could not add more answer fields (have {current_count}, need {len(answers)})")
            page.screenshot(path="debug/debug_gsquiz_add_answers.png")
            break

    col1 = question_item.locator(".item-column.column1 div.answer-box")
    col2 = question_item.locator(".item-column.column2 div.answer-box")

    for a_idx, (text, is_correct) in enumerate(answers):
        if a_idx >= current_count:
            break
        try:
            # Even indices → column1, odd → column2
            col_idx = a_idx // 2
            answer_box = col1.nth(col_idx) if a_idx % 2 == 0 else col2.nth(col_idx)
            fill_contenteditable(page, answer_box.locator("div.js-item-input"), text)

            if is_correct:
                answer_box.locator(".question-check-back").click(timeout=3000)
                print(f"    Answer '{text}' marked as correct")
        except Exception as e:
            print(f"  Warning: could not fill answer {a_idx+1}: {e}")
            page.screenshot(path=f"debug/debug_gsquiz_answer_{a_idx+1}.png")
