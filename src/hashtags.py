"""Shared hashtag utilities for content and competitor analysis.

Pages in this space (Yemeni jewellery retail) overuse phone-number hashtags
(#+967777000, #0777000000). They are contact info, not marketing signals, so
every analysis tool filters them through ``marketing_hashtags`` — otherwise
the "top hashtags" of any page is dominated by its phone number instead of
the tags that actually sell.
"""

import re

_TAG_RE = re.compile(r"#[^\s#.,!?؛،؟]+")


def all_hashtags(text: str) -> list[str]:
    """Every hashtag in a message, lowercased — no filtering."""
    return [h.lower() for h in _TAG_RE.findall(text or "")]


def is_contact_hashtag(tag: str) -> bool:
    """True for hashtags that carry contact info rather than marketing intent.

    Heuristic: at least 5 digits (phone numbers, long IDs), or more digits
    than letters — so a tag with a year (#Dior2026) survives while #777000
    and #+967777000 do not.
    """
    body = tag.lstrip("#")
    digits = sum(c.isdigit() for c in body)
    letters = sum(c.isalpha() for c in body)
    return digits >= 5 or (digits > 0 and digits > letters)


def marketing_hashtags(text: str) -> list[str]:
    """Hashtags with contact-info tags (phone numbers) removed."""
    return [t for t in all_hashtags(text) if not is_contact_hashtag(t)]
