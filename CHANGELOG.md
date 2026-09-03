# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5] - 2026-11-12

### Added
- Consolidation tie-breaking with source trust and deterministic id ordering
- Decay steady-state simulation with configurable tier thresholds
- Deletion non-resurrection invariant across recall, context, and export paths
- Session replay checkpoint resume at arbitrary event offset
- Trigger suppression when briefing already covers the reminder item
- Eventlog schema v4 migration with content_hash column
- Preference calibration reliability bins and error measurement
- Privacy tier enforcement leak matrix with deny-by-default
- Policy conflict diagnostics with precedence detection
- End-to-end pipeline integration tests (ingest → consolidate → recall → brief)
- Performance measurement for recall latency on 90-day persona

### Fixed
- Examples 06, 07, 09 corrected to match current API signatures

## [0.1.4] - 2026-11-12

### Fixed
- Consolidation is now truly idempotent (loops until stable)
- Evaluation maps planted event_ids to fact node_ids correctly
- Per-fact query retrieval instead of single generic query
- Mypy type errors resolved across six modules

### Added
- Integration tests for full consolidate-retrieve-brief pipeline
- Integration tests for privacy redaction and deletion cascade
- Integration tests for session replay and preference learning
- Integration tests for approval queue and plan DSL validation
- Memory graph architecture documentation
- Retrieval and context assembly guide
- Detailed evaluation harness documentation

## [0.1.3] - 2026-11-12

### Added
- `validate-session` CLI subcommand for checking session file integrity
- BM25 index save/load methods for persistence across sessions
- Consolidation report formatting with memory citations
- Session crash resume and determinism tests
- Deletion cascade property tests (no resurrection guarantee)
- Plan DAG type validation and budget escalation checks
- End-to-end pipeline recall benchmark
- Session recording and replay documentation

## [0.1.2] - 2026-11-12

### Added
- Helper functions across all modules (statistics, summary, info)
- Export helpers for memory graphs and briefings
- Privacy guide documentation
- Session replay example
- Edge case tests across modules
- Troubleshooting documentation
- GitHub templates (issues, PRs, dependabot)
- Code of conduct

### Changed
- Improved error messages
- Better documentation coverage
- Version bump to 0.1.2

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

## [0.1.3] - 2026-11-12

### Added
- Module info helpers across all modules
- Additional statistics and summary functions
- Improved documentation coverage
- GitHub infrastructure (templates, dependabot, code of conduct)
