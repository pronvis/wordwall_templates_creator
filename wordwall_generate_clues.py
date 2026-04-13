#!/usr/bin/env python3
"""
Generate clues for all placeholders in a wordwall markdown file:
  - '??' → text clue via Ollama (batch, single request)
  - '<image>' → image via Stable Diffusion, saved to wordwall_images/

Usage:
    python wordwall_generate_clues.py [input.md] [output.md]

Defaults:
    input  = wordwall_templates.md
    output = wordwall_templates_filled.md
"""

import re
import sys
from pathlib import Path

import ollama

OLLAMA_MODEL = "yi:6b"
# OLLAMA_MODEL = "qwen3.5:35b"

IMAGE_MODEL = "stabilityai/sdxl-turbo"
IMAGE_DIR = Path("wordwall_images")

TEXT_PLACEHOLDER = "??"
IMAGE_PLACEHOLDER = "<image>"
# Balloon pop: '<image> :: description' — generate image using the description as prompt
BALLOON_IMAGE_PATTERN = re.compile(r"^(-\s+)<image>\s*::\s*(.+)$")
# Image quiz: 'question :: <image> :: answers' — generate image using the question as prompt
IMAGE_QUIZ_PATTERN = re.compile(r"^(-\s+)(.+?)\s*::\s*<image>\s*::\s*(.+)$")


# ---------------------------------------------------------------------------
# Text clue generation
# ---------------------------------------------------------------------------

def generate_clues_batch(words: list[str]) -> dict[str, str]:
    """Send all words in one request. Returns {word: clue}."""
    word_list = "\n".join(f"{i+1}. {w}" for i, w in enumerate(words))
    prompt = (
        f"Generate a short one-sentence clue for each word below, for use in a Hangman game.\n"
        f"Do not include the word itself in the clue.\n"
        f"Reply ONLY in this exact format, one per line:\n"
        f"1. <clue for word 1>\n"
        f"2. <clue for word 2>\n"
        f"...and so on. No extra text.\n\n"
        f"Words:\n{word_list}"
    )

    print(f"Sending {len(words)} words to Ollama in one request...")
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.message.content.strip()
    print("Response received. Parsing...")

    result = {}
    for line in raw.splitlines():
        m = re.match(r"^(\d+)\.\s+(.+)$", line.strip())
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(words):
                result[words[idx]] = m.group(2).strip()

    for word in words:
        if word not in result:
            print(f"  WARNING: no clue parsed for '{word}', keeping placeholder.")
            result[word] = TEXT_PLACEHOLDER

    return result


# ---------------------------------------------------------------------------
# Image clue generation
# ---------------------------------------------------------------------------

_pipe = None


def _load_pipeline():
    global _pipe
    if _pipe is not None:
        return _pipe

    import torch
    from diffusers import AutoPipelineForText2Image

    if torch.backends.mps.is_available():
        device, dtype = "mps", torch.float16
    elif torch.cuda.is_available():
        device, dtype = "cuda", torch.float16
    else:
        device, dtype = "cpu", torch.float32

    print(f"Loading image model ({IMAGE_MODEL}) on {device}...")
    _pipe = AutoPipelineForText2Image.from_pretrained(
        IMAGE_MODEL, torch_dtype=dtype, variant="fp16"
    ).to(device)
    return _pipe


NEGATIVE_PROMPT = (
    "abstract, blurry, text, letters, words, watermark, signature, "
    "surreal, distorted, low quality, multiple objects, busy background"
)


def build_image_prompt(word: str) -> str:
    """Ask Ollama to write a descriptive Stable Diffusion prompt for the word."""
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write a Stable Diffusion prompt for a single clear image that immediately "
                    f"and unambiguously shows '{word}' to a child. "
                    f"Describe only the main object or scene — be concrete and specific, not abstract. "
                    f"Example for 'apple': 'a single red apple with a green leaf, white background, "
                    f"flat vector illustration style'. "
                    f"Reply with the prompt only, no extra text."
                ),
            }
        ],
    )
    return response.message.content.strip()


def _safe_filename(text: str) -> str:
    """Replace characters that are invalid or problematic in filenames."""
    return re.sub(r'[\\/:*?"<>|]', "_", text).replace(" ", "_")


