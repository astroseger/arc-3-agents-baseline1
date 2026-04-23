# Results on First 10 ARC-3 Public Games

Evaluation on the first 10 [ARC-AGI-3](https://arcprize.org/arc-agi/3) public games.

## Setup

- The agent plays each game from scratch (no cross-game learning).
- The agent cannot return to previously solved levels (`GAME_RESET` is forbidden).
- Each run is a single playthrough of a game.

## Interruption Policy

The agent currently lacks interruption handling. Some runs were terminated early due to technical issues (e.g., model capacity limits), and we report these runs as-is without continuation.

Fully clean handling—ensuring identical execution with or without interruptions—is difficult in the current architecture, while simpler resume strategies would introduce variability depending on the number of interruptions.

## Results

| Game | Run | Levels Solved | Human-Normalized Score | Estimated API Cost | Status |
|------|-----:|--------------:|-----------------------:|------:|--------|
| ar25 | 01 | 8/8 | 100.00% | $76.83 | completed |
| bp35 | 01 | 1/9 | 0.61% | $343.40 | completed |
| cd82 | 01 | 6/6 | 86.51% | $104.68 | completed |
| cn04 | 01 | 5/6 | 62.15% | $258.62 | interrupted (305 steps) |
| cn04 | 02 | 1/6 | 0.01% | $282.34 | interrupted (1998 steps) |
| dc22 | 01 | 4/6 | 24.60% | $313.67 | interrupted (632 steps) |
| dc22 | 02 | 4/6 | 34.23% | $274.62 | interrupted (2156 steps) |
| ft09 | 01 | 6/6 | 51.86% | $68.38 | completed |
| g50t | 01 | 3/7 | 21.43% | $37.07 | interrupted (318 steps) |
| g50t | 02 | 2/7 | 1.24% | $250.34 | interrupted (1841 steps) |
| ka59 | 01 | 0/7 | 0.00% | $42.98 | interrupted (481 steps) |
| ka59 | 02 | 1/7 | 0.01% | $243.81 | interrupted (2194 steps) |
| lf52 | 01 | 4/10 | 14.65% | $248.13 | interrupted (713 steps) |
| lp85 | 01 | 8/8 | 100.00% | $52.93 | completed |

## Summary

- Fully solved: **4 / 10 games**
- Human-level performance (100% HNS): **2 games**
- Partial success: majority of remaining games
- Complete failure: **2 games** (plus 1 failed run on `cn04`)

## Discussion

The agent demonstrates strong performance on a subset of games, including perfect solutions in 4 cases. However, performance varies significantly between runs of the same game (see `cn04` and `g50t`).
Handling interruptions and improving consistency are key next steps.
