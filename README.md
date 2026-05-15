# ARC-AGI-3 baseline1 agent

- We release our baseline1 agent to solve ARC-AGI-3 games. This agent demostrates that LLM-based agents — are capable of building and using computational
world models for complex but low-dimensional and deterministic environments.
- Results on ARC-AGI-3. Results on 25 public games with GPT-5.5/medium reasoning efforts: the score is 52.63%. Agent can fully solve 13/25 games. Our preliminary expirements demostrates that results with GPT-5.5/high reasoning efforts could be singifactly better. We will report as soon as we have them.
- We expect this results to generalise on validation set because (as you can verify by yourself, read `AGENT.md`), our agent doesn't contain any game specifci information, so it expected to be general in ARC-AGI-3 universe. However we cannot rule out that some information about public games has already liked to GPT-5.5 and our agent somehow able to use this information.
- Our agent is reatively cheap to run. one ChatGPT Pro subscription (200 USD) is enough to run a full experiment for roughly 2-8 games (depending how difficult are the games) within the Codex weekly limit for that account.

## Agent
The description and instructions how to run it can be found in baseline1/README.md

## Results on ARC-AGI-3 Public Games

### Baseline1 GPT-5.5 medium reasoning effort

We relese full runs, so you can check world models created by the agent. 

Full table and link to full runs can be found in `baseline1_gpt5.5_medium/README.md`

Summary of results:
- Fully solved games: **13/25 games**
- Mean score, averaging runs within each game first: **52.63%**

### Baseline0.9 GPT-5.4 medium reasoning effort

We also publish here the results of preliminary version of the agent, which we call here baseline0.9 with GPT-5.4 and medium reasoning effort. This baseline1 is a sligtly improvent version of this agent, I've simplified world model interfaces and fixed few bugs in the server/client. I don't know yet how these changes influence performance, however it is still not the same agent as baseline1, so the difference between baseline1 with GPT-5.5 is not only the base LLM model. However I believe most of difference is basecuse base LLM model, but this need to be verified.

We keep this results here, because they been used for the first version of our article publised on arxiv.

Full table and link to full runs can be found in `baseline1_gpt5.4_medium/README.md`

Summary of results:
- Fully solved : **7/25 games**
- Mean score, averaging runs within each game first: **34.69%**

-------

-->  Put somewhere a reminder to cite our article


