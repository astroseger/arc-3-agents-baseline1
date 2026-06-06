# BASELINE1 Agent Source with Docker Automation

## Introduction

This repository contains the source code for the BASELINE1 agent and the Docker-based automation used to run it.

If you want to check that the agent does not have access to game-specific hidden information and is intended to be general within the ARC-AGI-3 universe, read [AGENT.md](AGENT.md).

To run the system you need:

- a Linux machine with Docker installed;
- an ARC API key available in the environment as `ARC_API_KEY`;
- a ChatGPT Pro subscription.

With the default GPT-5.5/medium configuration, one ChatGPT Pro subscription (200 USD) is enough to run a full experiment for roughly 2-8 games within the Codex weekly limit for that account.

Warning: the current system does not have a graceful recovery mechanism for fatal Codex errors. If a fatal Codex error appears, the agent stops and cannot automatically recover the run. Known failure cases include:

- Codex can occasionally crash with a "model at model capacity limits" error. In my experience, this happened about twice in a month.
- A run can stop when the Codex account reaches its 5-hour or weekly usage limit. In my experience, with a single ChatGPT Pro subscription (200 USD), you can safely run two games in parallel without hitting the 5-hour limit.

## System Requirements

For one game, expect to need about 1-2 moderately fast CPU cores and about 3 GB of memory.

For 25 games in parallel, a reasonable target is about 48 CPU cores and 64 GB RAM. For two games in parallel, almost any modern machine should be enough.

## How to Run the System

### Set up Codex accounts

As mentioned above, you can run two games in parallel with a single ChatGPT Pro subscription (200 USD) without hitting the 5-hour usage limit. To do this, set up two Codex account folders authenticated with the same ChatGPT subscription.

To create and authenticate those accounts:

1. Build the Docker images:

```bash
./src/build_dockers.sh
```

2. Set up the first Codex account:

```bash
cd codex_accounts
./prepare_account.sh codex01
```

Follow the device-auth instructions and authenticate with your ChatGPT Pro subscription.

3. Optionally check the first account:

```bash
cd codex_accounts
./check_account.sh codex01
```

4. Optionally set up a second account for parallel runs:

```bash
cd codex_accounts
./prepare_account.sh codex02
```

5. Optionally check the second account:

```bash
cd codex_accounts
./check_account.sh codex02
```

After this, the system is ready to run experiments.

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

After the run finishes, generate score summaries with the analysis scripts.

## Analysis Scripts

The `analysis_scripts/` directory contains helper scripts for inspecting runs.

- `count_level_attempts_dirs.py` tracks progress from attempt directories:

```bash
python3 analysis_scripts/count_level_attempts_dirs.py run
```

- `analyse_runs.py` calculates scores:

```bash
python3 analysis_scripts/analyse_runs.py run
```

- `print_results_md.py` prints scores as a Markdown table. Run it after `analyse_runs.py`:

```bash
python3 analysis_scripts/print_results_md.py run
```

- `summarize_agent_logs_in_dir.py` summarizes agent logs:

```bash
python3 analysis_scripts/summarize_agent_logs_in_dir.py run
```

- `get_comptetiotion_scorecard_from_id.sh` downloads a competition scorecard by ID when you run in competition mode.

## Running in Competition Mode

To run against the competition server, pass `--competition`:

```bash
python3 run_controller.py --competition
```

There are two important caveats:

1. A competition scorecard can be closed after about 15 minutes of inactivity. In practice the limit may be somewhat longer, but the agent can spend more than 15 minutes in simplification or refactoring prompts, especially when Codex is slow. This makes competition mode better suited to large parallel runs.

2. A competition scorecard closes after 24 hours. Some individual games can take more than 24 hours, and you may not have enough ChatGPT Pro subscriptions to run all games in parallel.

## API-Key Controller

There is also `run_controller_with_api_key.py`, which runs Codex with `OPENAI_API_KEY` instead of authenticated Codex account folders.

This mode is expected to be much more expensive. In earlier testing, prompt-cache hit rates were much lower with API-key runs than with ChatGPT Pro-backed Codex accounts. Because of this, runs that fit within the weekly limit of a single ChatGPT Pro account may cost around 5000 USD if run through the API. The script prints a warning and requires explicit confirmation before it starts.
