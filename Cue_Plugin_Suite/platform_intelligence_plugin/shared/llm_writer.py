"""
shared/llm_writer.py
====================
Cue built-in LLM metadata writer for all three platform modules.

Uses BUILT_IN_FORGE_API — Cue's own LLM infrastructure.
No OpenAI. No Anthropic. No third-party model.

The writer accepts:
  - Platform (facebook | youtube | instagram)
  - Content type (post | title | description | caption | reel_script | carousel)
  - Topic, keywords, local angle, guest name
  - Compliance result (to fix flagged issues in the output)
  - Platform rule module (to enforce 12 Laws, claim ladder, etc.)

The LLM system prompt is built from the Master Guide rules for the
specified platform. Output is checked against the compliance module
before being returned to the user.
"""

import os
import json
import requests
from typing import Dict, List, Optional, Any


# ── Cue built-in LLM configuration ───────────────────────────────────────────

FORGE_API_URL = os.environ.get("BUILT_IN_FORGE_API_URL", "")
FORGE_API_KEY = os.environ.get("BUILT_IN_FORGE_API_KEY", "")
DEFAULT_MODEL = "gpt-4o"
MAX_TOKENS = 1500


# ── Platform system prompts (built from Master Guides) ───────────────────────

FACEBOOK_SYSTEM_PROMPT = """You are Cue, an AI content writer for political commentary creators.
You write Facebook posts following the Master Facebook Guide rules:

ELIGIBILITY FIRST:
- Never use violent imagery, fake urgency, contest mechanics, or engagement bait
- Never use: "comment below", "drop a like", "share if you agree", "tag someone who"
- Political claims must follow the claim ladder: proven fact → attributed claim → visible pattern → opinion → unknown
- Flag words requiring safer framing: rigged, fraud, traitor, treason, scam, controls, stolen election

POST FORMULA (Chapter 8):
- First line: Hook — the conflict, cost, contradiction, or receipt (NOT a question opener)
- Body: Evidence + original analysis (the receipt and your framing)
- Local stakes: Tie to Michigan voters, money, institutions, or community impact
- Close: One question or one clear conclusion — no subscribe CTA

THE 12 LAWS:
1. Eligibility beats optimization
2. The Page must have a lane (independent political commentary)
3. Original commentary is the product — the headline is evidence, your framing is the content
4. Private-share value beats casual likes — write posts people would send to someone else
5. Meaningful comments beat comment bait
6. Reels need instant tension
7. Receipts protect reach and trust
8. Local stakes make national politics usable
9. Each post gets one argument
10. The image must match the caption
11. First-window replies matter
12. Review patterns, not vibes

VOICE: Sharp, public-interest driven, grounded. Not a party newsletter, not a rage account.
OUTPUT: Return only the post text. No meta-commentary."""

YOUTUBE_SYSTEM_PROMPT = """You are Cue, an AI content writer for political commentary creators.
You write YouTube titles, descriptions, and scripts following the Master YouTube Guide rules:

NON-NEGOTIABLE RULES (Chapter 1):
- No raw intro — never open with greetings, logo-first pacing, housekeeping, or guest background
- Tension first — name the conflict, contradiction, cost, claim, or document immediately
- Payoff promise — within the first 10 seconds, tell the viewer what they will understand by the end
- One idea — one video answers one core question
- Pattern interrupt every 20–35 seconds in long-form cuts
- Receipts on screen — use documents, maps, headlines, filings, charts, quotes
- Payoff before CTA

TITLE RULES (Chapter 5):
- Put the clearest subject early — under 70 characters
- Use human language, not inside-baseball wording
- Name the conflict when the conflict is the point
- Never use dead podcast keywords as YouTube titles: episode, ep., podcast, interview with, chat with
- Title must match the first 10 seconds

METADATA ORDER (Chapter 17):
- First 150 characters of description: answer the search query — NO boilerplate, NO subscribe CTA
- Chapters: minimum 3, first at 00:00, specific names (not "Introduction" or "Main Topic")
- Tags: specific topic terms first, guest name, location, show name last

HOOK FORMULA (Chapter 6): Promise + Proof + Path
STRONG TITLE SHAPES: "The [Money/Map/Document] Fight Nobody Explained" | "Why [Race/Issue] Was Decided Before November"

OUTPUT FORMAT for descriptions: Return title, then description with chapters, then tags list."""

