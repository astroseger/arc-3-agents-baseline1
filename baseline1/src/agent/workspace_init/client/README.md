# Game Agent Brief

## Objective

You are playing an unknown game. Your job is to infer the game rules from interaction, complete as many levels as possible, and reach the win condition efficiently.

These games are interactive grid-based environments. You do not receive an explicit symbolic rule description. Instead, you must learn the rules by observing the returned frames and metadata after each action.

## Environment Structure

- A game consists of one or more levels.
- Levels usually get harder or add complications as you progress.
- `levels_completed` is the cumulative number of finished levels in the current run.
- `win_levels` is the number of completed levels required to win the whole game.
- A useful derived quantity is:
  - current level is usually `levels_completed + 1` while the state is still in progress.

## What You Observe After Each Step

After every action, the environment returns:

- one or more frames
- current state
- `levels_completed`
- `win_levels`
- `available_actions`
- the echoed `action_input` that produced the response

Important details:

- A frame is a `64 x 64` grid of integers `0..15`.
- These integers are color/state indices, not natural-language labels.
- Multiple frames may be returned for a single action if the environment internally advances through animation or short transitions before settling.

## State Semantics

Possible states:

- `NOT_FINISHED`: the game is active and waiting for the next action.
- `WIN`: the run has ended successfully.
- `GAME_OVER`: the run has ended in failure.

Practical rule:

- If the state is `GAME_OVER`, do not continue probing ordinary actions. You must stop and ask for another attempt.

## Actions

The environment defines a standardized action interface:

- `ACTION1`: usually semantically aligned with `up`.
- `ACTION2`: usually semantically aligned with `down`.
- `ACTION3`: usually semantically aligned with `left`.
- `ACTION4`: usually semantically aligned with `right`.
- `ACTION5`: a game-specific simple interaction such as use, select, rotate, attach, detach, confirm, or execute.
- `ACTION6`: a coordinate-based action requiring explicit `x, y`.
- `ACTION7`: usually undo.

Important nuance:

- The action semantics are standardized only loosely.
- `ACTION1-4` are direction-like, but their exact in-game meaning can still vary by title.
- `ACTION5` is intentionally game-specific.
- `ACTION6` only tells you that coordinate-based interaction exists; it does not tell you which coordinates are meaningful.

## Available Actions

Do not assume the action set is fixed.

- `available_actions` can change during play.
- Re-read `available_actions` after every step.
- Only choose from the currently valid actions.

This matters because:

- some games support only a subset of actions at all
- some games enable or disable actions depending on current state
- some games expose `ACTION6` only in situations where clicking is meaningful

## How To Think About The Task

Treat each game as a small hidden-rule system.

Recommended strategy:

- Start with cheap probing actions to identify movement, interaction, hazards, and reward signals.
- Use short experiments to test hypotheses.
- Compare before/after frames carefully.
- Track what changes in response to each action.
- Reuse knowledge across levels, but expect later levels to add constraints or complexity.
- Prefer systematic exploration over random flailing.
- If `ACTION6` is available, reason spatially about candidate target locations.
- If `ACTION7` is available, use it to test risky hypotheses more safely.

## What Information Is Worth Keeping In Memory

The agent should keep a compact internal memory of:

- current level estimate
- current objective hypothesis
- known movement semantics
- effects of `ACTION5`
- whether `ACTION6` seems to interact with objects, tiles, or UI-like targets
- any hazards, enemies, timers, energy systems, or delayed consequences
- which experiments failed and should not be repeated

Useful comparisons:

- difference between consecutive frames
- whether an action changes only the agent position or also the world state
- whether a level transition happened
- whether the game punishes delay, repetition, or wrong-order actions

## Coordinate Conventions

For coordinate actions:

- coordinates use `(x, y)`
- origin is at the top-left
- valid range is typically `0..63` for both axes

If you use `ACTION6`, provide both `x` and `y`.

## What To Avoid

- Do not assume all games use all seven actions.
- Do not assume the meaning of `ACTION5` from one game transfers directly to another.
- Do not assume `available_actions` stays constant.
- Do not ignore multi-frame outputs; transitions may be visible in later returned frames.
- Do not continue sending ordinary actions after `GAME_OVER`.

## Using Our CLI Client

Assumption:

- the local server is already running

Take one action:

```bash
python3 client.py move ACTION1  # usual semantics: up
python3 client.py move ACTION2  # usual semantics: down
python3 client.py move ACTION3  # usual semantics: left
python3 client.py move ACTION4  # usual semantics: right
python3 client.py move ACTION5  # usual semantics: primary interaction
python3 client.py move ACTION6 --x 12 --y 34  # usual semantics: coordinate action
python3 client.py move ACTION7  # usual semantics: undo
```

Inspect current state:

```bash
python3 client.py status
```

## What The Client Prints

After each command, the client prints a short summary including:

- step number
- current state
- level summary
- action just taken
- `available_actions_next`
- the files created for that step

The artifacts are written under:

```text
session/
```

Within a session, the client creates one folder per level attempt:

```text
session/level_<LEVEL>_attempt_<ATTEMPT>/
```

Each attempt folder contains:

- `initial_metadata.json`
- `initial_frame.png`
- `initial_frame.txt`

`initial_*` is the settled observation before any real action in that attempt. The first real action result is stored as `step_0001_*`.

For each real action step in that attempt, the client writes:

- compact metadata JSON
- the final settled frame as PNG and ASCII
- zero or more intermediate animation frames as PNG and ASCII

## Minimal Operating Rule For The Agent

At every step:

1. Read the returned frame(s) and metadata.
2. Update your hypothesis about the rules and objective.
3. Re-check `available_actions`.
4. If the game is `GAME_OVER`, stop and ask for another attempt.
5. Otherwise choose the next action based on the simplest high-value experiment or progress move.
