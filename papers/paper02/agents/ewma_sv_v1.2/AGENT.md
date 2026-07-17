# `ewma_sv_v1.2` architecture

This is the v1.2 fixed-interface executable-world-model treatment with scheduled simplification and verification.

## Isolation and controller

Codex runs unsandboxed inside an isolated Docker container. The game implementation and `arc_agi` library remain in a separate server container, and each new playthrough starts with a clean run workspace and cleaned Codex state except for required authentication data.

[`agent.py`](src/agent/agent.py) is a thin external controller. It starts the client, sends prompts, inspects session progress, and selects the normal, reset, or stuck protocol; game-solving logic remains with Codex. [`agent_runner.py`](src/agent/agent_runner.py) supervises recovery after an unexpected exit or 30 minutes without log activity, with at most ten recovery attempts. The Docker image installs Codex CLI `0.128.0`.

## Treatment

- The [main prompt](src/agent/prompts/main_prompt.md) fixes interfaces for the transition engine, initial-state reconstruction, observation renderer, and main planner.
- The same light/four-stage simplification schedule as `ewma_s_v1.2` runs in normal, reset, stuck, and recovery paths.
- Codex is instructed to run the world-model and planner verifiers after changes; the external controller does not silently enforce them.
- Online plan gating is not required. `plan_executor.py` is available for Codex to discover but is not named in the prompts.

## Initial agent workspace

The workspace supplies empty model stubs:

- [`world_model_engine.py`](src/agent/workspace_init/world_model_engine.py)
- [`world_model_state_io.py`](src/agent/workspace_init/world_model_state_io.py)
- [`world_model_main_planner.py`](src/agent/workspace_init/world_model_main_planner.py)

It also supplies the live client, [world-model replay verification](src/agent/workspace_init/verify_world_model.py), [planner verification](src/agent/workspace_init/verify_main_planner.py), planner runners, session/state-reconstruction helpers, mismatch visualization, and [`plan_executor.py`](src/agent/workspace_init/plan_executor.py). These files contain no game-specific rules, layouts, or solutions.
