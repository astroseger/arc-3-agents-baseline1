# Results on ARC-3 Public Games (GPT-5.5/high)

Evaluation on the public [ARC-AGI-3](https://arcprize.org/arc-agi/3) games.

## Setup

- agent baseline1, base LLM GPT-5.5 with high reasoning effort.
- The agent plays each game from scratch (no cross-game learning).
- The agent cannot return to previously solved levels (`GAME_RESET` is forbidden).
- Each run is a single playthrough of a game.

## Interruption Policy

This is the first, experimental version of our agent, and it lacks proper interruption handling. Some runs were terminated early due to technical issues (e.g., model capacity limits), and we report these runs as-is without continuation.

We deliberately do not resume such runs manually. Doing so would introduce variability depending on the number and timing of interruptions, which would make the results less fair and less reproducible. In this sense, interruption handling is considered part of the agent itself.

## Results

Full runs, including all generated artifacts, are available here: [baseline1_gpt5.5_high.tar.gz](https://www.dropbox.com/scl/fi/0y876g7tddkphod2r108d/baseline1_gpt5.5_high.tar.gz?rlkey=fgyzm5ojbeqdhgm9clbbf6eb2&st=sn0ud5n8&dl=0). The agent workspaces are located in the `agent_run` folders; these include the world models created by the agent, which may be interesting to inspect.


| Game | Run index | Levels solved | Score | Steps on Solved | Steps on Last | Run Status |
|---|---:|---:|---:|---:|---:|---|
| ar25 | run1 | 8/8 | 100.00% | 264 | 47 | normal termination |
| bp35 | run1 | 4/9 | 17.25% | 292 | 50 | interrupted |
| cd82 | run1 | 6/6 | 100.00% | 130 | 16 | normal termination |
| cn04 | run1 | 6/6 | 100.00% | 448 | 60 | normal termination |
| dc22 | run1 | 4/6 | 36.41% | 318 | 1524 | normal termination |
| ft09 | run1 | 6/6 | 95.11% | 157 | 23 | normal termination |
| g50t | run1 | 7/7 | 100.00% | 554 | 71 | normal termination |
| ka59 | run1 | 7/7 | 62.97% | 1099 | 180 | normal termination |
| lf52 | run1 | 6/10 | 34.93% | 598 | 2048 | normal termination |
| lp85 | run1 | 8/8 | 100.00% | 226 | 7 | normal termination |
| ls20 | run1 | 7/7 | 98.31% | 714 | 128 | normal termination |
| m0r0 | run1 | 5/6 | 71.43% | 1054 | 1519 | normal termination |
| r11l | run1 | 6/6 | 74.28% | 227 | 77 | normal termination |
| re86 | run1 | 4/8 | 26.37% | 249 | 1505 | normal termination |
| s5i5 | run1 | 3/8 | 0.68% | 1514 | 1514 | normal termination |
| sb26 | run1 | 8/8 | 100.00% | 150 | 17 | normal termination |
| sc25 | run1 | 3/6 | 20.11% | 88 | 1019 | interrupted |
| sk48 | run1 | 5/8 | 30.16% | 1142 | 1681 | normal termination |
| sp80 | run1 | 1/6 | 4.76% | 6 | 780 | interrupted |
| su15 | run1 | 9/9 | 88.66% | 284 | 19 | normal termination |
| tn36 | run1 | 6/7 | 26.15% | 1460 | 1598 | normal termination |
| tr87 | run1 | 6/6 | 86.35% | 540 | 173 | normal termination |
| tu93 | run1 | 9/9 | 100.00% | 192 | 29 | normal termination |
| vc33 | run1 | 3/7 | 19.43% | 67 | 1529 | normal termination |
| wa30 | run1 | 9/9 | 100.00% | 1495 | 205 | normal termination |

## Summary
- Fully solved games: **14/25**
- Mean per-game RHAE: **63.74%**


