"""One-off: generate README hero assets via DashScope qwen-image-2.0."""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import dashscope
from dashscope import MultiModalConversation
from dotenv import load_dotenv

load_dotenv()

API_KEY = (os.getenv("QWEN_API_KEY") or "").strip()
if not API_KEY:
    raise SystemExit("QWEN_API_KEY missing")

# Classic Beijing DashScope host (matches project Qwen defaults)
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"
dashscope.api_key = API_KEY

OUT_DIR = Path("docs/assets")
OUT_DIR.mkdir(parents=True, exist_ok=True)

JOBS = [
    {
        "name": "readme-hero",
        "size": "2688*1536",
        "prompt_extend": True,
        "prompt": (
            "Wide cute animated hero banner introducing MindGraph to cat lovers. Style: "
            "charming 2D/3D hybrid animation like a modern kids education app — soft clay "
            "and cel-shaded look, warm classroom lighting. A fluffy black cat mascot with "
            "big sparkling eyes and a tiny scarf sits on a wooden school desk, paw touching "
            "a glowing floating mind-map made of soft pastel bubbles and yarn-like connectors. "
            "Clear title text MindGraph in friendly bold rounded letters. Background: cozy "
            "classroom with chalkboard, books, crayons, and sunlight. Warm cream, peach, and "
            "soft teal accents. Inviting, wholesome, educational, no scary vibe, no watermark."
        ),
        "negative": (
            "scary cat, horror, realistic photo, gore, messy text, warped letters, purple neon, "
            "cyberpunk, adult content, watermark, cluttered UI, dark gloomy mood"
        ),
    },
    {
        "name": "readme-diagrams",
        "size": "2048*2048",
        "prompt_extend": True,
        "prompt": (
            "Cute 2x2 educational poster for cat lovers introducing MindGraph diagram types. "
            "Soft 2D/3D animation style, pastel classroom aesthetic. Each panel has a tiny "
            "black cat helper. Top-left Circle Map: black cat in the center circle with "
            "context bubbles around. Top-right Bubble Map: black cat describing attributes "
            "with bubbly nodes. Bottom-left Tree Map: black cat climbing a friendly hierarchy "
            "tree of topic cards. Bottom-right Concept Map: two black cats connected by "
            "labeled yarn arrows. Clear English panel captions: Circle Map, Bubble Map, "
            "Tree Map, Concept Map. Warm, playful, readable, README-friendly, no watermark."
        ),
        "negative": (
            "scary, horror, photoreal, illegible text, overlapping panels, neon glow, "
            "watermark, dark mood, messy composition"
        ),
    },
    {
        "name": "readme-canvas",
        "size": "2688*1536",
        "prompt_extend": True,
        "prompt": (
            "Cute animated story scene introducing MindGraph canvas to cat-loving students "
            "and teachers. 2D/3D hybrid animation style. In a bright classroom, a fluffy "
            "black cat teacher stands on a stool pointing at a large interactive whiteboard "
            "showing a colorful mind map titled Ideas. Soft pastel nodes and curved "
            "connectors. A few small student cats watch happily with notebooks. Side props: "
            "backpacks, plants, alphabet cards. Friendly title ribbon saying Learn with "
            "MindGraph. Warm sunlight, wholesome education vibes, sharp readable key words "
            "only, no gibberish, no watermark."
        ),
        "negative": (
            "gibberish text, scary cats, horror, photoreal humans, purple neon, watermark, "
            "blurry, dark classroom, cluttered unreadable UI"
        ),
    },
]


def _extract_image_url(content: object) -> str | None:
    if not isinstance(content, list):
        return None
    for item in content:
        if isinstance(item, dict) and item.get("image"):
            return str(item["image"])
    return None


def _response_image_url(resp: object) -> str | None:
    """Pull the first image URL from a DashScope multimodal response."""
    status = getattr(resp, "status_code", None)
    print(f"  status={status}")
    if status != 200:
        print("  error:", getattr(resp, "code", None), getattr(resp, "message", None))
        return None
    output = getattr(resp, "output", None)
    choices = getattr(output, "choices", None) if output is not None else None
    if not choices:
        print("  no choices in response")
        return None
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None) if message is not None else None
    image_url = _extract_image_url(content)
    if not image_url:
        print("  no image in response:", content)
    return image_url


def main() -> None:
    """Call DashScope and download README image assets."""
    for job in JOBS:
        print(f"Generating {job['name']}...")
        messages = [{"role": "user", "content": [{"text": job["prompt"]}]}]
        resp = MultiModalConversation.call(
            api_key=API_KEY,
            model="qwen-image-2.0",
            messages=messages,
            result_format="message",
            stream=False,
            watermark=False,
            prompt_extend=bool(job.get("prompt_extend", True)),
            negative_prompt=job["negative"],
            size=job["size"],
            n=1,
        )
        image_url = _response_image_url(resp)
        if not image_url:
            continue
        dest = OUT_DIR / f"{job['name']}.png"
        urllib.request.urlretrieve(image_url, dest)
        print(f"  saved {dest} ({dest.stat().st_size} bytes)")
    print("done")


if __name__ == "__main__":
    main()
