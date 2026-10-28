# ARC-AGI-3 General Agents

> [!NOTE]
> **New project: [EnvTraverse](https://github.com/astroseger/envtraverse).**
> See our latest work on environment-agnostic agents and the accompanying papers,
> code, and experiment results.

This repository is the project page for our experiments with coding agents designed to be game-general within ARC-AGI-3. We develop and evaluate agent architectures, reasoning strategies, and tools for solving unfamiliar interactive games.

## General-agent setting

The agents contain no game-specific code, prompts, hand-coded heuristics, hidden solutions, or other game-specific information. The same agent code and prompts are used across games.

Each game is evaluated as a single recorded playthrough from a fresh workspace. The agent has no access to files, logs, or conversation state from previous playthroughs. It cannot restart the game or return to completed levels.

## Public-game saturation

With GPT-5.6-sol, `ewma_sv_v1.6` fully solved all 25 public games at both tested reasoning efforts, achieved about 99% mean per-game Relative Human Action Efficiency (RHAE), and used fewer than half as many environment actions as the human baseline.

Because GPT-5.6-sol postdates the public games and held-out performance has not been tested, we interpret this as saturation of the public set—not evidence that ARC-AGI-3 has been solved generally.

## Recommended agents

For new experiments, consider:

- [`ewma_sv_v1.6`](papers/paper02/agents/ewma_sv_v1.6): maintains and simplifies a fixed-interface executable world model and verifies it through exact replay of recorded observations. It gives the strongest public-game results but is relatively expensive to run.
- [`twma_v1.6`](papers/paper02/agents/twma_v1.6): maintains a textual world model without requiring a persistent executable simulator or replay-verification stack. It is much simpler and less expensive while still achieving strong results.
  The updated [`twma_v1.61`](https://github.com/astroseger/envtraverse/tree/main/papers/paper03/twma_v1.61/) in EnvTraverse uses a newer Codex version supporting GPT-6-astra.

For environment-agnostic agents that can work across different environments, see our [EnvTraverse project](https://github.com/astroseger/envtraverse).

## Papers and supporting materials

- [Executable World Models for ARC-AGI-3 in the Era of Coding Agents](https://arxiv.org/abs/2605.05138) — [supporting materials](papers/paper01/)
- [Do Coding Agents Need Executable World Models, Simplification, and Verification to Solve ARC-AGI-3?](http://arxiv.org/abs/2607.15439) — [supporting materials](papers/paper02/)
- [Improving Environment-Agnostic Coding Agents: The Role of Scaffolding](https://arxiv.org/abs/2610.22289) — [supporting materials](https://github.com/astroseger/envtraverse/tree/main/papers/paper03/)
- Can Environment-Agnostic Agents Solve ARC-AGI-3 from Warped and Noisy Images? — [supporting materials](https://github.com/astroseger/envtraverse/tree/main/papers/paper04/) (arXiv link coming soon, [temporary Google Drive link](https://drive.google.com/file/d/1kD4KvfYtYykf_auaQtKzwN4SK8R-CntV/view?usp=sharing))

## Citation

If you use this repository or the released results, please cite the relevant paper.

## License

Released under the [MIT License](LICENSE).
