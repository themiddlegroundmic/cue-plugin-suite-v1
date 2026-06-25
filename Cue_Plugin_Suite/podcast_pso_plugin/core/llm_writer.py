"""
llm_writer.py
=============
Uses Cue's own built-in LLM (BUILT_IN_FORGE_API) to generate replacement
podcast metadata: title, first-150-words description, PSO-ordered tags,
chapter names, and political safety rewrites.

NO THIRD-PARTY MODEL — this uses only the Cue platform's internal LLM,
which is already wired into the project via BUILT_IN_FORGE_API_URL and
BUILT_IN_FORGE_API_KEY environment variables.

This is the feature Ausha cannot offer at any price point.
Ausha shows you what to fix. Cue writes the fix for you.

API contract follows the Cue LLM integration spec in references/llm-integration.md:
  POST {BUILT_IN_FORGE_API_URL}/v1/chat/completions
  Authorization: Bearer {BUILT_IN_FORGE_API_KEY}
  Body: OpenAI-compatible chat completions format
"""

import json
import os
import requests
from typing import Dict, List, Optional

from .feed_parser import Episode


# ── System prompt for the PSO metadata writer ───────────────────────────────

PSO_SYSTEM_PROMPT = """You are the Cue PSO Metadata Writer — a specialist in Podcast Search Optimization (PSO) for political commentary and news podcasts.

Your job is to rewrite podcast episode metadata so it ranks higher on Apple Podcasts and Spotify. You follow these rules without exception:

TITLE RULES:
- Maximum 80 characters
- Lead with the most searchable entity or event (person, legislation, country, event)
- No vague openers like "Episode", "Ep", "Part", "Special", "Update"
- No clickbait or exaggeration
- Must be factually accurate to the episode content

DESCRIPTION RULES (first 150 words):
- Open with the primary keyword naturally in the first sentence
- Name the guest (if any) in the first sentence
- State the stakes or why this matters in the second sentence
- Use 2–3 of the provided detected/factual keywords naturally in the first 150 words
- No boilerplate (no fan mail links, no BuyMeACoffee, no sponsor copy) in the first 150 words
- Write in a conversational, direct tone — not corporate or generic

TAG RULES:
- Return exactly 8–12 tags
- Order: Detected keywords first → Factual entities → Local/geographic → Guest name → Show brand last
- No dead tags: podcast, episode, show, host, guest, interview, audio, listen, subscribe, follow
- All tags lowercase, no hashtags

CHAPTER RULES:
- Return 3–5 chapter names with realistic timestamps
- First chapter must be (00:00)
- Chapter names should be specific, not generic ("Iran Nuclear Talks" not "Main Topic")

POLITICAL SAFETY RULES:
- If the original title or description contains: rigged, fraud, traitor, treason, scam, stolen, fake, hoax, powder keg, criminal, corrupt — rewrite to use qualified language
- Example: "rigged election" → "disputed election results" or "election integrity concerns"
- Never remove the substance, only soften the framing to avoid platform suppression

Return your response as valid JSON only — no markdown, no explanation outside the JSON."""


# ── User prompt template ─────────────────────────────────────────────────────

