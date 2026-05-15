# Results on ARC-3 Public Games

Evaluation on the public [ARC-AGI-3](https://arcprize.org/arc-agi/3) games.

## Setup

- agent baseline1, base LLM GPT-5.5 with medium reasoning effort.
- The agent plays each game from scratch (no cross-game learning).
- The agent cannot return to previously solved levels (`GAME_RESET` is forbidden).
- Each run is a single playthrough of a game.
- When multiple runs are reported for the same game, they are independent runs.

## Interruption Policy

This is the first, experimental version of our agent, and it lacks proper interruption handling. Some runs were terminated early due to technical issues (e.g., model capacity limits), and we report these runs as-is without continuation.

We deliberately do not resume such runs manually. Doing so would introduce variability depending on the number and timing of interruptions, which would make the results less fair and less reproducible. In this sense, interruption handling is considered part of the agent itself.

## Results

Full runs, including all generated artifacts, are available here: [baseline1_gpt5.5_medium.tar.gz](https://www.dropbox.com/scl/fi/oznnhic9ovxzvz5062r6b/baseline1_gpt5.5_medium.tar.gz?rlkey=o2hiam2zcmpzv1usvvr46thq6&st=c581comd&dl=0). The agent workspaces are located in the `agent_run` folders; these include the world models created by the agent, which may be interesting to inspect.


| Game | Run index | Levels solved | Score | Steps on Solved | Steps on Last | Run Status |
|---|---:|---:|---:|---:|---:|---|
| ar25 | crun_01 | 8/8 | 100.00% | 483 | 53 | normal termination |
| bp35 | run_02 | 1/9 | 0.96% | 32 | 843 | interrupted |
| cd82 | crun_01 | 6/6 | 72.17% | 520 | 16 | normal termination |
| cn04 | run_01/1 | 6/6 | 61.79% | 1610 | 360 | normal termination |
| cn04 | run_01/2 | 6/6 | 77.38% | 666 | 271 | normal termination |
| cn04 | run_01/3 | 6/6 | 68.18% | 1287 | 84 | normal termination |
| dc22 | run_02 | 6/6 | 100.00% | 938 | 479 | normal termination |
| ft09 | run_01/1 | 6/6 | 75.70% | 447 | 13 | normal termination |
| g50t | run_01/1 | 7/7 | 76.34% | 882 | 73 | normal termination |
| ka59 | run_01/1 | 6/7 | 35.43% | 846 | 316 | interrupted |
| lf52 | run_01/1 | 5/10 | 25.66% | 378 | 819 | interrupted |
| lp85 | run_01/1 | 8/8 | 84.89% | 1243 | 1058 | normal termination |
| ls20 | run_01/1 | 7/7 | 71.56% | 1263 | 95 | normal termination |
| m0r0 | run_01/1 | 6/6 | 100.00% | 451 | 82 | normal termination |
| r11l | run_01/1 | 6/6 | 100.00% | 122 | 41 | normal termination |
| re86 | run_01/1 | 2/8 | 8.26% | 66 | 1406 | interrupted |
| s5i5 | run_01/1 | 2/8 | 1.46% | 265 | 254 | interrupted |
| sb26 | crun_01 | 8/8 | 87.65% | 243 | 17 | normal termination |
| sb26 | crun_02_test | 8/8 | 65.61% | 271 | 30 | normal termination |
| sb26 | crun_03_test | 8/8 | 96.79% | 207 | 17 | normal termination |
| sb26 | crun_04_test | 8/8 | 64.47% | 270 | 42 | normal termination |
| sb26 | run_01/1 | 8/8 | 44.06% | 464 | 89 | normal termination |
| sc25 | run_01/1 | 3/6 | 16.89% | 214 | 1009 | interrupted |
| sk48 | run_01/1 | 4/8 | 8.08% | 1407 | 352 | interrupted |
| sp80 | run_01/1 | 5/6 | 35.86% | 795 | 578 | interrupted |
| su15 | run_01/1 | 3/9 | 3.01% | 338 | 1538 | normal termination |
| tn36 | run_01/1 | 4/7 | 21.50% | 572 | 1549 | normal termination |
| tr87 | crun_01 | 6/6 | 63.89% | 1110 | 286 | normal termination |
| tr87 | run_01/1 | 6/6 | 91.96% | 560 | 25 | normal termination |
| tr87 | run_01/2 | 6/6 | 83.15% | 451 | 77 | normal termination |
| tr87 | run_01/3 | 6/6 | 57.12% | 568 | 245 | normal termination |
| tu93 | run_01/1 | 9/9 | 100.00% | 224 | 29 | normal termination |
| vc33 | run_01/1 | 3/7 | 21.43% | 56 | 1529 | normal termination |
| wa30 | run_01/1 | 7/9 | 35.13% | 2212 | 1252 | interrupted |
| wa30 | run_01/2 | 7/9 | 48.15% | 1533 | 398 | interrupted |


## Summary

- Fully solved games: **13 games**
- Total failure (best run score < 5%): **3 games**
- Mean score, averaging runs within each game first: **52.63%**



