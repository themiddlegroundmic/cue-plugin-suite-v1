from __future__ import annotations

from typing import List

from src.core.types.models import CueWriterOutput, CueWriterRequest


class CueIntelligenceWriter:
    """Rule-based v1 writer that consumes only CueIntelligenceReport."""

    def write(self, request: CueWriterRequest) -> CueWriterOutput:
        report = request.intelligenceReport
        episode = request.episode or (report.show.episodes[0] if report.show and report.show.episodes else None)
        if not report.primaryTopic:
            raise ValueError("CueWriterRequest requires an intelligence report with primaryTopic")

        keywords = [k.value for k in report.keywords[:12]]
        primary_keyword = keywords[0] if keywords else report.primaryTopic
        base_title = episode.title if episode else report.primaryTopic
        title = self._title(base_title, primary_keyword)
        opening = self._opening(report.primaryTopic, keywords, report.contentGaps)
        full_description = opening + "\n\n" + self._supporting_description(report)
        chapters = self._chapters(episode, keywords)

        generated = {
            "episodeTitle": title,
            "descriptionOpening150Words": " ".join(opening.split()[:150]),
            "fullDescription": full_description,
            "tags": keywords[:15],
            "chapters": chapters,
        }
        if request.targetPlatform == "youtube":
            generated["youtubeTitle"] = title[:70]
            generated["youtubeDescription"] = full_description
        if request.targetPlatform == "instagram":
            generated["instagramCaption"] = opening + "\n\n" + " ".join("#" + k.replace(" ", "") for k in keywords[:8])
            generated["hashtags"] = ["#" + k.replace(" ", "") for k in keywords[:12]]
        if request.targetPlatform == "facebook":
            generated["facebookPost"] = opening

        return CueWriterOutput(
            generatedText=generated,
            whyThisWorks=[
                f"Uses the primary topic from the intelligence report: {report.primaryTopic}.",
                f"Prioritizes keywords supported by collected signals: {', '.join(keywords[:5])}.",
                f"Responds to content gaps: {self._gap_text(report.contentGaps[0]) if report.contentGaps else 'none detected'}.",
            ],
            keywordsUsed=keywords[:10],
            riskNotes=report.riskFlags or ["No major v1 risk flags detected."],
            scoreImpactEstimate={
                "opportunityScore": min(100, report.opportunityScore + 5),
                "platformReadinessScore": min(100, report.platformReadinessScore + 12),
                "confidenceScore": report.confidenceScore,
            },
        )

    def _title(self, current_title: str, primary_keyword: str) -> str:
        title = current_title.strip()
        if primary_keyword.lower() not in title.lower():
            title = f"{primary_keyword.title()}: {title}"
        return title[:80].rstrip(" :-")

    def _opening(self, topic: str, keywords: List[str], gaps: List[str]) -> str:
        keyword_phrase = ", ".join(keywords[:3]) if keywords else topic
        gap = self._gap_text(gaps[0]) if gaps else "This episode focuses on the clearest available audience opportunity."
        return (
            f"This episode examines {topic} through the lens of {keyword_phrase}. "
            f"{gap} The discussion is structured for listeners searching for practical context, current signals, and clear takeaways."
        )

    def _supporting_description(self, report) -> str:
        competitors = ", ".join(c.get("showTitle", "") for c in report.competitors[:3] if c.get("showTitle"))
        competitor_note = f"Competitive context reviewed: {competitors}." if competitors else "Competitive context was limited in this scan."
        return (
            f"Opportunity Score: {report.opportunityScore}. "
            f"Platform Readiness Score: {report.platformReadinessScore}. "
            f"Confidence Score: {report.confidenceScore}. {competitor_note}"
        )

    def _chapters(self, episode, keywords: List[str]):
        if episode and episode.chapters:
            return episode.chapters
        chapter_topics = keywords[:4] or ["Context", "Signals", "Content gaps", "Takeaways"]
        return [{"time": f"00:{i * 5:02d}:00", "name": topic.title()} for i, topic in enumerate(chapter_topics)]

    def _gap_text(self, gap) -> str:
        if isinstance(gap, dict):
            topic = gap.get("gap_topic", "content gap")
            reason = gap.get("reason", "")
            angle = gap.get("suggested_angle", "")
            return f"{topic}: {reason} {angle}".strip()
        return str(gap)