def generate_image(word: str) -> str:
    """Generate an image for word, return path string."""
    IMAGE_DIR.mkdir(exist_ok=True)
    out_path = IMAGE_DIR / f"{_safe_filename(word)}.png"

    if out_path.exists():
        print(f"  Using cached image for '{word}': {out_path}")
        return str(out_path)

    pipe = _load_pipeline()
    prompt = build_image_prompt(word)
    print(f"  SD prompt for '{word}': {prompt}")
    image = pipe(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        num_inference_steps=4,   # SDXL-Turbo is optimized for 1-4 steps
        guidance_scale=0.0,      # SDXL-Turbo requires guidance_scale=0
    ).images[0]
    image.save(out_path)
    print(f"  Saved: {out_path}")
    return str(out_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process(input_path: str, output_path: str):
    lines = Path(input_path).read_text().splitlines()

    text_pending: dict[int, str] = {}         # line_idx -> word
    image_pending: dict[int, str] = {}        # line_idx -> word
    balloon_image_pending: dict[int, str] = {} # line_idx -> description (image prompt)
    image_quiz_pending: dict[int, tuple[str, str]] = {}  # line_idx -> (question, answers)

    for idx, line in enumerate(lines):
        # Image quiz: 'question :: <image> :: answers' — generate image from question text
        quiz_m = IMAGE_QUIZ_PATTERN.match(line)
        if quiz_m:
            question = quiz_m.group(2).strip()
            answers = quiz_m.group(3).strip()
            image_quiz_pending[idx] = (question, answers)
            continue

        # Balloon pop: '<image> :: description' — generate image from description
        balloon_m = BALLOON_IMAGE_PATTERN.match(line)
        if balloon_m:
            description = balloon_m.group(2).strip()
            balloon_image_pending[idx] = description
            continue

        m = re.match(r"^(-\s+)(.+?)\s*::\s*(.+)$", line)
        if not m:
            continue
        clue_part = m.group(3).strip()
        word = m.group(2).strip()
        if clue_part == TEXT_PLACEHOLDER:
            text_pending[idx] = word
        elif clue_part == IMAGE_PLACEHOLDER:
            image_pending[idx] = word

    # --- text clues (one batch request) ---
    text_clues: dict[str, str] = {}
    if text_pending:
        text_clues = generate_clues_batch(list(text_pending.values()))

    # --- image clues (sequential, model loaded once) ---
    image_paths: dict[int, str] = {}
    if image_pending:
        for idx, word in image_pending.items():
            image_paths[idx] = generate_image(word)

    # --- balloon pop image clues (image generated from description) ---
    balloon_image_paths: dict[int, str] = {}
    if balloon_image_pending:
        for idx, description in balloon_image_pending.items():
            balloon_image_paths[idx] = generate_image(description)

    # --- image quiz image clues (image generated from question text) ---
    image_quiz_paths: dict[int, str] = {}
    if image_quiz_pending:
        for idx, (question, _) in image_quiz_pending.items():
            image_quiz_paths[idx] = generate_image(question)

    # --- rebuild markdown ---
    result = []
    for idx, line in enumerate(lines):
        if idx in text_pending:
            word = text_pending[idx]
            clue = text_clues.get(word, TEXT_PLACEHOLDER)
            m = re.match(r"^(-\s+)", line)
            prefix = m.group(1) if m else "- "
            print(f"  '{word}' => {clue}")
            result.append(f"{prefix}{word} :: {clue}")
        elif idx in image_pending:
            word = image_pending[idx]
            path = image_paths[idx]
            m = re.match(r"^(-\s+)", line)
            prefix = m.group(1) if m else "- "
            result.append(f"{prefix}{word} :: <image:{path}>")
        elif idx in image_quiz_pending:
            question, answers = image_quiz_pending[idx]
            path = image_quiz_paths[idx]
            m = re.match(r"^(-\s+)", line)
            prefix = m.group(1) if m else "- "
            print(f"  image quiz image for '{question}' => {path}")
            result.append(f"{prefix}{question} :: <image:{path}> :: {answers}")
        elif idx in balloon_image_pending:
            description = balloon_image_pending[idx]
            path = balloon_image_paths[idx]
            m = re.match(r"^(-\s+)", line)
            prefix = m.group(1) if m else "- "
            print(f"  balloon image for '{description}' => {path}")
            result.append(f"{prefix}<image:{path}> :: {description}")
        else:
            result.append(line)

    Path(output_path).write_text("\n".join(result) + "\n")
    print(f"\nDone. Written to {output_path}")


if __name__ == "__main__":
    input_md = sys.argv[1] if len(sys.argv) > 1 else "wordwall_templates.md"
    output_md = sys.argv[2] if len(sys.argv) > 2 else "wordwall_templates_filled.md"
    process(input_md, output_md)
