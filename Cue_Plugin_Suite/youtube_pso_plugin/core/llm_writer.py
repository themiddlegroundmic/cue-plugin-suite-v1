"""
core/llm_writer.py
==================
Cue built-in LLM metadata writer for YouTube.

Uses Cue's own BUILT_IN_FORGE_API — no OpenAI, no Anthropic, no third-party model.
Generates replacement titles, descriptions, hooks, and chapter names
following the rules from the Master YouTube Guide.

The system prompt encodes the YouTube Guide's Three-Layer Video Test,
Title Rules, Hook Formula, Retention Structure, Chapter Rules,
and political safety doctrine.
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)

FORGE_API_URL = os.environ.get("BUILT_IN_FORGE_API_URL", "")
FORGE_API_KEY = os.environ.get("BUILT_IN_FORGE_API_KEY", "")

# ── YouTube Guide system prompt ───────────────────────────────────────────────
YOUTUBE_SYSTEM_PROMPT = """You are the Cue YouTube Metadata Writer. You generate YouTube titles,
descriptions, hooks, and chapter names for political commentary content.

TITLE RULES (Master YouTube Guide):
- Maximum 60 characters (hard limit — YouTube truncates at 60 in search)
- Lead with the topic or entity, not a vague teaser
- Use tension words: fight, exposed, blocked, failed, revealed, ignored, missed
- Never start with "Episode", "Ep.", "Interview", "Podcast", or a number
- Never use engagement bait: "You won't believe", "This will shock you"
- One clear argument per title — not two theses
- Local stakes first: name the city, county, or state before the national angle

HOOK FORMULA (first 30 seconds):
- Open with the tension or stakes — never "Welcome back" or "Today we're talking about"
- State what the viewer will understand by the end
- Name the specific entity, vote, document, or event — not vague references
- Political safety: use "alleged", "disputed", "according to [source]" for contested claims

DESCRIPTION RULES:
- First 150 characters are indexed — no boilerplate, no subscribe asks, no links
- First line must name the topic, entity, and stakes
- Include 3–5 chapters minimum using MM:SS format
- First chapter must be 00:00
- Chapter names must be specific — not "Introduction", "Main Topic", "Conclusion"
- Move all links, subscribe asks, and social handles BELOW the chapters

CHAPTER NAMING:
- Name the specific argument or revelation, not the format
- Bad: "Introduction", "Interview", "Discussion", "Conclusion"
- Good: "The Vote That Changed the Budget", "What the Records Show", "Who Actually Benefits"

POLITICAL SAFETY:
- "rigged" → "disputed" or "contested" with source
- "fraud" → "alleged fraud" with attribution
- "traitor/treason" → "accused of" with specific allegation
- "scam" → "alleged scam" or "critics call it"
- Always follow: proven fact → attributed claim → visible pattern → opinion

TAG ORDER (PSO priority):
1. DETECTED keywords (from YouTube autocomplete)
2. COMPETITOR keywords (from top-ranking video titles)
3. LOCAL keywords (geographic identifiers)
4. GUEST/ENTITY keywords (named people, organizations)
5. BRAND tag last (channel name)
Never use: video, youtube, channel, subscribe, episode, interview, podcast

