# Results on ARC-3 Public Games for `secure_baseline_v1.5 agent`

Evaluation on the public [ARC-AGI-3](https://arcprize.org/arc-agi/3) games.

## Setup

- The agent plays each game from scratch (no cross-game learning).
- The agent cannot return to previously solved levels (`GAME_RESET` is forbidden).
- Each run is a single playthrough of a game.
- The agent is stopped after performing 1,500 moves on the current level. Any actions performed after `GAME_OVER` without calling `RESET level` also count toward this limit.


# Failure-handling policy

To avoid selection bias, any run interrupted by a technical failure or by reaching the Codex usage limit would be reported as interrupted and would not be restarted. Restarting such runs would also violate the single-playthrough evaluation protocol.

This policy is important because interruptions are not necessarily independent of agent performance. Runs in which the agent struggles and obtains a lower score generally take longer than runs in which it quickly finds a good solution. They therefore have more opportunity to encounter a technical failure or reach a usage limit. Restarting interrupted runs could consequently discard a disproportionate number of low-scoring trajectories and bias the reported results upward.

For the simulations reported here, we ensured that sufficient resources were available and that no runs were affected by technical failures or usage limits. Therefore, this policy did not need to be applied.

## Results

### GPT-5.5, xhigh reasoning effort, run01

Full runs, including all generated artifacts, are available here: [secure_baseline1_v1.5_gpt5.5_xhigh_run01.tar.gz](https://www.dropbox.com/scl/fi/wy4bcpbr0rdcq1lxzw1hb/secure_baseline1_v1.5_gpt5.5_xhigh_run01.tar.gz?rlkey=m8npt7z3w60h2ig2rxpu7ttpj&st=lt17ano9&dl=0). The agent workspaces are located in the `agent_run` folders; these include the world models created by the agent, which may be interesting to inspect.

| Game | Levels solved | Score | Steps on Solved | Steps on Unsolved | Run Status |
|---|---:|---:|---:|---:|---|
| ar25 | 8/8 | 100.00% | 372 | - | normal termination |
| bp35 | 6/9 | 46.67% | 222 | 1500 | normal termination |
| cd82 | 6/6 | 100.00% | 168 | - | normal termination |
| cn04 | 6/6 | 87.36% | 611 | - | normal termination |
| dc22 | 5/6 | 71.43% | 513 | 1500 | normal termination |
| ft09 | 4/6 | 47.62% | 49 | 1500 | normal termination |
| g50t | 7/7 | 85.86% | 646 | - | normal termination |
| ka59 | 7/7 | 100.00% | 386 | - | normal termination |
| lf52 | 10/10 | 90.36% | 1766 | - | normal termination |
| lp85 | 8/8 | 100.00% | 104 | - | normal termination |
| ls20 | 7/7 | 98.62% | 778 | - | normal termination |
| m0r0 | 6/6 | 100.00% | 245 | - | normal termination |
| r11l | 6/6 | 82.49% | 525 | - | normal termination |
| re86 | 8/8 | 100.00% | 597 | - | normal termination |
| s5i5 | 8/8 | 100.00% | 387 | - | normal termination |
| sb26 | 8/8 | 100.00% | 150 | - | normal termination |
| sc25 | 6/6 | 72.82% | 441 | - | normal termination |
| sk48 | 8/8 | 81.94% | 1165 | - | normal termination |
| sp80 | 5/6 | 54.97% | 1120 | 1500 | normal termination |
| su15 | 9/9 | 29.56% | 715 | - | normal termination |
| tn36 | 7/7 | 90.58% | 292 | - | normal termination |
| tr87 | 6/6 | 100.00% | 241 | - | normal termination |
| tu93 | 9/9 | 99.26% | 259 | - | normal termination |
| vc33 | 7/7 | 66.91% | 746 | - | normal termination |
| wa30 | 7/9 | 43.73% | 930 | 1500 | normal termination |

fully solved games: 20/25
mean per-game RHAE: 82.01%

