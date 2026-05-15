# Agent

Our agent is based on unsandboxed Codex. In principle, this means the Codex process can read any file that exists inside its runtime environment. Because of that, we treat the filesystem visible to the agent as part of the task definition: it must not contain hidden game implementation, previous run state, or any information that would let the agent cheat instead of learning from client observations.

- We run the agent in an isolated Docker container.
- We isolate it from the `arc_agi` library through a client/server boundary. The server that uses `arc_agi` runs in a separate Docker container.
- Before each new agent run, we remove previous Codex account state except for required authentication data such as `auth.json`.
- The `src/agent` folder contains all information available to the agent.

# Contents of `src/agent`

`agent.py` is the external controller. It prepares the run directory, starts Codex, sends prompts to Codex, runs the client, inspects progress, and decides which prompt to send next.

The other top-level Python files are helper libraries and debugging tools used by `agent.py`: running Codex, reading session status, logging prompts, taking git snapshots, etc.

`prompts/` contains the prompts that `agent.py` sends to Codex during the run.

`workspace_init/` is the initial workspace for the agent. We copy it into `agent_run/` before starting Codex.

For a more agent-facing explanation of these files, read `prompts/main_prompt.md`. It describes the provided tools and expected deliverables in the same terms Codex sees during a run.

## World model stubs provided to the agent

- `world_model_engine.py` - world dynamics model stub.
- `world_model_state_io.py` - reconstruction/rendering stub.
- `world_model_main_planner.py` - planner stub.

## Helper programs provided to the agent

- `client/client.py` - live game CLI: start, move, status, stop.
- `client/ascii_to_png.py` - ASCII frame to PNG converter.
- `verify_world_model.py` - checks world-model predictions against recorded attempts.
- `verify_main_planner.py` - checks planner success on completed levels.
- `run_main_planner.py` - runs the main planner.
- `run_aux_planner.py` - runs auxiliary planners.
- `plan_executor.py` - executes planned actions in both game and model.
- `plot_initial_full_frames.py` - renders reconstructed full-frame maps.
- `generate_animation_analysis_prompt.py` - creates animation-analysis prompts.

## Helper libraries provided to the agent

- `session_tools.py` - reads sessions, attempts, frames, and metadata.
- `state_reconstruction_tools.py` - reconstructs and simulates world-model states.
- `frame_plot_lib.py` - renders frames and mismatch visualizations.
- `mismatch_artifacts.py` - saves mismatch/debug artifacts.
- `load_initial_full_frame.py` - loads reconstructed full-frame maps.
- `script_tools.py` - shared CLI/planner helper functions.
- `timeout_tools.py` - timeout context manager.
- `game_status.py` - shared status constants.
