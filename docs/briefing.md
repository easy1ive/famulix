# Briefing Application

The briefing application is famulix's flagship end-to-end demo: a deterministic
daily briefing that cites the memories it used and renders self-contained HTML
with embedded SVG visuals.

## Overview

```python
from famulix.briefing import build_briefing, render_briefing_html

briefing = build_briefing(
    graph=graph,
    date_str="2026-03-15",
    now_s=1000000,
    budget_tokens=500,
    seed=42,
)

html = render_briefing_html(briefing)
with open("briefing.html", "w") as f:
    f.write(html)
```

## Pipeline

The briefing pipeline has four stages:

1. **Gather**: Collect candidate memories (agenda, commitments, reminders, recent facts)
2. **Select**: Choose the highest-value items within the token budget
3. **Compose**: Render each item with title, body, and priority
4. **Cite**: Attach memory_ids to each briefing item for provenance

## Briefing Structure

A briefing contains sections:

- **Agenda**: Calendar events and meetings for the day
- **Commitments**: Promises and obligations extracted from messages
- **Reminders**: Time-sensitive action items
- **Recent Memories**: Important facts from the past few days

Each section contains items with:
- `title`: Short human-readable label
- `body`: Full content
- `priority`: Importance score (0.0 to 1.0)
- `memory_ids`: List of source memory node_ids

## Citation Integrity

Every briefing item cites the memory nodes it was derived from:

```python
for item in briefing.items:
    for mid in item.memory_ids:
        node = graph.get_node(mid)
        assert node is not None, "Citation must resolve to existing node"
        assert node.is_active, "Citation must point to active node"
```

The evaluation harness verifies 100% citation coverage.

## HTML Rendering

`render_briefing_html()` produces self-contained HTML with embedded SVG:

```python
from famulix.briefing import render_briefing_html

html = render_briefing_html(briefing)
```

The HTML includes:
- Day ribbon: visual timeline of the day
- Commitment timeline: chronological view of obligations
- Retention heatmap: memory importance over time
- Embedded run metadata: versions, seeds, config hash

All CSS and SVG are inline — no external dependencies.

## Markdown Rendering

For simpler output, use `render_briefing_markdown()`:

```python
from famulix.briefing import render_briefing_markdown

md = render_briefing_markdown(briefing)
print(md)
```

## Personalization

Briefings can be personalized based on learned preferences:

```python
from famulix.personalization import apply_preferences

personalized = apply_preferences(
    briefing,
    profile=profile,
    now_s=1000000,
)
```

Preferences affect:
- **Tone**: concise vs verbose
- **Format**: markdown vs plain text
- **Ordering**: priority vs chronological
- **Length**: short vs medium vs long

## Determinism

The briefing is fully deterministic:
- Same seed → identical event selection
- Same events → identical briefing content
- Same briefing → identical HTML bytes

This enables regression testing and CI validation.

## CLI Usage

```bash
famulix brief --persona alex --seed 42 --date 2026-03-15 --output briefing.html
```

## Demo

Run the full persona day demo:

```bash
famulix demo
```

This generates a 14-day synthetic history, builds the memory graph, runs
consolidation, retrieves relevant memories, assembles context, and produces a
briefing with evaluation scores.

## Limitations Section

Every briefing includes an honest limitations section:

```
This briefing is generated from synthetic data with planted ground truth.
It demonstrates memory retrieval and context assembly mechanics.
No real LLM, real user data, or external API was used.
Scores describe only this constructed scenario.
```

This is automatically generated from coverage facts and evaluation results.
