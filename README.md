# JARVIS Cognitive System

JARVIS is a modular cognitive architecture scaffold designed to coordinate planning, memory, runtime control, and specialized worker execution. This repository captures the initial architecture baseline for the system so the core layers can evolve under version control.

## Architecture Overview

The current scaffold is organized around a small set of cooperating layers:

- `constitutional_core/`: identity and governing principles for system behavior
- `executive_planner/`: queueing, prioritization, validation, audit, and plan creation
- `intent_layer/`: active goals, constraints, and user preference capture
- `memory_system/`: episodic, semantic, and procedural memory primitives
- `workers/`: domain-oriented workers for runtime, finance, studio, and study tasks
- `runtime/`: runtime bootstrap and autonomy decision logic
- `infrastructure/`: deployment, persistence, and monitoring placeholders
- `interface/`: API, CLI, and dashboard placeholders
- `tests/`: test suite location for validation and regression coverage

## Runtime Entrypoint

Primary runtime bootstrap:

- `runtime/internal_agent_runtime.py`

Within the workspace-level scaffold, this corresponds to:

- `jarvis_core/runtime/internal_agent_runtime.py`

## Module Explanation

### Constitutional Core

Defines the system identity and principles that constrain planning and execution.

### Executive Planner

Provides the initial planning toolchain: task intake, prioritization, validation, audit logging, and plan assembly.

### Intent Layer

Stores active goals, constraints, and operating preferences that shape planner decisions.

### Memory System

Separates memory concerns into episodic recall, semantic facts, and procedural routines.

### Worker Framework

Hosts specialized worker adapters that can accept domain-specific tasks.

### Runtime Engine

Bootstraps the active runtime state and enforces gated autonomy behavior.

## Development Workflow

1. Create or update architecture modules inside the relevant subsystem directory.
2. Add or expand tests in `tests/` as runtime wiring becomes more concrete.
3. Update `ARCHITECTURE.md` when subsystem responsibilities change.
4. Record user-visible architecture milestones in `CHANGELOG.md`.
5. Review `git status` before each commit to ensure only intentional files are tracked.
