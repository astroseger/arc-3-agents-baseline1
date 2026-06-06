# Results on ARC-3 Public Games

Evaluation on the public [ARC-AGI-3](https://arcprize.org/arc-agi/3) games.

## Setup

- agent baseline1, base LLM GPT-5.5 with high reasoning effort.
- The agent plays each game from scratch (no cross-game learning).
- The agent cannot return to previously solved levels (`GAME_RESET` is forbidden).
- Each run is a single playthrough of a game.

## Interruption Policy
As described in the article, some runs where interrupted because of techical failures or 
simply because of hitting Codex usage limits on the OpenAI
subscription used for the experiment. We report these runs as interrupted
and do not restart them. Restarting after an interruption would conflict with the
single-playthrough evaluation protocol. It would also introduce a
selection bias. For the same game, runs in which the agent struggles and
obtains a lower score usually take longer than runs in which it finds a
good solution quickly. Longer runs have more opportunity to encounter a
technical interruption or hit a Codex usage limit. Restarting after
such failures would therefore preferentially discard some low-scoring
trajectories.

## Results

### GPT-5.5, high reasoning effort, run01

Full runs, including all generated artifacts, are available here: [secure_baseline1_gpt5.5_high_run01.tar.gz](https://www.dropbox.com/scl/fi/usq1imwtbpx8hus5bhybv/secure_baseline1_gpt5.5_high_run01.tar.gz?rlkey=a5ivu028f55ophyyl5wq027ss&st=qyctmpps&dl=0). The agent workspaces are located in the `agent_run` folders; these include the world models created by the agent, which may be interesting to inspect.

| Game | Levels solved | Score | Steps on Solved | Steps on Unsolved | Run Status |
|---|---:|---:|---:|---:|---|
| ar25 | 8/8 | 100.00% | 307 | - | normal termination |
| bp35 | 5/9 | 4.43% | 1195 | 1340 | interrupted |
| cd82 | 6/6 | 92.91% | 170 | - | normal termination |
| cn04 | 6/6 | 96.34% | 715 | - | normal termination |
| dc22 | 0/6 | 0.00% | 0 | 1586 | normal termination |
| ft09 | 6/6 | 57.80% | 474 | - | normal termination |
| g50t | 7/7 | 95.08% | 556 | - | normal termination |
| ka59 | 7/7 | 100.00% | 541 | - | normal termination |
| lf52 | 6/10 | 35.48% | 632 | 1580 | normal termination |
| lp85 | 8/8 | 100.00% | 190 | - | normal termination |
| ls20 | 7/7 | 57.02% | 1600 | - | normal termination |
| m0r0 | 6/6 | 67.33% | 2441 | - | normal termination |
| r11l | 6/6 | 89.29% | 182 | - | normal termination |
| re86 | 5/8 | 40.10% | 423 | 272 | interrupted |
| s5i5 | 2/8 | 0.25% | 860 | 18 | interrupted |
| sb26 | 8/8 | 83.78% | 234 | - | normal termination |
| sc25 | 3/6 | 20.23% | 92 | 347 | interrupted |
| sk48 | 7/8 | 11.26% | 3496 | 0 | interrupted |
| sp80 | 4/6 | 39.21% | 178 | 195 | interrupted |
| su15 | 9/9 | 56.85% | 736 | - | normal termination |
| tn36 | 7/7 | 74.98% | 606 | - | normal termination |
| tr87 | 6/6 | 100.00% | 416 | - | normal termination |
| tu93 | 9/9 | 100.00% | 266 | - | normal termination |
| vc33 | 3/7 | 21.43% | 61 | 1325 | interrupted |
| wa30 | 4/9 | 9.11% | 1186 | 1511 | normal termination |

fully solved games: **15/25**
mean per-game RHAE: **58.12%**

### GPT-5.4, high reasoning effort, run01

Full runs, including all generated artifacts, are available here: [secure_baseline1_gpt5.4_high_run01.tar.gz](https://www.dropbox.com/scl/fi/1c4w0rhhivcmg78kp2ux2/secure_baseline1_gpt5.4_high_run01.tar.gz?rlkey=dze4vhkiumb0aa21z3u9hyjaa&st=5h4ci6z2&dl=0). The agent workspaces are located in the `agent_run` folders; these include the world models created by the agent, which may be interesting to inspect.

| Game | Levels solved | Score | Steps on Solved | Steps on Unsolved | Run Status |
|---|---:|---:|---:|---:|---|
| ar25 | 8/8 | 92.80% | 521 | - | normal termination |
| bp35 | 3/9 | 2.73% | 481 | 1199 | interrupted |
| cd82 | 6/6 | 100.00% | 147 | - | normal termination |
| cn04 | 1/6 | 0.33% | 111 | 1514 | normal termination |
| dc22 | 4/6 | 36.84% | 1568 | 715 | interrupted |
| ft09 | 6/6 | 100.00% | 109 | - | normal termination |
| g50t | 6/7 | 59.25% | 860 | 785 | interrupted |
| ka59 | 6/7 | 9.29% | 2220 | 161 | interrupted |
| lf52 | 1/10 | 1.82% | 10 | 1511 | normal termination |
| lp85 | 8/8 | 100.00% | 110 | - | normal termination |
| ls20 | 7/7 | 77.26% | 804 | - | normal termination |
| m0r0 | 1/6 | 0.01% | 790 | 1519 | normal termination |
| r11l | 4/6 | 18.45% | 693 | 502 | interrupted |
| re86 | 4/8 | 27.78% | 187 | 1390 | interrupted |
| s5i5 | 5/8 | 41.67% | 297 | 423 | interrupted |
| sb26 | 8/8 | 73.87% | 234 | - | normal termination |
| sc25 | 3/6 | 16.71% | 1059 | 740 | interrupted |
| sk48 | 1/8 | 2.78% | 30 | 1163 | interrupted |
| sp80 | 1/6 | 4.76% | 39 | 1479 | interrupted |
| su15 | 1/9 | 1.72% | 25 | 1582 | normal termination |
| tn36 | 1/7 | 3.57% | 11 | 1549 | normal termination |
| tr87 | 6/6 | 100.00% | 240 | - | normal termination |
| tu93 | 9/9 | 100.00% | 191 | - | normal termination |
| vc33 | 3/7 | 10.73% | 132 | 1529 | normal termination |
| wa30 | 7/9 | 49.77% | 1290 | 919 | interrupted |

fully solved games: **8/25**
mean per-game RHAE: **41.29%**

