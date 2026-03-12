# Architecture Overview

This document describes the baseline structure of the JARVIS Cognitive System scaffold.

## Constitutional Core

Location: `constitutional_core/`

The Constitutional Core defines the identity of the system and the principles that govern its behavior. In the current scaffold, this layer is represented by JSON configuration files that establish mission, operating mode, capabilities, and high-level behavioral principles such as alignment, safety, traceability, and adaptation.

Primary artifacts:

- `constitutional_core/identity.json`
- `constitutional_core/principles.json`

## Executive Planner

Location: `executive_planner/`

The Executive Planner is responsible for turning goals into draft plans and maintaining order over task execution. It currently includes:

- a queue primitive for task intake
- a prioritizer for weighted scoring
- a validator for structural plan checks
- an audit logger for decision traceability
- a planner for draft plan creation

This layer is expected to become the orchestration brain that connects goals, memory, workers, and runtime policy.

## Memory System

Location: `memory_system/`

The Memory System separates stored knowledge into three distinct forms:

- Episodic memory for time-ordered events and recent activity
- Semantic memory for facts and concepts
- Procedural memory for reusable step sequences

This split keeps retrieval and updates conceptually clean while supporting future reasoning and adaptation workflows.

## Worker Framework

Location: `workers/`

The Worker Framework contains specialized worker stubs that accept tasks in different domains. The current scaffold includes workers for:

- runtime operations
- finance
- studio or creative tasks
- study and learning tasks

Each worker currently exposes a minimal `handle` method and returns a normalized acceptance payload. Later versions can extend these workers with capabilities, permissions, and tool integrations.

## Runtime Engine

Location: `runtime/`

The Runtime Engine is the execution layer that bootstraps the system and governs autonomous behavior. The current scaffold includes:

- `runtime/internal_agent_runtime.py` for runtime initialization
- `runtime/autonomy.py` for simple approval and supervision gates

The runtime entrypoint advertises planner, memory, and worker dependencies as a lightweight bootstrap contract. As the architecture evolves, this layer should become the central coordinator for lifecycle management, worker dispatch, validation, and observability.
