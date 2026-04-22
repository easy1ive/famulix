# Reporting Demo

This example demonstrates how to generate human-readable reports from evaluation scorecards and preference profiles.

## What it shows

- **Preference profile reports**: Current preferences with confidence levels, entry counts, and decay information
- **Evaluation reports**: Full evaluation metrics with per-slice breakdowns and honest limitations
- **Automatic limitations sections**: Both reports include limitations that are generated from the evaluation context, ensuring honest disclosure

## Running the example

```bash
python examples/09_reporting_demo.py
```

Or via the project Makefile:

```bash
make examples
```

## Expected output

The example produces two reports:

### Preference Profile Report

```
# Preference Profile Report

- **Version**: 31
- **Total entries**: 30
- **Unique keys**: 5
- **Decay half-life**: 30.0 days

## Current Preferences

### tone

- **Preferred value**: formal
- **Confidence**: 0.847
- **Total entries**: 8
...
```

### Evaluation Report

```
# Evaluation Report

## Overall Metrics

- **Recall@10**: 0.850
- **Precision@10**: 0.720
- **Contradiction resolution**: 0.950
- **Citation coverage**: 0.880
- **Budget adherence**: 1.000
- **Preference calibration (Brier)**: 0.1234
- **Deletion resurrection violations**: 0
- **Privacy violations**: 0

## Limitations

- All metrics computed on synthetic data with planted ground truth
- No real LLM or real user data involved
- Results reflect framework mechanics, not conversational ability
```

## Key features demonstrated

1. **Preference decay**: The report shows how preferences decay over time based on the configured half-life
2. **Confidence thresholds**: Only preferences with sufficient confidence are shown
3. **Per-slice breakdowns**: Evaluation metrics can be broken down by fact type, time window, or other dimensions
4. **Honest limitations**: Both reports include automatically generated limitations sections that disclose the synthetic nature of the data

## Use cases

- **Debugging**: Understand what preferences the system has learned and with what confidence
- **Auditing**: Generate evaluation reports for review and comparison across different configurations
- **Documentation**: Produce human-readable summaries of system behavior for stakeholders
- **Reproducibility**: Reports include version numbers and configuration details for reproducibility

## Related examples

- [Persona Day Example](README_04_persona_day.md): Full end-to-end pipeline with briefing generation
- [Preference Loop Example](README_03_preference.md): Preference learning and calibration
- [Evaluation Harness](../docs/EVALUATION.md): Detailed evaluation documentation
