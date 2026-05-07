# Results on ARC-AGI-3 Public Games

Evaluation on the public [ARC-AGI-3](https://arcprize.org/arc-agi/3) games.

## Setup

- The agent plays each game from scratch (no cross-game learning).
- The agent cannot return to previously solved levels (`GAME_RESET` is forbidden).
- Each run is a single playthrough of a game.

## Interruption Policy
This is the first, experimental version of our agent, and it lacks proper interruption handling. Some runs were terminated early due to technical issues (e.g., model capacity limits), and we report these runs as-is without continuation.

We deliberately do not resume such runs manually. Doing so would introduce variability depending on the number and timing of interruptions, which would make the results less fair and less reproducible. In this sense, interruption handling is considered part of the agent itself.

## Results

| Game | Run | Levels Solved | RHAE Score | Estimated API Cost | Interruption Status |
|------|-----:|--------------:|-----------------------:|------:|--------|
| ar25 | 01 | 8/8 | 100.00% | $76.83 | completed |
| bp35 | 01 | 1/9 | 0.61% | $343.40 | completed |
| cd82 | 01 | 6/6 | 86.51% | $104.68 | completed |
| cn04 | 01 | 5/6 | 62.15% | $258.62 | interrupted (1041 steps) |
| cn04 | 02 | 1/6 | 0.01% | $282.34 | interrupted (1998 steps) |
| dc22 | 01 | 4/6 | 24.60% | $313.67 | interrupted (632 steps) |
| dc22 | 02 | 4/6 | 34.23% | $274.62 | interrupted (2156 steps) |
| ft09 | 01 | 6/6 | 51.86% | $68.38 | completed |
| g50t | 01 | 3/7 | 21.43% | $37.07 | interrupted (318 steps) |
| g50t | 02 | 4/7 | 34.03% | $339.50 | completed |
| ka59 | 01 | 0/7 | 0.00% | $42.98 | interrupted (481 steps) |
| ka59 | 02 | 1/7 | 0.01% | $243.81 | completed |
| lf52 | 01 | 4/10 | 14.65% | $248.13 | interrupted (713 steps) |
| lp85 | 01 | 8/8 | 100.00% | $52.93 | completed |
| ls20 | 01 | 6/7 | 27.11% | $374.53 | interrupted (2846 steps) |
| m0r0 | 01 | 1/6 | 1.05% | $124.45 | completed |
| r11l | 01 | 2/6 | 14.29% | $224.99 | completed |
| re86 | 01 | 6/8 | 33.23% | $419.86 | interrupted (1644 steps) |
| s5i5 | 01 | 5/8 | 8.21% | $395.20 | interrupted (2495 steps) |
| sb26 | 01 | 8/8 | 92.70% | $34.08 | completed |
| sc25 | 01 | 0/6 | 0.00% | $97.34 | interrupted (708 steps) |
| sk48 | 01 | 2/8 | 0.75% | $620.33 | completed |
| sp80 | 01 | 1/6 | 4.76% | $86.81 | interrupted (305 steps) |
| su15 | 01 | 2/9 | 3.58% | $378.11 | completed |
| tn36 | 01 | 1/7 | 0.01% | $192.04 | completed |
| tr87 | 01 | 6/6 | 100.00% | $44.49 | completed |
| tu93 | 01 | 9/9 | 78.33% | $102.51 | completed |
| vc33 | 01 | 2/7 | 8.59% | $369.47 | completed |
| wa30 | 01 | 0/9 | 0.00% | $88.18 | completed |


## Summary
- Fully solved (all levels solved): **7 games**
- Near human performance (RHAE > 75%): **6 games**
- Total failure (RHAE < 5%): **9 games** (plus 1/2 failed attempt for cn04)

## Discussion

The agent demonstrates strong performance on a subset of games, including multiple perfect solutions and several high-performing partial runs.