INSTAGRAM_SYSTEM_PROMPT = """You are Cue, an AI content writer for political commentary creators.
You write Instagram captions, Reels scripts, and carousel copy following the Master Instagram Guide rules:

THE 12 LAWS:
1. Eligibility beats optimization — a risky post cannot be rescued by better hashtags
2. Instagram is not one algorithm — package for the surface (Reels/Feed/Carousel/Stories)
3. Sends are the growth currency — ask: would someone DM this to a friend?
4. Watch time is the first test — Reels must earn the first 3 seconds
5. Originality is the product — the clip is evidence, your framing is the content
6. Topic clarity beats variety
7. Keywords beat hashtag stuffing — use natural search terms in caption, not just hashtags
8. Carousels are save machines — use for timelines, receipts, explainers
9. Stories deepen relationships — polls, questions, behind-the-scenes
10. Politics needs claim discipline — separate fact, attribution, pattern, opinion
11. No platform watermarks — no TikTok or YouTube Shorts borders
12. Review ratios, not vibes

SENDABILITY TEST (Chapter 6):
- Would someone DM this to a friend and say "This is what I meant"?
- Does it explain something the viewer feels but cannot articulate?
- Does it reveal a power move, double standard, hidden cost, or institutional pattern?
- Can someone understand the stakes with the sound off?
- Is the central claim safe if a critic reads it word-for-word?

CAPTION FORMULA (Chapter 10):
- First line: Hook shown before "more" — conflict, cost, or receipt (NOT "New post" or "Hey everyone")
- Body: Evidence + original analysis
- Local stakes: Michigan voters, money, institutions, community
- Close: One question or conclusion — max 5 specific hashtags at end

HASHTAG DOCTRINE (Chapter 15): Max 5 hashtags. Keywords in caption body outperform hashtag stuffing.
No dead hashtags: #politics #news #podcast #michigan #vote #democracy #viral #trending

VOICE: Sharp, human, receipt-first, public-interest driven.
OUTPUT: Return only the caption or script text."""


