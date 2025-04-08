# Architecture

famulix separates observations from derived memories. Versioned `Event` records form an append-only SQLite log; encoders project events into a provenance-linked `MemoryGraph`. Consolidation resolves duplicate and contradictory facts, while decay and deletion update active state without erasing audit tombstones.

Retrieval combines lexical matches with time and salience signals. Context assembly selects whole items under a token estimate budget. Preference feedback is maintained separately from factual memory and can explain the style applied to the daily briefing. Policy checks gate tool execution and plan steps. Session traces retain decisions and receipts for deterministic replay.

The daily briefing composes selected memories and includes source IDs on each item. Its HTML and SVG are rendered locally with escaped text. The synthetic history factory supplies reproducible fixtures and planted ground truth; its scores describe mechanics on those fixtures only.

Evaluation runs an explicit private-to-public export probe and counts whether the policy gate permits it. It also tombstones a live synthetic fact, rebuilds the active retrieval index, and counts any resurfacing result. These counters describe those executed checks, not a general privacy certification.

## Mechanism references

- Packer et al., [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560), for tiered memory as a system design idea.
- Park et al., [Generative Agents](https://arxiv.org/abs/2304.03442), for recency, importance, and relevance as memory signals.
- Robertson and Zaragoza, [The Probabilistic Relevance Framework: BM25 and Beyond](https://doi.org/10.1561/1500000019), for lexical retrieval.
- Carbonell and Goldstein, [The Use of MMR, Diversity-Based Reranking](https://doi.org/10.1145/290941.291025), for diversified selection.
- Brier, [Verification of Forecasts Expressed in Terms of Probability](https://doi.org/10.1175/1520-0493(1950)078%3C0001:VOFEIT%3E2.0.CO;2), for the squared probability score.
- Ebbinghaus, [Memory: A Contribution to Experimental Psychology](https://psychclassics.yorku.ca/Ebbinghaus/), for the historical forgetting-curve concept.

These works motivate mechanisms; famulix provides its own data model and implementation. No result here evaluates a real conversational model.
