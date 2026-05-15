# Source code of BASELINE1 agent with docker based automation

## Introduction

Source code of baseline1 agent with docker based automation. To run this agent your will need
- linux machine with installed docker
- arc api key setup in environment as `ARC_API_KEY`
- ChatGPT PRO subsciption. With one subscirption you will be able to run 2-6 games with a weekly limit

Warning the current system is lack mechanisms of recovering from fatal error in codex. The possible errors are
- Sometime codex crush with "model at model capacity limits" error. Which happens twice for a month for me. 
- You hit you 5 hours or weekly limit in codex. Based on my expirience, with a single chatGPT PRO (200$) subscrition you can safely run two games in parallel without hitting 5 hours limit 

## System requirments 
You need 1 better 2 moder fast CPUs for one game. You also need ~3 GB of memory for one game. So if you run all 25 games in parallel you better have 48CPU/64GB RAM. But for running 2 games in parallel almost any modern machine would be ok.

## How to run the system

### Setup your codex accounts
Based on my expirience with GPT-5.5/medium as based model, you can run two games in parallel with a single ChatGPT PRO subscription without hitting 5 hour limit. So we will create two codex folders two run two games in parallel



1. Build the dockers `./src/build_dockers.sh`
2. setup codex01: `cd codex_accounts; ./prepare_account.sh codex01` .  Follow instruction to authenticate codex with device authentication with your ChatGPT PRO subsciption
4. (optional) check that codex account setup properly by running `cd codex_accounts; check_account.sh codex01`
5. (optional) setup codex02: `cd codex_accounts; ./prepare_account.sh codex02`. Follow instructions to authenticate codex with device authentication with the same ChatGPT PRO subsciption
6. (optional) check that codex account setup properly by running `cd codex_accounts; check_account.sh codex02`


You all setup two run expirements

### Run expiriments

1. Edit list of codex account folders in run_config.yaml if you used different folder names (by default it is [codex01, codex02] to run two games in paramme) 
2. Edit list of games you want to run in `run_config.yaml`. You can put more games then number of codex account folders you have. They will be run sequentially two in parallel.
3. Run the system (better do it in the screen for example becaues runs could take some time).
```
# better in screen or tmux!
python3 run_controller.py
```
By default controller will be run in local model (not in competition mode), so your will generate scorecards by running `analyse_runs.py`

## Scripts for analysis of expirements

In `analysis_scripts` there are several usefull script for analsis.

- count_level_attempts_dirs.py usefull for traking progress of the agent during the run
run:
`python3 analysis_scripts/count_level_attempts_dirs.py run`

- `analyse_runs.py` to calculate scores
`python3 analysis_scripts/analyse_runs.py run`
- `print_results_md.py` to print scores in a table (you should run it after `analyse_runs.py`)
`python3 print_results_md.py run`
- `summarize_agent_logs_in_dir.py` function to analyse logs
- `get_comptetiotion_scorecard_from_id.sh` - to download you competition card usufull if you run the system in competition mode

## Running in competition mode
If you want you can run the system in competition mode by passing --competition parameter to the `python3 run_controller.py`. However there are few warning.
1. Competition scorecard is closed after 15 min of incativity (on practive this number seems to be bigger). The agent can easily take more then 15 minutes on simplification stage (in some cases more then hour, when GPT-5.5 is busy and codex is slow). So this mode is suitable only for massive parallel runs, or we need somehow remove this inactivity limit
2. Competition scorecard will be closed after 24 hours. So if run takes long. Even individual game can take more then 24 hours to complete, in some cases even more. Also you might not have enought chatGPT subscirptions to run all games in paralle. In any case you should know about this limit.
