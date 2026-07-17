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
- executable world-model code, including planning code. You may choose the file organization and interfaces.
- `level_N_reasoning_log.md` -- short log of hypotheses, evidence, observations, and model updates during level solving
- `level_N_report.md` -- short report written after solving the level, describing what you did and the final form of the model

# Executable world model

The executable world model should be explicit enough to support planning. You may choose its internal state representation, action representation, algorithms, helper artifacts, and planner design.

The model should help you reason about candidate action sequences, terminal outcomes, and useful plans.

Keep the implementation as simple as you can while preserving useful planning.

# Helper programs

Use the following helper programs.

- `client` -- execute chosen in-attempt actions directly in the real game client.

## Useful Python libraries

Incorporate Python libraries like NumPy, SciPy, Sympy and NetworkX when they help your world model or planners.

# Notes

Keep `world_model.md` clear enough that you can understand what the model predicts, why you believe it, what objective you are pursuing, and what observations remain unresolved.

Keep `level_N_reasoning_log.md` brief but concrete.

After each level, write `level_N_report.md` with the main actions, useful clues, difficult observations, false hypotheses, and final model shape.

