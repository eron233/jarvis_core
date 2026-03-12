# Development Continuation Guide

## Project

- Project name: JARVIS Cognitive System
- Architecture version: 0.1.0
- Project root: `jarvis_core/`
- Runtime entrypoint: `jarvis_core/runtime/internal_agent_runtime.py`

## Modules

- `constitutional_core`
- `executive_planner`
- `intent_layer`
- `memory_system`
- `workers`
- `runtime`
- `infrastructure`
- `interface`
- `tests`

## Next Module To Implement

Recommended next development task:

- Implement runtime-to-planner integration in `runtime/internal_agent_runtime.py` so the entrypoint constructs and coordinates the executive planner, memory layer, and worker registry instead of returning only a static bootstrap payload.

## Resume Development In VS Code

1. Open a terminal in the project root workspace.
2. Change into the repository:
   - `cd jarvis_core`
3. Open the project in VS Code:
   - `code .`
4. Start by reviewing:
   - `README.md`
   - `ARCHITECTURE.md`
   - `runtime/internal_agent_runtime.py`
   - `executive_planner/planner.py`
5. Confirm the repository is clean before new work:
   - `git status`
6. Continue with the next module task and add tests in `tests/` as integration logic is introduced.

## OPEN IN VSCODE

```powershell
cd jarvis_core
code .
```

## Entrypoint Confirmation

- Runtime entrypoint: `jarvis_core/runtime/internal_agent_runtime.py`
