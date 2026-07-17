# Introduction

You are playing a game.

You interact with the real game through the client in `client`. Before doing anything else, read:

- `client/README.md`

Your primary objective is to build and maintain an executable world model of the game.

Use that world model to plan actions and complete all levels using as few moves as possible, including exploration moves.

Actions taken in the real game are costly because each move consumes a limited step budget. Simulation inside the world model is free.

The game consists of several levels with increasing complexity. Later levels usually extend earlier mechanics rather than replacing them, so a useful model may carry ideas forward across levels.

The client may return multiple frames for a single action because of animations or short transitions. For world-model work, final settled ASCII frames are usually the best frame source. Intermediate animation frames and PNG frames may still provide visual clues about mechanics.

# Attempts

If the game is in the `GAME_OVER` state, you should report it, and I will give you another attempt on the same level.

Remember that the game is deterministic: each attempt starts from exactly the same state, so the same actions will lead to exactly the same results.

Do not repeat the same mistakes. Think carefully, analyze previous failed attempts, and try a different approach in new attempts.

You are forbidden to call RESET by yourself.

# Required deliverables for each level

- `world_model.md` -- concise description of the current world model
- `world_model_engine.py` — world model engine, updated continuously so it remains valid for all solved levels so far
- `world_model_state_io.py` — initial-state reconstruction and observation rendering, updated continuously so it remains valid for all solved levels so far
- `world_model_main_planner.py` — main planner, updated continuously so it remains valid for all solved levels so far
- optional `level_N_planner_i.py` — additional intermediate-state planners used during solving
- `level_N_reasoning_log.md` -- short log of hypotheses, evidence, observations, and model updates during level solving
- `level_N_report.md` -- short report written after solving the level, describing what you did and the final form of the model


# Executable world model

Your executable world model should have four explicit parts.

## 1. World model engine

This is the internal game dynamics model.

It should:

- represent the internal game state
- receive an action
- update the state according to inferred mechanics
- be as simple and general as possible

The world model engine must be implemented in `world_model_engine.py` as a function called `world_model_engine`.

The world model engine should model only the dynamics within a single attempt. It should not model transitions between attempts.

`world_model_engine` must receive exactly two arguments:

- `state` — the current internal world-model state
- `action` — the action to apply

and it must return:

- `new_state` — the new internal world-model state
- `game_status` — one of `RUNNING`, `LEVEL_COMPLETED`, or `GAME_OVER` (`RUNNING` is non-terminal state, `LEVEL_COMPLETED` and `GAME_OVER` are terminal states for an-attempt)

The engine state must be a dictionary with the following obligatory field:

- `level` — the level index

and it must also contain the internal representation of the non-terminal game state.

The `action` must be represented as a dictionary with field `name` and two optional parameters `x` and `y` (for `ACTION6`).

Your goal is to infer a compact underlying rule system. The real mechanics are usually relatively simple.

Do **not** hardcode level layouts or ad hoc special cases into the engine unless absolutely necessary.

If some information really is level-specific, isolate it in a clearly separated level-specific data structure rather than burying it in the engine logic.

Hardcode as little as possible.
The model must explain observations through general mechanics, not by memorizing level-specific behavior.

It is strictly forbidden to load real game observations into the world model engine in any way.

## 2. State reconstruction

This logic reconstructs the initial state of the internal world model for each level.

It must be implemented in `world_model_state_io.py` with the following functions.

### `initial_state_reconstruction`

This function reconstructs the initial state for a given level.

The game is deterministic at level start: all attempts for the same level begin from the same initial world state and produce the same initial observation. This is true even in partially visible worlds.

It must receive exactly two parameters:

- `level_index` — the index of the level
- `initial_frame` — the initial settled ASCII frame of the current level

For some games, the entire world is visible in the initial frame; we call these “fully visible worlds.” In such cases, you should reconstruct the world state from the provided initial frame.

For partially visible worlds, `initial_frame` may not contain enough information to reconstruct the full initial world state.

In such cases, you may choose any clean reconstruction strategy, but keep it separate from `initial_state_reconstruction(...)`. One acceptable approach is to write separate reconstruction code that uses all available observations from all attempts of the same level to estimate the level-wide initial full frame. For sliding or scrolling worlds, this full frame may be larger than the visible `64x64` frame.

If you use this approach, save the reconstructed full initial frame as a level artifact, and let `initial_state_reconstruction(...)` load only that artifact, not raw attempts, session logs, later observations, or other real game data.

The saved full initial frame is still a hypothesis. Be conservative at visibility boundaries: do not treat unseen regions as known unless they are forced by evidence.

It is strictly forbidden to load real game observations into `initial_state_reconstruction` in any way, except for the explicitly provided initial frame and any explicitly saved level-wide initial-state reconstruction artifact.

### State Reconstruction Principles

To reconstruct any later non-terminal state of the same attempt:

1. reconstruct the initial state with `initial_state_reconstruction(...)`
2. advance it with `world_model_engine(...)` by simulating the known attempt actions up to the required prefix

## 3. Observation renderer

This is the function that translates the internal world-model state back into the expected ASCII frame.

It must be implemented in `world_model_state_io.py` as a function called `state_renderer`.
You may also define a separate helper such as `apply_render_overrides(frame, state, level_index, attempt_index, step_count)` for verification-only temporary frame patches.

`state_renderer` must receive exactly one argument:

- `state` — the internal world-model state produced by the world model engine

and it must return the corresponding ASCII frame as `numpy.ndarray` of shape `64x64`, dtype `np.int16`.

