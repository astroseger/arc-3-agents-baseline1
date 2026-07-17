# ARC-AGI-3 agent implementations

This directory contains the runnable agent packages used for the executable-world-model ablations and follow-up systems. It documents agent designs and tooling only; article results are not included here.

## Agents

| Package | World-model treatment | Simplification | Verification | Follow-up changes |
|---|---|---:|---:|---|
| [`twma_v1.2`](twma_v1.2) | Textual model | No | No | — |
| [`ewma_v1.2`](ewma_v1.2) | Flexible-interface executable model and planner | No | No | — |
| [`ewma_s_v1.2`](ewma_s_v1.2) | Flexible-interface executable model and planner | Yes | No | — |
| [`ewma_sv_v1.2`](ewma_sv_v1.2) | Fixed engine, reconstruction/renderer, and planner interfaces | Yes | Exact replay and planner checks | — |
| [`ewma_sv_v1.5`](ewma_sv_v1.5) | Fixed-interface verification treatment | Yes | Yes | Trouble prompts and accelerated client |
| [`twma_v1.6`](twma_v1.6) | Textual model | No | No | Trouble prompts, accelerated client, post-`GAME_OVER` action guard, newer Codex CLI |
| [`ewma_sv_v1.6`](ewma_sv_v1.6) | Fixed-interface verification treatment | Yes | Yes | Same v1.6 harness updates as the textual variant |

Each package contains:

- `README.md`: setup and run instructions;
- `AGENT.md`: treatment-specific architecture;
- `run_config.yaml`: accounts, games, model, effort, and run tag;
- `src/`: controller, prompts, client/server code, Docker files, and any treatment-specific workspace utilities.

All default configurations select the same 25 public games and four Codex account folders. The v1.2 and v1.5 packages default to `gpt-5.5`/`xhigh`; the v1.6 packages default to `gpt-5.6-sol`/`max`.

## Account capacity and parallel runs

As a rough planning estimate, running all 25 games with `twma_v1.2` or `ewma_v1.2` may require 1–2 ChatGPT Pro subscriptions used with Codex to stay within weekly usage limits. The other variants are more compute-intensive and may require 4–5 Pro subscriptions.

You may create two or more Codex account folders authenticated with the same Pro subscription. However, never use the same Codex account folder for two games running in parallel; each concurrent game must use a separate account folder.

Also account for any shorter rolling usage limit, such as the previously applicable five-hour limit. OpenAI's limits may change, so verify the current Codex usage policy before starting a large run.

## Analysis utilities

Shared run-inspection tools are in [`analysis_scripts/`](analysis_scripts):

- `analyse_runs.py` extracts actions and writes scorecard and cost-estimation JSON files;
- `print_results_md.py` and `print_results_md_cost.py` render Markdown summaries;
- `count_level_attempts.py` and `count_level_attempts_dirs.py` inspect progress;
- `summarize_agent_log.py` and `summarize_agent_logs_in_dir.py` summarize logs;
- `extract_actions_from_server_log.py` reconstructs action traces;
- the `print_cost_*.py` tools inspect token-cost estimates;
- `get_comptetiotion_scorecard_from_id.sh` retrieves a competition scorecard.

From this directory, a typical completed local run can be analyzed with:

```bash
python3 analysis_scripts/analyse_runs.py twma_v1.2/run
python3 analysis_scripts/print_results_md.py twma_v1.2/run
```
