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
  determinism suite covering the full offline pipeline.
- Version consistency test across pyproject, package, and changelog.

## [0.1.0] - 2026-11-12

- Initial project bootstrap
