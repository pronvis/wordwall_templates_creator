## Wordwall Bot

Automates creating templates on [wordwall.net](https://wordwall.net) from a markdown file, with optional AI-generated clues (text via Ollama, images via Stable Diffusion).

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) running locally with your model pulled, e.g. `ollama pull qwen3.5:35b`

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install playwright ollama diffusers transformers accelerate torch
playwright install chromium
```

### Auth

Create `wordwall_auth.env`:
```
login: your@email.com
password: yourpassword
```

### Supported template types

| `##` heading | Description | Entry format |
|---|---|---|
| `Hangman` | Classic hangman with text or image clues | `word :: clue` or `word :: <image>` |
| `Match up` | Match word to image (min 3 items) | `word :: <image:path>` |
| `Anagram` | Unscramble words, with or without clues | `word :: clue` (with clues) or `word` (without) |
| `Crossword` | Crossword with text clues | `word :: clue` |
| `Wordsearch` | Word search, with or without clues | `word :: clue` (with clues) or `word` (without) |
| `Image quiz` | Question with image + multiple choice answers | `question :: <image:path> :: ans1 : +ans2 : ans3` |
| `Gameshow quiz` | Multiple choice quiz (min 5 questions recommended) | `question :: ans1 : +ans2 : ans3 : +ans4` |
| `Balloon pop` | Match keyword to definition (min 5 items) | `keyword :: definition` or `<image:path> :: definition` |
| `Matching pairs` | Match identical items or definition–image pairs | `word` (identical) or `definition :: <image:path>` (pairs) |

Answer format for quiz templates: prefix the correct answer(s) with `+`. The "Add more answers" button adds 2 fields at a time; put answers in visual order (1, 2, 3, 4, …).

### Markdown format

Create `wordwall_templates.md`:
```markdown
# Folder name

## Hangman

### Activity title

- word1 :: manually written clue
- word2 :: ??          # generate text clue via Ollama
- word3 :: <image>     # generate image clue via Stable Diffusion

## Gameshow quiz

### Quiz title

- What is the capital of France? :: London : +Paris : Berlin : Madrid

## Image quiz

### Image quiz title

- What animal is this? :: <image> :: Cat : +Dog : Bird

# Another folder

## Wordsearch

### Without clues

- apple
- banana
- cherry
```

- `#` — folder name on the "My Activities" page (optional; omit to skip folder grouping)
- `##` — template type (see table above)
- `###` — activity title
- Multiple `#` sections create separate folders; all activities under each `#` are moved into that folder after creation
- Multiple `###` sections under one `##` create multiple activities
- `??` in clue field → text clue generated via Ollama
- `<image>` in clue field → image generated via Stable Diffusion
- `<image> :: description` (Balloon pop) → image generated from the description text

### Usage

**Step 1 — generate clues** (for `??` and `<image>` placeholders):
```bash
python wordwall_generate_clues.py
# reads wordwall_templates.md
# writes wordwall_templates_filled.md
# saves images to wordwall_images/
```

Review `wordwall_templates_filled.md` before proceeding.

**Step 2 — create templates on wordwall.net:**
```bash
python wordwall_bot.py wordwall_templates_filled.md
```

A browser window will open so you can watch the automation. Press Enter in the terminal to close it when done.
