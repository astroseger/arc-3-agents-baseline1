# `twma_v1.2`

This directory contains the v1.2 textual-world-model agent and the Docker automation used to run it. See [AGENT.md](AGENT.md) for its implementation and [the parent README](../README.md) for the complete agent family and analysis utilities.

## Variant

- `world_model.md` is the persistent environment hypothesis; no executable simulator or planner is required.
- Scheduled simplification and exact replay verification are disabled.
- The Docker image installs Codex CLI `0.128.0`.

## Default run

`run_config.yaml` selects all 25 public games, four Codex account directories (`codex01` through `codex04`), and `gpt-5.5` with `xhigh` reasoning effort. Edit it before launching if you want another model, effort, game subset, or account layout.

## Requirements

- Linux with Docker;
- an ARC API key in `ARC_API_KEY`;
- authenticated Codex account directories, or `OPENAI_API_KEY` for the API-key controller.

## System Requirements

For one game, expect to need about 1-2 moderately fast CPU cores and about 3 GB of memory.

For 25 games in parallel, a reasonable target is about 48 CPU cores and 64 GB RAM. For four games in parallel, a modern workstation is generally sufficient.

## How to Run the System

### Set up Codex accounts

Build the Docker images:

```bash
./src/build_dockers.sh
```

The default configuration uses four account folders. Create and authenticate each one:

```bash
cd codex_accounts
./prepare_account.sh codex01
./prepare_account.sh codex02
./prepare_account.sh codex03
./prepare_account.sh codex04
```

Follow the device-auth instructions for each command. You can verify an account with `./check_account.sh codex01` and the analogous command for the others. Return to the package root with `cd ..` before continuing.

### Run experiments

1. Edit `run_config.yaml`.

   Set `codex_accounts` to the account folders you created, if you used different folder names. Set `games` to the game IDs you want to run. You can list more games than accounts; the controller runs up to one game per account in parallel and queues the rest.

2. Make sure `ARC_API_KEY` is set:

```bash
export ARC_API_KEY=...
```

3. Start the controller, preferably inside `screen` or `tmux` because runs can take a long time:

```bash
python3 run_controller.py
```

By default, `run_controller.py` uses the local server mode, not competition mode. Results are written under `run/`. The controller expects `run/` not to exist before it starts.

Analysis utilities now live in [`../analysis_scripts`](../analysis_scripts) and are documented in [`../README.md`](../README.md).

## Running in Competition Mode

To run against the competition server, pass `--competition`:

```bash
python3 run_controller.py --competition
```

There are two important caveats:

1. A competition scorecard can be closed after a period of inactivity, while an agent may spend substantial time reasoning between environment actions. Competition mode is therefore better suited to sufficiently parallel runs.

2. A competition scorecard closes after 24 hours. Some individual games can take more than 24 hours, and you may not have enough ChatGPT Pro subscriptions to run all games in parallel.

## API-Key Controller

There is also `run_controller_with_api_key.py`, which runs Codex with `OPENAI_API_KEY` instead of authenticated Codex account folders.

API-key runs may be substantially more expensive than runs backed by authenticated Codex accounts. The script prints a warning and requires explicit confirmation before it starts.
