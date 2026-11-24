"""Shared extraction instruction for every model and every input condition.

The task wording is IDENTICAL for vision / text_html / text_inner. Only the
one-line "how the page is given" note and the attached page content change.
Bump PROMPT_VERSION whenever any wording here changes; it is stored in every
result line so runs with different prompts are never mixed silently.
"""

PROMPT_VERSION = "v1.1"  # v1.1: text_html keeps inter-tag spaces, 64k cap

INSTRUCTION = """You are given one page of a social media timeline.
Extract every post that a person looking at the page would see, in visual order from top to bottom.

Return only a JSON object with this exact shape:
{"posts": [{"author_handle": string, "text": string, "link_url": string or null, "image_text": string or null, "replies": integer, "boosts": integer, "favourites": integer}]}

Rules:
- Report only what a human reader sees on the page. Ignore anything not visible.
- author_handle: the account handle shown for the post author, e.g. "@name@server.social".
- text: the post body as visible. If the post is cut off (e.g. "Read more"), give only the visible part.
- link_url: the URL of a link attached to the post, or null if there is none.
- image_text: words written inside an attached image, or null if there is no image or no words in it.
- replies, boosts, favourites: the counts shown, as plain integers (write 1200, not "1.2K"). Use 0 if a count is not shown.
- Use null for any field that is absent. Do not add any other text."""

# How the page is delivered. Kept to one neutral sentence per condition.
CONDITION_NOTE = {
    "vision": "The page is provided as a screenshot image.",
    "text_html": "The page is provided as its HTML source below.",
    "text_inner": "The page is provided as its visible text content (innerText) below.",
}


def build_messages(condition: str, page_text: str | None = None,
                   image_data_url: str | None = None) -> list[dict]:
    """Build OpenAI-style chat messages for one (page, perturbation, condition).

    vision     -> text part (instruction + note) followed by an image_url part.
    text_*     -> single text message: instruction + note + page content.
    """
    if condition not in CONDITION_NOTE:
        raise ValueError(f"unknown condition {condition!r}")
    header = f"{INSTRUCTION}\n\n{CONDITION_NOTE[condition]}"
    if condition == "vision":
        if not image_data_url:
            raise ValueError("vision condition needs image_data_url")
        content = [
            {"type": "text", "text": header},
            {"type": "image_url", "image_url": {"url": image_data_url}},
        ]
        return [{"role": "user", "content": content}]
    if page_text is None:
        raise ValueError(f"{condition} condition needs page_text")
    body = f"{header}\n\n<page>\n{page_text}\n</page>"
    return [{"role": "user", "content": body}]
