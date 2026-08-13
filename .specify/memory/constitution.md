<!--
Sync Impact Report
- Version change: (template, unversioned) → 1.0.0
- Rationale: Initial ratification of the project constitution — first concrete adoption from the
  Spec Kit template constitutes a MAJOR version per semantic versioning rules for governance docs.
- Modified principles: N/A (initial fill of placeholder template)
- Added sections:
  - I. Library-First
  - II. CLI Interface
  - III. Test-First (NON-NEGOTIABLE)
  - IV. Integration Testing
  - V. Observability & Simplicity
  - Technology & Quality Constraints
  - Development Workflow & Review Process
  - Governance
- Removed sections: none
- Deferred / TODO placeholders: none — all template tokens resolved
- Templates requiring follow-up review (not modified by this command):
  - .specify/templates/plan-template.md — verify Constitution Check gates still reference these
    five principles when next used
  - .specify/templates/spec-template.md — no direct constitution references found
  - .specify/templates/tasks-template.md — no direct constitution references found
  - .specify/templates/checklist-template.md — no direct constitution references found
-->

# aiboots Constitution

## Core Principles

### I. Library-First
Every feature MUST begin as a standalone library, not as code embedded directly in an
application entry point. Libraries MUST be self-contained, independently testable, and
documented with a clear purpose statement. A library MUST NOT be created solely to group
code organizationally — each one must justify its own existence as an independently usable
unit.

**Rationale**: Library-first design forces clear boundaries and reusable interfaces from the
start, preventing tangled, monolithic code that is difficult to test or reuse across contexts.

### II. CLI Interface
Every library MUST expose its functionality through a command-line interface. Interfaces MUST
follow a text in/out protocol: input arrives via stdin and/or arguments, standard output carries
results, and standard error carries diagnostics and failures. CLIs MUST support both a
human-readable output format and a JSON output format for machine consumption.

**Rationale**: A uniform text-based protocol keeps libraries composable, scriptable, and
debuggable without requiring a GUI or bespoke integration for every consumer.

### III. Test-First (NON-NEGOTIABLE)
Test-Driven Development is mandatory for all new functionality. Tests MUST be written first,
reviewed and approved by the user, confirmed to fail, and only then followed by implementation.
The Red-Green-Refactor cycle MUST be strictly followed. No implementation code may be written
before a corresponding failing test exists.

**Rationale**: Writing tests first ensures requirements are understood and verifiable before
implementation begins, and prevents tests from being retrofitted to match whatever the code
happens to do.

### IV. Integration Testing
Integration tests are REQUIRED for: new library contract surfaces, any change to an existing
contract, inter-service or inter-library communication paths, and shared data schemas. Unit
tests alone are NOT sufficient for these areas — the contract between components MUST be
exercised directly.

**Rationale**: Unit tests validate internals in isolation but cannot catch mismatches at the
boundaries where independently developed pieces integrate; those boundaries are where real
regressions occur.

### V. Observability & Simplicity
Text-based I/O (per Principle II) MUST be preserved so system behavior remains debuggable from
logs and CLI output alone. Structured logging is REQUIRED for all libraries and services.
Implementations MUST start as simple as possible (YAGNI) — additional complexity, abstraction
layers, or configurability MUST be justified by a concrete, current requirement, not a
speculative future one.

**Rationale**: Systems that are observable and simple by default are far cheaper to debug,
extend, and hand off than systems optimized preemptively for flexibility no one has asked for
yet.

## Technology & Quality Constraints

All code MUST pass automated tests and linting before being considered complete. Breaking
changes to a library's public CLI or API surface MUST be called out explicitly and versioned
accordingly (MAJOR version bump) rather than introduced silently. Dependencies MUST be
justified — prefer the standard library or an already-adopted dependency over adding a new one
for marginal convenience.

## Development Workflow & Review Process

All feature work MUST flow through the Spec Kit lifecycle (`/speckit-specify` →
`/speckit-plan` → `/speckit-tasks` → `/speckit-implement`) so that specification, design, and
tests precede implementation. Every pull request or review MUST verify compliance with the
Core Principles above before approval. Any deviation from a principle MUST be documented with
an explicit justification in the relevant plan's Complexity Tracking section; unjustified
complexity is grounds for rejecting a design.

## Governance

This constitution supersedes all other project practices and conventions. Amendments require:
(1) a documented rationale for the change, (2) an explicit version bump following the semantic
versioning policy below, and (3) propagation of any resulting changes to dependent templates
and guidance docs in the same amendment.

**Versioning policy**:
- MAJOR: Backward-incompatible governance changes, or removal/redefinition of an existing
  principle.
- MINOR: A new principle or section is added, or existing guidance is materially expanded.
- PATCH: Clarifications, wording fixes, typo corrections, or other non-semantic refinements.

**Compliance review**: All plans and PRs MUST include a Constitution Check step verifying
alignment with the Core Principles. Complexity or deviations MUST be justified in writing;
unjustified deviations block approval.

**Version**: 1.0.0 | **Ratified**: 2026-08-05 | **Last Amended**: 2026-08-05
