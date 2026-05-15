# ARC-AGI-3 Baseline1 Agent

This repository releases our `baseline1` agent for ARC-AGI-3 games. The agent demonstrates that LLM-based coding agents can build and use executable world models for complex, low-dimensional, deterministic environments.

The agent does not include hand-coded game-specific logic. It maintains a Python world model, verifies that model against previous observations, refactors it toward simpler abstractions, and uses the model for planning before acting.

## Paper

For more detail, see our arXiv paper:

- [Executable World Models for ARC-AGI-3 in the Era of Coding Agents](https://arxiv.org/abs/2605.05138)

If you use this repository or the released results, please cite the paper.

## Agent

The agent implementation, run instructions, and system requirements are documented in [baseline1/README.md](baseline1/README.md).

To verify that the agent is intended to be game-general within ARC-AGI-3 and does not contain game-specific hidden information, see [baseline1/AGENT.md](baseline1/AGENT.md).

With the default GPT-5.5 medium-reasoning configuration, one ChatGPT Pro subscription (200 USD) is enough to run full experiments for roughly 2-8 games, depending on game difficulty, within the weekly Codex limit for that account.

## Results on ARC-AGI-3 Public Games

### Baseline1: GPT-5.5 Medium Reasoning Effort

We release the full runs so that the generated artifacts and world models can be inspected.

The complete table and links to the full runs are available in [results/baseline1_gpt5.5_medium/README.md](results/baseline1_gpt5.5_medium/README.md).

Summary:

- Fully solved games: **13/25**
- Mean score, averaging runs within each game first: **52.63%**

Preliminary experiments suggest that GPT-5.5 with high reasoning effort may perform significantly better. We will report those results when they are available.

### Baseline0.9: GPT-5.4 Medium Reasoning Effort

We also include results for an earlier preliminary version of the agent, which we call `baseline0.9`. These runs used GPT-5.4 with medium reasoning effort.

`baseline1` is a slightly improved version of this agent: it simplifies the world-model interfaces and fixes several bugs in the server/client code. We have not yet isolated the effect of these changes, so the difference between `baseline0.9` with GPT-5.4 and `baseline1` with GPT-5.5 should not be interpreted as a pure model comparison. We expect most of the difference to come from the base LLM, but this still needs to be verified.

These results are kept here because they were used in the first arXiv version of the paper.

The complete table and links to the full runs are available in [results/baseline0.9_gpt5.4_medium/README.md](results/baseline0.9_gpt5.4_medium/README.md).

Summary:

- Fully solved games: **7/25**
- Mean score, averaging runs within each game first: **34.69%**

## Generalization

We expect the `baseline1` agent to generalize to the validation set because it does not contain game-specific code or game-specific prompts. However, this remains to be tested directly on the private validation set. We also cannot rule out that information about public games is already present in GPT-5.5's training data and that the agent may indirectly benefit from that information.
