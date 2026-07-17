# `twma_v1.6` architecture

This is the v1.6 textual-world-model follow-up.

## Isolation and controller

Codex runs unsandboxed inside an isolated Docker container. The game implementation and `arc_agi` library remain in a separate server container, and each new playthrough starts with a clean run workspace and cleaned Codex state except for required authentication data.

[`agent.py`](src/agent/agent.py) is a thin external controller. It starts the client, sends prompts, inspects session progress, and selects the normal, reset, stuck, or trouble protocol; game-solving logic remains with Codex. [`agent_runner.py`](src/agent/agent_runner.py) supervises recovery after an unexpected exit or 30 minutes without log activity, with at most ten recovery attempts. The Docker image installs Codex CLI `0.144.1`.

## Treatment

- The [main prompt](src/agent/prompts/main_prompt.md) requires a concise textual model but no executable simulator or planner deliverable.
- Scheduled simplification and exact replay verification are disabled.
- The v1.5 trouble intervention and accelerated client are enabled.
- The client rejects every action except `RESET` after `GAME_OVER`.

## Initial agent workspace

[`workspace_init/`](src/agent/workspace_init) contains only the live game client and its ASCII-to-PNG helper. No world-model templates, planner templates, or verifier utilities are supplied.
