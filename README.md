# ARC-AGI-3 Baseline1 Agent
This repository releases our `baseline1` agent for ARC-AGI-3 games. The agent is an LLM-based coding agent that builds an executable Python world model from observations, verifies that model against previous transitions, refactors it toward simpler abstractions, and plans through the model before acting.

The agent does **not** contain game-specific code, game-specific prompts, hand-coded heuristics, hidden solutions, or any other game-specific information. It is designed to be general within the ARC-AGI-3 universe: the same agent and prompts are used across games.

During evaluation, each game is played as a single recorded playthrough. The agent starts from a fresh workspace, sees the target game only once, and has no access to previous playthrough-specific files, logs, or conversation state. It cannot restart the whole game to obtain a better trajectory and cannot return to previously completed levels.

Under these constraints, we believe `baseline1` should be considered eligible for the ARC-AGI-3 main leaderboard. The system is ARC-AGI-3-general rather than game-specific: it is designed for the ARC-AGI-3 interaction setting, but it is not tailored to any individual public game.

## Paper

For more detail, see our arXiv paper:

- [Executable World Models for ARC-AGI-3 in the Era of Coding Agents](https://arxiv.org/abs/2605.05138)

If you use this repository or the released results, please cite the paper.

### Preventing unintended information access

Earlier versions had information-leakage vulnerabilities. For details, see the “Preventing unintended information access” section of the accompanying article.

In our audit of historical runs of the baseline1 agent, we found only one game in which the agent clearly appears to have benefited from such vulnerabilities. In the GPT-5.5-medium run of dc22, the agent appears to have downloaded a public scorecard or related external material. In a few other runs, agents attempted to use web search, but we found no evidence that these attempts produced useful external information.

To avoid mixing vulnerable and fixed evaluations, we discarded all results produced with the older system and did not use them in the article, except when explicitly discussing leakage examples. The old agent, old results, and full run logs remain available for transparency in the [old_vulnerable_version](old_vulnerable_version) folder.

The current version closes the observed leakage channels. The agent container no longer contains the real game name in files, process arguments, environment variables, or API-visible services. It also no longer contains references to ARC or ARC-AGI. The agent container has no general internet access. It can reach OpenAI services only through a separate proxy container whose allowlist is restricted to OpenAI endpoints. Codex web search is disabled.

## Agent

The agent implementation, run instructions, and system requirements are documented in [secure_baseline1/README.md](secure_baseline1/README.md).

To verify that the agent is intended to be game-general within ARC-AGI-3 and does not contain game-specific hidden information, see [secure_baseline1/AGENT.md](secure_baseline1/AGENT.md).

With the default GPT-5.5 high-reasoning configuration, one ChatGPT Pro subscription (200 USD) is enough to run full experiments for roughly 2-8 games, depending on game difficulty, within the weekly Codex limit for that account.

## Results on ARC-AGI-3 Public Games

We release the full runs so that the generated artifacts and world models can be inspected.

The complete table and links to the full runs are available in [results/README.md](results/README.md).

#### GPT-5.5 High Reasoning Effort, run01

fully solved games: **15/25**
mean per-game RHAE: **58.12%**

#### GPT-5.4 High Reasoning Effort, run01

fully solved games: **8/25**
mean per-game RHAE: **41.29%**

## Generalization

We expect `baseline1` to generalize to the private validation set because it does not contain game-specific code, game-specific prompts, hand-coded heuristics, or hidden information about individual games. However, this remains an empirical question that can only be settled by evaluation on the private validation set. We also cannot rule out the possibility that information about the public games is already present in the base LLM's training data and that the agent may indirectly benefit from that information.

## License

This project is released under the MIT License. See [LICENSE](LICENSE) for details.
