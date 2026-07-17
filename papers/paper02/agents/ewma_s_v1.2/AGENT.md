# `ewma_s_v1.2` architecture

This is the v1.2 flexible-interface executable-world-model treatment with scheduled simplification.

## Isolation and controller

Codex runs unsandboxed inside an isolated Docker container. The game implementation and `arc_agi` library remain in a separate server container, and each new playthrough starts with a clean run workspace and cleaned Codex state except for required authentication data.

[`agent.py`](src/agent/agent.py) is a thin external controller. It starts the client, sends prompts, inspects session progress, and selects the normal, reset, or stuck protocol; game-solving logic remains with Codex. [`agent_runner.py`](src/agent/agent_runner.py) supervises recovery after an unexpected exit or 30 minutes without log activity, with at most ten recovery attempts. The Docker image installs Codex CLI `0.128.0`.

## Treatment

- The [main prompt](src/agent/prompts/main_prompt.md) requires textual and executable world models plus planning code, with interfaces chosen by Codex.
- Whenever Codex returns control, the controller sends one light simplification prompt on level 1 and early in the first level-2 attempt.
- In later states it sends three model-simplification prompts followed by a planner-refactoring prompt.
- No fixed model templates or exact replay verifier utilities are supplied.

## Initial agent workspace

[`workspace_init/`](src/agent/workspace_init) contains only the live game client and its ASCII-to-PNG helper. Codex creates its executable model and planning code during the run.