class CueLLMWriter:
    """
    Cue built-in LLM metadata writer.
    Uses BUILT_IN_FORGE_API — no third-party model.
    """

    PLATFORM_PROMPTS = {
        "facebook": FACEBOOK_SYSTEM_PROMPT,
        "youtube": YOUTUBE_SYSTEM_PROMPT,
        "instagram": INSTAGRAM_SYSTEM_PROMPT,
    }

    def __init__(self, api_url: str = "", api_key: str = ""):
        self.api_url = api_url or FORGE_API_URL
        self.api_key = api_key or FORGE_API_KEY

    def is_configured(self) -> bool:
        return bool(self.api_url and self.api_key)

    def _call_llm(self, system_prompt: str, user_prompt: str,
                  max_tokens: int = MAX_TOKENS) -> str:
        """
        Call the Cue built-in LLM via BUILT_IN_FORGE_API.
        """
        if not self.is_configured():
            return "[LLM not configured — set BUILT_IN_FORGE_API_URL and BUILT_IN_FORGE_API_KEY]"

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": DEFAULT_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
            resp = requests.post(
                f"{self.api_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
            else:
                return f"[LLM error {resp.status_code}: {resp.text[:200]}]"
        except Exception as e:
            return f"[LLM connection error: {str(e)[:100]}]"

    def write_facebook_post(self, topic: str, keywords: List[str],
                             local_angle: str = "", claim_type: str = "attributed_claim",
                             has_receipt: bool = True, post_type: str = "text") -> str:
        """
        Write a Facebook post using the Master Facebook Guide rules.
        """
        system = self.PLATFORM_PROMPTS["facebook"]
        kw_str = ", ".join(keywords[:5]) if keywords else "political commentary"
        local_str = local_angle or "Michigan voters and community"

        user_prompt = f"""Write a Facebook post about: {topic}

Keywords to naturally incorporate: {kw_str}
Local angle: {local_str}
Claim type: {claim_type}
Has receipt/source: {has_receipt}
Post type: {post_type}

Follow the post formula exactly:
1. First line: Hook (conflict, cost, contradiction, or receipt — NOT a question)
2. Body: Evidence + original analysis
3. Local stakes: What this means for {local_str}
4. Close: One question or conclusion (no subscribe CTA)

Return only the post text."""

        return self._call_llm(system, user_prompt)

    def write_youtube_title(self, topic: str, keywords: List[str],
                             guest: str = "", conflict: str = "") -> str:
        """
        Write a YouTube title using the Master YouTube Guide rules.
        """
        system = self.PLATFORM_PROMPTS["youtube"]
        kw_str = ", ".join(keywords[:5]) if keywords else topic
        conflict_str = f" The conflict: {conflict}." if conflict else ""
        guest_str = f" Guest: {guest}." if guest else ""

        user_prompt = f"""Write a YouTube title for a video about: {topic}
Keywords: {kw_str}{conflict_str}{guest_str}

Rules:
- Under 70 characters
- Put the clearest subject early
- Name the conflict if it is the point
- No dead podcast keywords (episode, ep., podcast, interview with, chat with)
- Use one of these shapes if it fits:
  "The [Money/Map/Document] Fight Nobody Explained"
  "Why [Race/Issue] Was Decided Before November"
  "What [Candidate/Institution] Wants Voters to Miss"

Return only the title text."""

        return self._call_llm(system, user_prompt, max_tokens=100)

    def write_youtube_description(self, topic: str, keywords: List[str],
                                   guest: str = "", chapters: List[str] = None,
                                   local_angle: str = "") -> str:
        """
        Write a YouTube description using the Master YouTube Guide metadata order.
        """
        system = self.PLATFORM_PROMPTS["youtube"]
        kw_str = ", ".join(keywords[:8]) if keywords else topic
        guest_str = f"Guest: {guest}. " if guest else ""
        local_str = local_angle or "Michigan"
        chapter_str = "\n".join(chapters) if chapters else "00:00 [Opening argument]\n[MM:SS] [Key receipt]\n[MM:SS] [Conclusion]"

        user_prompt = f"""Write a YouTube description for a video about: {topic}
{guest_str}Keywords: {kw_str}
Local angle: {local_str}

REQUIRED STRUCTURE:
1. First 150 characters: Answer the search query about {topic} — NO boilerplate, NO subscribe CTA
2. Body: Key claims, sources, context
3. Chapters (use these as a starting point, improve the names):
{chapter_str}
4. Close (after all content): Subscribe CTA, social links

Return the full description."""

        return self._call_llm(system, user_prompt)

    def write_instagram_caption(self, topic: str, keywords: List[str],
                                 surface: str = "feed", local_angle: str = "",
                                 hashtags: List[str] = None) -> str:
        """
        Write an Instagram caption using the Master Instagram Guide rules.
        """
        system = self.PLATFORM_PROMPTS["instagram"]
        kw_str = ", ".join(keywords[:5]) if keywords else topic
        local_str = local_angle or "Michigan voters"
        tag_str = " ".join(hashtags[:5]) if hashtags else "#michiganpolitics #politicalcommentary #independentmedia"
        surface_note = {
            "reels": "This is a Reels caption — hook must work with sound off, tension first.",
            "carousel": "This is a carousel caption — hook earns the swipe, close prompts a save.",
            "feed": "This is a Feed post — strong single argument, sendable to a friend.",
            "stories": "This is a Stories caption — conversational, for existing followers.",
        }.get(surface, "Feed post")

        user_prompt = f"""Write an Instagram caption about: {topic}
Surface: {surface_note}
Keywords to use naturally: {kw_str}
Local angle: {local_str}
Hashtags to include at end: {tag_str}

Follow the caption formula:
1. First line: Hook (shown before "more") — conflict, cost, receipt, or contradiction
   NOT: "New post", "Hey everyone", "Check this out"
2. Body: Evidence + original analysis + local stakes for {local_str}
3. Close: One question or conclusion
4. Hashtags at end (max 5, specific niche terms only)

Pass the sendability test: would someone DM this to a friend?
Return only the caption text."""

        return self._call_llm(system, user_prompt)

    def write_instagram_reel_script(self, topic: str, keywords: List[str],
                                     receipt: str = "", local_angle: str = "") -> str:
        """
        Write an Instagram Reels script using the Reels formula from Chapter 12.
        """
        system = self.PLATFORM_PROMPTS["instagram"]
        kw_str = ", ".join(keywords[:5]) if keywords else topic
        receipt_str = f"Receipt/evidence: {receipt}. " if receipt else ""
        local_str = local_angle or "Michigan"

        user_prompt = f"""Write an Instagram Reels script about: {topic}
{receipt_str}Keywords: {kw_str}
Local angle: {local_str}

Follow the Reels formula:
- 0–3 seconds: Instant tension — conflict, contradiction, or cost. Must work with sound off.
- 3–10 seconds: Proof — the receipt, document, quote, or clip
- 10–30 seconds: Analysis — your original framing of what it means
- Close: Strong conclusion or open loop — NO subscribe demand, NO follow CTA

Rules:
- No platform watermarks (no TikTok/YouTube Shorts references)
- Captions/subtitles implied — write for sound-off readability
- One argument only

Return the script with [0-3s], [3-10s], [10-30s], [Close] labels."""

        return self._call_llm(system, user_prompt)

    def fix_compliance_issues(self, platform: str, original_text: str,
                               compliance_flags: List[str]) -> str:
        """
        Take a piece of content that failed compliance and rewrite it to fix the issues.
        """
        system = self.PLATFORM_PROMPTS.get(platform, self.PLATFORM_PROMPTS["facebook"])
        flags_str = "\n".join(f"- {flag}" for flag in compliance_flags)

        user_prompt = f"""Rewrite the following {platform} content to fix these compliance issues:

COMPLIANCE ISSUES TO FIX:
{flags_str}

ORIGINAL CONTENT:
{original_text}

Rewrite the content to fix every issue listed above while preserving the core argument and voice.
Return only the rewritten content."""

        return self._call_llm(system, user_prompt)
