# Privacy Guide

Famulix implements GDPR-style privacy controls with tiered access and right-to-forget semantics.

## Privacy Tiers

Four tiers with increasing restriction:

1. **public**: No restrictions, exportable
2. **shared**: Readable by trusted components
3. **personal**: Restricted access, audit logged
4. **private**: Highly restricted, explicit approval required

## PII Detection

Automatic detection of email addresses, phone numbers, credit card numbers (with checksum validation), and physical addresses.

## Redaction

Two modes: detect (report PII locations) and redact (replace with masked values).

## Right-to-Forget

Delete a memory and cascade across all data structures with tombstones to prevent re-derivation.

## Offline Operation

All privacy operations run locally. No data leaves your machine.
