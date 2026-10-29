"""LLM helper — Phase 7 AI Intelligence.

Tries OpenAI → Anthropic → fallback template. No hard dependency;
if libs not installed or keys missing, falls back to deterministic template.

Env:
- OPENAI_API_KEY / LLM_API_KEY
- ANTHROPIC_API_KEY
- LLM_MODEL (default gpt-4o-mini for OpenAI, claude-3-5-sonnet for Anthropic)
"""

import os


def _get_key() -> tuple[str | None, str]:
    """Return (key, provider) where provider is openai|anthropic|none."""
    if os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"):
        return os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"), "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return os.getenv("ANTHROPIC_API_KEY"), "anthropic"
    return None, "none"


def call_llm(
    prompt: str,
    system: str = "You are a helpful marketing assistant. Respond in the requested language.",
    model: str | None = None,
    max_tokens: int = 800,
) -> str | None:
    """Call LLM if configured, else return None (caller should fallback)."""
    key, provider = _get_key()
    if not key:
        return None

    # Try OpenAI
    if provider == "openai":
        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=key)
            mdl = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
            resp = client.chat.completions.create(
                model=mdl,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip() if resp.choices else None  # type: ignore[attr-defined,union-attr]
        except Exception:
            return None

    # Try Anthropic
    if provider == "anthropic":
        try:
            import anthropic  # type: ignore

            client = anthropic.Anthropic(api_key=key)  # type: ignore[assignment]
            mdl = model or os.getenv("LLM_MODEL") or "claude-3-5-sonnet-20240620"
            resp = client.messages.create(  # type: ignore[attr-defined]
                model=mdl,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            # anthropic returns list of content blocks
            if resp.content and len(resp.content) > 0:  # type: ignore[attr-defined]
                block = resp.content[0]  # type: ignore[attr-defined]
                text = getattr(block, "text", None) or getattr(block, "content", None) or str(block)
                return text.strip() if text else None
            return None
        except Exception:
            return None

    return None


def call_vision(
    image_url: str,
    prompt: str = "Describe this image for an Instagram caption. Be engaging.",
    model: str | None = None,
) -> str | None:
    """Vision LLM (gpt-4o) for image captioning. Falls back to None."""
    key, provider = _get_key()
    if not key or provider != "openai":
        # Only OpenAI vision is widely available; Anthropic vision requires different handling
        return None
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=key)
        mdl = model or os.getenv("LLM_VISION_MODEL") or "gpt-4o"
        resp = client.chat.completions.create(
            model=mdl,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            max_tokens=400,
        )
        return resp.choices[0].message.content.strip() if resp.choices else None  # type: ignore[attr-defined,union-attr]
    except Exception:
        return None