def build_user_prompt(
    episode: Episode,
    detected_keywords: List[str],
    factual_keywords: List[str],
    local_keywords: List[str],
    guest_names: List[str],
    show_brand: str,
    competitor_terms: List[str],
) -> str:
    return f"""Rewrite the metadata for this podcast episode.

SHOW: {show_brand}
CURRENT TITLE: {episode.title}
CURRENT DESCRIPTION (first 300 chars): {(episode.description or '')[:300]}
CURRENT TAGS: {', '.join(episode.tags or [])}

DETECTED KEYWORDS (from Apple Podcasts search — use these):
{', '.join(detected_keywords[:5]) if detected_keywords else 'none detected'}

FACTUAL ENTITIES (from episode content):
{', '.join(factual_keywords[:5]) if factual_keywords else 'none'}

LOCAL KEYWORDS:
{', '.join(local_keywords[:3]) if local_keywords else 'none'}

GUEST NAMES:
{', '.join(guest_names) if guest_names else 'none mentioned'}

COMPETITOR TERMS (used by top-ranking shows):
{', '.join(competitor_terms[:8]) if competitor_terms else 'none'}

SAFETY FLAGS DETECTED: {', '.join(episode.safety_flags) if episode.safety_flags else 'none'}

Return this exact JSON structure:
{{
  "title": "new title here (max 80 chars)",
  "description_opening": "First 150 words of new description here. Must open with primary keyword naturally.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "chapters": [
    {{"time": "00:00", "name": "Chapter name"}},
    {{"time": "05:30", "name": "Chapter name"}},
    {{"time": "18:00", "name": "Chapter name"}}
  ],
  "safety_rewrites": {{
    "original_flag": "rewritten safe version"
  }},
  "reasoning": "One sentence explaining the primary keyword choice."
}}"""


# ── LLM Writer class ─────────────────────────────────────────────────────────

class LLMWriter:
    """
    Generates replacement metadata for podcast episodes using Cue's built-in LLM.

    Usage:
        writer = LLMWriter(
            api_url=os.environ["BUILT_IN_FORGE_API_URL"],
            api_key=os.environ["BUILT_IN_FORGE_API_KEY"],
        )
        result = writer.write_metadata(episode, keyword_data)
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str = "auto",
        max_tokens: int = 1200,
        temperature: float = 0.4,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._session = requests.Session()

    def write_metadata(
        self,
        episode: Episode,
        detected_keywords: List[str],
        factual_keywords: List[str],
        local_keywords: List[str],
        guest_names: List[str],
        show_brand: str,
        competitor_terms: List[str],
    ) -> Optional[Dict]:
        """
        Call Cue's built-in LLM to generate replacement metadata.
        Returns parsed JSON dict or None on failure.
        """
        user_prompt = build_user_prompt(
            episode=episode,
            detected_keywords=detected_keywords,
            factual_keywords=factual_keywords,
            local_keywords=local_keywords,
            guest_names=guest_names,
            show_brand=show_brand,
            competitor_terms=competitor_terms,
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": PSO_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }

        try:
            resp = self._session.post(
                f"{self.api_url}/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"[LLMWriter] JSON parse error for '{episode.title}': {e}")
            return None
        except Exception as e:
            print(f"[LLMWriter] API error for '{episode.title}': {e}")
            return None

    def write_batch(
        self,
        episodes: List[Episode],
        keyword_data: Dict,
        show_brand: str,
        max_episodes: int = 20,
    ) -> Dict[str, Optional[Dict]]:
        """
        Generate metadata for a batch of episodes (P1 priority by default).
        Returns dict: {episode_guid: llm_output_or_None}
        """
        results = {}
        for ep in episodes[:max_episodes]:
            kd = keyword_data.get(ep.guid, {})
            result = self.write_metadata(
                episode=ep,
                detected_keywords=kd.get("detected", []),
                factual_keywords=kd.get("factual", []),
                local_keywords=kd.get("local", []),
                guest_names=kd.get("guest", []),
                show_brand=show_brand,
                competitor_terms=kd.get("competitor_terms", []),
            )
            results[ep.guid] = result
            status = "✓" if result else "✗"
            print(f"[LLMWriter] {status} {ep.title[:50]}")
        return results

    @staticmethod
    def from_env() -> "LLMWriter":
        """Construct LLMWriter from Cue environment variables."""
        api_url = os.environ.get("BUILT_IN_FORGE_API_URL", "")
        api_key = os.environ.get("BUILT_IN_FORGE_API_KEY", "")
        if not api_url or not api_key:
            raise EnvironmentError(
                "BUILT_IN_FORGE_API_URL and BUILT_IN_FORGE_API_KEY must be set. "
                "These are automatically available in the Cue platform environment."
            )
        return LLMWriter(api_url=api_url, api_key=api_key)