OUTPUT FORMAT: Return valid JSON only. No markdown. No explanation outside the JSON."""


class YouTubeLLMWriter:
    """
    Generates YouTube metadata using Cue's built-in LLM.
    Falls back to rule-based templates if the API is unavailable.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "auto",
    ):
        self.api_url = api_url or FORGE_API_URL
        self.api_key = api_key or FORGE_API_KEY
        self.model = model

    @property
    def is_configured(self) -> bool:
        return bool(self.api_url and self.api_key)

    def generate_metadata(
        self,
        current_title: str,
        current_description: str,
        topic: str,
        detected_keywords: List[str],
        competitor_keywords: List[str],
        local_keywords: List[str],
        entity_keywords: List[str],
        channel_name: str = "The MiddleGround Mic",
        political_safety_flags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate replacement YouTube metadata for a single video.

        Returns dict with:
          - title: str
          - description: str (first 150 chars + chapters + links section)
          - hook: str (first 30 seconds script)
          - chapters: List[{"timestamp": "MM:SS", "name": str}]
          - tags: List[str] (in PSO order)
          - safety_notes: List[str]
          - pso_notes: str
        """
        if not self.is_configured:
            logger.warning("Cue LLM API not configured. Using rule-based fallback.")
            return self._rule_based_fallback(
                current_title, topic, detected_keywords,
                competitor_keywords, local_keywords, entity_keywords, channel_name
            )

        prompt = self._build_prompt(
            current_title=current_title,
            current_description=current_description,
            topic=topic,
            detected_keywords=detected_keywords,
            competitor_keywords=competitor_keywords,
            local_keywords=local_keywords,
            entity_keywords=entity_keywords,
            channel_name=channel_name,
            political_safety_flags=political_safety_flags or [],
        )

        try:
            response = requests.post(
                f"{self.api_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": YOUTUBE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.4,
                    "max_tokens": 1200,
                },
                timeout=30,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()

            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            return json.loads(content)

        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            logger.error(f"LLM API error: {e}. Using rule-based fallback.")
            return self._rule_based_fallback(
                current_title, topic, detected_keywords,
                competitor_keywords, local_keywords, entity_keywords, channel_name
            )

    def _build_prompt(
        self,
        current_title: str,
        current_description: str,
        topic: str,
        detected_keywords: List[str],
        competitor_keywords: List[str],
        local_keywords: List[str],
        entity_keywords: List[str],
        channel_name: str,
        political_safety_flags: List[str],
    ) -> str:
        kw_block = "\n".join([
            f"DETECTED (autocomplete): {', '.join(detected_keywords[:5]) or 'none'}",
            f"COMPETITOR (from top videos): {', '.join(competitor_keywords[:5]) or 'none'}",
            f"LOCAL (geographic): {', '.join(local_keywords[:3]) or 'none'}",
            f"ENTITY (named): {', '.join(entity_keywords[:3]) or 'none'}",
        ])

        safety_block = ""
        if political_safety_flags:
            safety_block = f"\nPOLITICAL SAFETY FLAGS IN CURRENT CONTENT:\n" + "\n".join(
                f"  - {flag}" for flag in political_safety_flags
            )

        desc_preview = current_description[:300] if current_description else "(no description)"

        return f"""Generate replacement YouTube metadata for this video.

CURRENT TITLE: {current_title}
CURRENT DESCRIPTION (first 300 chars): {desc_preview}
TOPIC: {topic}
CHANNEL NAME: {channel_name}

KEYWORD INTELLIGENCE:
{kw_block}
{safety_block}

Return a JSON object with exactly these fields:
{{
  "title": "replacement title (max 60 chars, leads with topic/entity, uses tension word)",
  "description": "full replacement description — first 150 chars must be keyword-rich opening, then chapters in 00:00 format, then links/social at the bottom",
  "hook": "first 30 seconds script — opens with tension/stakes, names the specific entity/vote/event, states what viewer will understand by the end",
  "chapters": [
    {{"timestamp": "00:00", "name": "specific chapter name — not Introduction"}},
    {{"timestamp": "02:30", "name": "second chapter"}},
    {{"timestamp": "05:00", "name": "third chapter"}}
  ],
  "tags": ["detected_keyword_1", "competitor_keyword_1", "local_keyword_1", "entity_keyword_1", "{channel_name.lower().replace(' ', '')}"],
  "safety_notes": ["any political safety fixes applied"],
  "pso_notes": "one sentence explaining the primary PSO improvement made"
}}"""

    def _rule_based_fallback(
        self,
        current_title: str,
        topic: str,
        detected_keywords: List[str],
        competitor_keywords: List[str],
        local_keywords: List[str],
        entity_keywords: List[str],
        channel_name: str,
    ) -> Dict[str, Any]:
        """
        Rule-based metadata generator used when the LLM API is unavailable.
        Applies YouTube Guide rules mechanically.
        """
        # Build title from best available keyword
        primary_kw = (
            detected_keywords[0] if detected_keywords
            else competitor_keywords[0] if competitor_keywords
            else topic
        )
        local = local_keywords[0].title() if local_keywords else ""
        tension_words = ["Fight", "Exposed", "Blocked", "Revealed", "Ignored", "Missed"]
        tension = tension_words[len(primary_kw) % len(tension_words)]

        if local:
            title = f"The {local} {primary_kw.title()} {tension}"[:60]
        else:
            title = f"The {primary_kw.title()} {tension} Nobody Explained"[:60]

        # Build tag set in PSO order
        tags = []
        tags.extend(detected_keywords[:3])
        tags.extend(competitor_keywords[:3])
        tags.extend(local_keywords[:2])
        tags.extend(entity_keywords[:2])
        tags.append(channel_name.lower().replace(" ", ""))
        tags = [t for t in tags if t][:15]

        # Build description opening
        desc_opening = (
            f"{primary_kw.title()} — here is what {local or 'the community'} needs to know "
            f"and why it matters now."
        )

        description = (
            f"{desc_opening}\n\n"
            f"00:00 The {primary_kw.title()} Breakdown\n"
            f"03:00 What the Records Show\n"
            f"06:00 What This Means Going Forward\n\n"
            f"---\n"
            f"Subscribe for independent political coverage.\n"
            f"Follow us on social media for daily updates."
        )

        return {
            "title": title,
            "description": description,
            "hook": (
                f"[Rule-based hook] {primary_kw.title()} — by the end of this video, "
                f"you'll understand exactly what happened and why it matters."
            ),
            "chapters": [
                {"timestamp": "00:00", "name": f"The {primary_kw.title()} Breakdown"},
                {"timestamp": "03:00", "name": "What the Records Show"},
                {"timestamp": "06:00", "name": "What This Means Going Forward"},
            ],
            "tags": tags,
            "safety_notes": [],
            "pso_notes": (
                f"Rule-based fallback applied. Primary keyword '{primary_kw}' placed in title. "
                "Connect Cue LLM API for AI-generated metadata."
            ),
        }