`state_renderer` only needs to render non-terminal level states. You do not need to render `LEVEL_COMPLETED` or `GAME_OVER` states.

This renderer is required so the model can be verified directly against real observations.

Your model is only acceptable if its rendered settled frame matches the real settled ASCII frame exactly.

If you absolutely cannot yet explain some frame-local visual detail, you may use `apply_render_overrides(...)` as a last-resort verification-only patch hook in `world_model_state_io.py`.
Use it only for narrow visual corrections to specific unresolved frames. Do **not** put game logic, state transitions, or planning logic into this hook.
Every `apply_render_overrides(...)` patch must be treated as temporary and as evidence that the world model is still missing a real mechanic, object identity, latent state variable, or observation rule.

It is strictly forbidden to load real game observations into the observation renderer in any way.

## 4. Main planner

The world model must support planning. The planner is the planner in terms of your internal world model.

It must be implemented in `world_model_main_planner.py` as a function called `planner`.

`planner` must receive:

- `state` — the internal world-model state

and it must return either:

- a list of actions to reach level completion
- `None` if level completion is not reachable

It should be possible to use the world model engine, together with this planner, to infer a sequence of actions required to reach a desired game state.

In most cases, a simple search or planning algorithm should be sufficient.

You must use a planner to guide your actions.

- You must implement the main planner as soon as possible, usually by extending the current planner from the previous solved level.
- If your world model is already good enough, you must try to use `planner` to plan all the way to level completion. You may use `python3 run_main_planner.py --from-current` to try it from the current in-attempt state.
- If level completion is not yet reachable, prefer using a separate planner for intermediate exploration targets. If you do so, you must save it as `level_N_planner_i.py` for future inspection.
- Auxiliary planners may optionally accept `goal`: `planner(state, goal=None)`, where `goal` is a JSON-serializable dictionary describing the requested target.
- The auxiliary planner may share logic with `world_model_main_planner.py`, but it must still plan in terms of the explicit world model.
- After level completion, `world_model_main_planner.py` is a required deliverable and you must verify it with `python3 verify_main_planner.py`. You may also inspect the planner output with `python3 run_main_planner.py --from-initial N`.

Pathfinding or planning done outside the explicit world model is not acceptable.

# Helper programs

Use the following helper programs.

- `client` -- execute chosen in-attempt actions directly in the real game client.
- `python3 verify_world_model.py` — verify the world model for levels `1..current_level` against all recorded attempts. For every attempt, it reconstructs the initial state, simulates the full attempt from that state, and checks the predicted status and rendered settled frame at each simulated step. If `apply_render_overrides(...)` changes a rendered frame, the verifier prints a warning; treat that as unresolved modeling debt and as a likely clue to the puzzle.
- `python3 verify_main_planner.py` — verify the main planner for all completed levels. For each completed level, it reconstructs the initial state, runs the planner, and checks with the world model engine that the resulting plan reaches `LEVEL_COMPLETED`. It does not verify the current level unless that level has already been completed.
- `python3 run_main_planner.py --from-current`, `python3 run_main_planner.py --from-initial N`, or `python3 run_main_planner.py --from-attempt N A S` — run the main planner and print the resulting action sequence. `--from-current` plans from the latest known state of the current level. `--from-initial N` plans from the initial state of level `N`. `--from-attempt N A S` plans from the state obtained by reconstructing the initial state and simulating the first `S` steps of attempt `A` on level `N`.
- `python3 run_aux_planner.py planner_module_name --from-current`, `python3 run_aux_planner.py planner_module_name --from-initial N`, or `python3 run_aux_planner.py planner_module_name --from-attempt N A S` — run an auxiliary planner module such as `level_N_planner_i` and print the resulting action sequence. Auxiliary planners must expose a function called `planner`. They may also receive `--goal 'JSON'`, which is parsed and passed to the auxiliary planner as `goal`. If you need an exploratory or intermediate target, use a separate planner saved as `level_N_planner_i.py`, and run it with `python3 run_aux_planner.py ...`.

## Useful Python helpers

You may also inspect data or test ideas directly in a Python REPL.

- `from state_reconstruction_tools import reconstruct_initial_state` — reconstruct the initial world-model state for a given level.
- `from state_reconstruction_tools import reconstruct_current_state` — reconstruct the current world-model state from the latest recorded attempt of the current level.
- `from state_reconstruction_tools import reconstruct_state` — reconstruct the world-model state for `level`, `attempt_index`, `step_count`.
- `from state_reconstruction_tools import simulate_actions` — simulate a sequence of actions in the world model from a given state.
- `from frame_plot_lib import save_ascii_frame_png` — render any 2D ASCII-frame `numpy.ndarray` to PNG. It also works for arbitrary subregions or stitched multi-frame panoramas, not just full `64x64` frames.
- `from session_tools import read_all_attempts_for_level` — read all recorded attempts for a level.
- `from session_tools import read_attempt_for_level` — read a specific recorded attempt for a level.
- `from session_tools import read_current_attempt` — read the latest recorded attempt of the current level.

## Useful Python libraries

Incorporate Python libraries like NumPy, SciPy, Sympy and NetworkX when they help your world model or planners.

# Verification

After each modification to the executable world model, you should run both verifiers:

- `python3 verify_world_model.py`
- `python3 verify_main_planner.py`

# Notes

Keep `world_model.md` clear enough that you can understand what the model predicts, why you believe it, what objective you are pursuing, and what observations remain unresolved.

Keep `level_N_reasoning_log.md` brief but concrete.

After each level, write `level_N_report.md` with the main actions, useful clues, difficult observations, false hypotheses, and final model shape.

