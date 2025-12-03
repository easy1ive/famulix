"""Personalization: applying preferences to briefing output.

Handles tone, format, ordering preferences with explainability ("why this
choice"). Includes cold-start defaults and A/B-style counterfactual comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from famulix.preferences import PreferenceProfile


@dataclass(frozen=True)
class PersonalizationConfig:
    """Default preferences used for cold-start."""

    default_tone: str = "neutral"
    default_format: str = "markdown"
    default_ordering: str = "priority"
    default_length: str = "medium"


@dataclass
class AppliedPreference:
    """A single applied preference with explanation."""

    key: str
    value: str
    confidence: float
    reason: str


@dataclass
class BriefingStyle:
    """Resolved briefing style with provenance."""

    tone: str = "neutral"
    format: str = "markdown"
    ordering: str = "priority"
    length: str = "medium"
    applied: list[AppliedPreference] = field(default_factory=list)

    def explain(self) -> list[str]:
        """Human-readable list of why each choice was made."""
        return [f"{p.key}: {p.value} (conf={p.confidence:.2f}) — {p.reason}" for p in self.applied]


def apply_preferences(
    profile: PreferenceProfile,
    *,
    now_s: int,
    config: PersonalizationConfig | None = None,
) -> BriefingStyle:
    """Resolve preferences into a concrete briefing style.

    Each preference that's confident enough is applied with an explanation.
    Cold-start defaults fill in any gaps.
    """
    cfg = config or PersonalizationConfig()
    style = BriefingStyle()
    prefs = profile.current_preferences(now_s)

    # Tone
    if "tone" in prefs:
        val, conf = prefs["tone"]
        style.tone = val
        style.applied.append(
            AppliedPreference(
                key="tone",
                value=val,
                confidence=conf,
                reason="learned from user feedback signals",
            )
        )
    else:
        style.tone = cfg.default_tone
        style.applied.append(
            AppliedPreference(
                key="tone",
                value=cfg.default_tone,
                confidence=0.0,
                reason="cold-start default (no feedback yet)",
            )
        )

    # Format
    if "format" in prefs:
        val, conf = prefs["format"]
        style.format = val
        style.applied.append(
            AppliedPreference(
                key="format",
                value=val,
                confidence=conf,
                reason="learned from user feedback signals",
            )
        )
    else:
        style.format = cfg.default_format
        style.applied.append(
            AppliedPreference(
                key="format",
                value=cfg.default_format,
                confidence=0.0,
                reason="cold-start default (no feedback yet)",
            )
        )

    # Ordering
    if "ordering" in prefs:
        val, conf = prefs["ordering"]
        style.ordering = val
        style.applied.append(
            AppliedPreference(
                key="ordering",
                value=val,
                confidence=conf,
                reason="learned from user feedback signals",
            )
        )
    else:
        style.ordering = cfg.default_ordering
        style.applied.append(
            AppliedPreference(
                key="ordering",
                value=cfg.default_ordering,
                confidence=0.0,
                reason="cold-start default (no feedback yet)",
            )
        )

    # Length
    if "length" in prefs:
        val, conf = prefs["length"]
        style.length = val
        style.applied.append(
            AppliedPreference(
                key="length",
                value=val,
                confidence=conf,
                reason="learned from user feedback signals",
            )
        )
    else:
        style.length = cfg.default_length
        style.applied.append(
            AppliedPreference(
                key="length",
                value=cfg.default_length,
                confidence=0.0,
                reason="cold-start default (no feedback yet)",
            )
        )

    return style


def counterfactual_compare(
    profile_a: PreferenceProfile,
    profile_b: PreferenceProfile,
    *,
    now_s: int,
) -> dict[str, dict[str, object]]:
    """Compare two profiles side-by-side for A/B-style analysis.

    Returns {key: {"a": value_a, "b": value_b, "changed": bool}}.
    """
    style_a = apply_preferences(profile_a, now_s=now_s)
    style_b = apply_preferences(profile_b, now_s=now_s)
    result: dict[str, dict[str, object]] = {}
    for key in ["tone", "format", "ordering", "length"]:
        va = getattr(style_a, key)
        vb = getattr(style_b, key)
        result[key] = {"a": va, "b": vb, "changed": va != vb}
    return result


def order_items(
    items: list[dict[str, object]],
    ordering: str,
) -> list[dict[str, object]]:
    """Sort items according to the chosen ordering strategy.

    Strategies:
    - priority: highest priority first
    - recency: newest first
    - category: grouped by category (stable within groups)
    - alphabetical: by title
    """
    if ordering == "priority":
        return sorted(items, key=lambda x: _number(x.get("priority"), 0.5), reverse=True)
    if ordering == "recency":
        return sorted(items, key=lambda x: int(_number(x.get("timestamp_s"), 0)), reverse=True)
    if ordering == "category":
        return sorted(items, key=lambda x: str(x.get("category", "")))
    if ordering == "alphabetical":
        return sorted(items, key=lambda x: str(x.get("title", "")))
    return list(items)


def default_style(config: PersonalizationConfig | None = None) -> BriefingStyle:
    """Return a cold-start briefing style built entirely from defaults."""
    cfg = config or PersonalizationConfig()
    from famulix.preferences import PreferenceProfile

    return apply_preferences(PreferenceProfile(), now_s=0, config=cfg)


def style_summary(style: BriefingStyle) -> dict[str, str]:
    """Return a flat dict of style choices for logging/serialization."""
    return {
        "tone": style.tone,
        "format": style.format,
        "ordering": style.ordering,
        "length": style.length,
    }


def personalization_diagnostics(
    style: BriefingStyle,
    explanation: list[str] | None = None,
) -> dict[str, object]:
    """Generate diagnostics for a personalization result.

    Returns a dict with:
    - style: the briefing style choices
    - explanation_count: number of explanation reasons
    - has_tone: whether a tone was chosen
    - has_format: whether a format was chosen
    - has_ordering: whether an ordering was chosen
    """
    return {
        "style": style_summary(style),
        "explanation_count": len(explanation) if explanation else 0,
        "has_tone": bool(style.tone),
        "has_format": bool(style.format),
        "has_ordering": bool(style.ordering),
    }


def compare_personalization_variants(
    variants: dict[str, BriefingStyle],
) -> dict[str, object]:
    """Compare multiple personalization variants.

    Returns a dict with:
    - variant_count: number of variants compared
    - variant_names: list of variant names
    - differences: dict showing which fields differ across variants
    """
    if not variants:
        return {
            "variant_count": 0,
            "variant_names": [],
            "differences": {},
        }

    names = list(variants.keys())
    styles = list(variants.values())

    # Check which fields differ
    differences: dict[str, list[str]] = {}
    for attr_name in ["tone", "format", "ordering", "length"]:
        values = [getattr(s, attr_name) for s in styles]
        if len(set(values)) > 1:
            differences[attr_name] = [
                f"{name}: {val}" for name, val in zip(names, values, strict=False)
            ]

    return {
        "variant_count": len(variants),
        "variant_names": names,
        "differences": differences,
    }


def _number(value: object, default: float) -> float:
    """Read a numeric sort field without accepting arbitrary objects."""
    return float(value) if isinstance(value, (int, float)) else default
