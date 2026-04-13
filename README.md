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

### Markdown format

Create `wordwall_templates.md`:
```markdown
# Folder name

## HangMan

### Activity title

- word1 :: manually written clue
- word2 :: ??          # generate text clue via Ollama
- word3 :: <image>     # generate image clue via Stable Diffusion

# Another folder

## HangMan

### Another activity

- word4 :: clue
```

- `#` — folder name on the "My Activities" page (optional; omit to skip folder grouping)
- `##` — template type (e.g. `HangMan`)
- `###` — activity title (maps to "Activity Title" on wordwall)
- Multiple `#` sections create separate folders; all activities under each `#` are moved into that folder after creation
- Multiple `###` sections under one `##` create multiple activities

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
