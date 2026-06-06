# Results on ARC-3 Public Games (GPT-5.4/medium)

Evaluation on the public [ARC-AGI-3](https://arcprize.org/arc-agi/3) games.

## Setup

- agent baseline0.9, base LLM GPT-5.4 with medium reasoning effort.
- The agent plays each game from scratch (no cross-game learning).
- The agent cannot return to previously solved levels (`GAME_RESET` is forbidden).
- Each run is a single playthrough of a game.

## Interruption Policy
This is the first, experimental version of our agent, and it lacks proper interruption handling. Some runs were terminated early due to technical issues (e.g., model capacity limits), and we report these runs as-is without continuation.

We deliberately do not resume such runs manually. Doing so would introduce variability depending on the number and timing of interruptions, which would make the results less fair and less reproducible. In this sense, interruption handling is considered part of the agent itself.

## Results

Full runs, including all generated artifacts, are available here: [baseline0.9_gpt5.4_medium.tar.gz](https://www.dropbox.com/scl/fi/hnnild1cg15s2mo5g82yb/baseline0.9_gpt5.4_medium.tar.gz?rlkey=1nqfohxk0a8lmxfxpnpdjwm9s&st=jccd4k66&dl=0). The agent workspaces are located in the `agent_run` folders; these include the world models created by the agent, which may be interesting to inspect.

| Game | Run index | Levels solved | RHAE Score | Status |
|---|---:|---:|---:|---|
| ar25 | 01 | 8/8 | 100.00% | completed |
| bp35 | 01 | 1/9 | 0.61% | completed |
| cd82 | 01 | 6/6 | 99.37% | completed |
| cn04 | 01 | 5/6 | 71.43% | interrupted (1041 steps) |
| cn04 | 02 | 1/6 | 0.01% | interrupted (1998 steps) |
| dc22 | 01 | 4/6 | 26.03% | interrupted (632 steps) |
| dc22 | 02 | 4/6 | 38.52% | interrupted (2156 steps) |
| ft09 | 01 | 6/6 | 58.29% | completed |
| g50t | 01 | 3/7 | 21.43% | interrupted (318 steps) |
| g50t | 02 | 4/7 | 35.71% | completed |
| ka59 | 01 | 0/7 | 0.00% | interrupted (481 steps) |
| ka59 | 02 | 1/7 | 0.01% | completed |
| lf52 | 01 | 4/10 | 15.95% | interrupted (713 steps) |
| lp85 | 01 | 8/8 | 100.00% | completed |
| ls20 | 01 | 6/7 | 30.33% | interrupted (2846 steps) |
| m0r0 | 01 | 1/6 | 1.05% | completed |
| r11l | 01 | 2/6 | 14.29% | completed |
| re86 | 01 | 6/8 | 36.15% | interrupted (1644 steps) |
| s5i5 | 01 | 5/8 | 9.05% | interrupted (2495 steps) |
| sb26 | 01 | 8/8 | 100.00% | completed |
| sc25 | 01 | 0/6 | 0.00% | interrupted (708 steps) |
| sk48 | 01 | 2/8 | 0.75% | completed |
| sp80 | 01 | 1/6 | 4.76% | interrupted (305 steps) |
| su15 | 01 | 2/9 | 3.58% | completed |
| tn36 | 01 | 1/7 | 0.01% | completed |
| tr87 | 01 | 6/6 | 100.00% | completed |
| tu93 | 01 | 9/9 | 86.86% | completed |
| vc33 | 01 | 2/7 | 9.66% | completed |
| wa30 | 01 | 0/9 | 0.00% | completed |


## Summary
- Fully solved (all levels solved): **7 games**
- Near human performance (RHAE > 75%): **6 games**
- Total failure (RHAE < 5%): **9 games** (plus 1/2 failed attempt for cn04)
- Mean score, averaging runs within each game first: **34.69%**

Note: This number differs slightly from the one reported in the first version of our article because that version used the old RHAE score calculation protocol, which was later updated by the ARC Prize team.

## Discussion

The agent demonstrates strong performance on a subset of games, including multiple perfect solutions and several high-performing partial runs.

