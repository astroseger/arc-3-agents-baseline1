# `ewma_sv_v1.5` architecture

This is the v1.5 fixed-interface verification follow-up.

## Isolation and controller

Codex runs unsandboxed inside an isolated Docker container. The game implementation and `arc_agi` library remain in a separate server container, and each new playthrough starts with a clean run workspace and cleaned Codex state except for required authentication data.

[`agent.py`](src/agent/agent.py) is a thin external controller. It starts the client, sends prompts, inspects session progress, and selects the normal, reset, stuck, or trouble protocol; game-solving logic remains with Codex. [`agent_runner.py`](src/agent/agent_runner.py) supervises recovery after an unexpected exit or 30 minutes without log activity, with at most ten recovery attempts. The Docker image installs Codex CLI `0.128.0`.

## Treatment

- It retains the fixed engine/reconstruction-renderer/planner interfaces, verification workspace, and simplification schedule from `ewma_sv_v1.2`.
- After `GAME_OVER`, the controller sends a trouble prompt when more than 50 additional actions have accumulated on that level since the previous trouble intervention.
- Level 1 and later levels use separate trouble prompts.
- The game client accelerates frame-to-image conversion relative to v1.2.

## Initial agent workspace

The workspace supplies empty [engine](src/agent/workspace_init/world_model_engine.py), [state-I/O](src/agent/workspace_init/world_model_state_io.py), and [planner](src/agent/workspace_init/world_model_main_planner.py) stubs, plus the live client, replay and planner verifiers, planner runners, session/state-reconstruction helpers, mismatch visualization, and [`plan_executor.py`](src/agent/workspace_init/plan_executor.py). These files contain no game-specific rules, layouts, or solutions.
