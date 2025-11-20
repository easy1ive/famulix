# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-11-12

### Added

- Trainable pairwise rank-fusion model in the optional torch extra, with a
  synthetic demo that measurably lowers training loss and beats the linear
  fusion baseline on the planted rule.
- `apply_reranker` retrieval hook that enforces citation-safety constraints
  on pluggable rerankers.
- Deterministic connector failure simulation (`FlakyConnector`) and partial
  hub collection (`collect_partial`).
- `trim_to_budget` context fallback that never exceeds the token budget.
- Golden digests for a small seeded persona history and a double-run
- Subgraph extraction and neighborhood queries for memory graph traversal.
- Enhanced query parser with quoted phrases, negated terms, and graceful
  handling of unclosed quotes.
- Policy conflict diagnostics with concrete overlap sets and sample requests.
- Deterministic Markdown rendering for consolidation reports.
- Decay configuration validation with tier ordering constraints.
- JSON output mode for the recall CLI command.
- Entity alias table validation detecting ambiguous aliases.
- Plan-level budget cap with step budget aggregation and validation.
- Persistent cooldown tracker for trigger scheduling across sessions.
  determinism suite covering the full offline pipeline.
- Version consistency test across pyproject, package, and changelog.
- BM25 index persistence (save/load) with stale-index detection and rebuild
  from graph.
- Episode summary generation with provenance edges citing source episodes.
- Plan DAG step type checking for input/output type validation.
- Policy engine wildcard pattern support ("*" and empty set match any value)
  with enhanced conflict diagnostics.
- Trigger dedupe window suppression to prevent duplicate triggers within
  configurable time windows.
- Enhanced session diff with field-level difference reporting for the first
  N mismatched frames.
- Tool registry idempotency key tracking and cache management helpers.
- Approval queue escalation chains with decision time metrics.

## [0.1.0] - 2026-11-12

- Initial project bootstrap
