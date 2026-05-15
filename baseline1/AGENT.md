# Agent

Our agent is based on unsandboxed codex, so in principle it has access to the whole accesssible file system. It is why we make sure that agent don't have access to any information which he could use to cheat. 

- We run agent in isolated docker contaner. 
- We isolate it from `arc_agi` library by our client/server. We run server with `arc_agi` library in a separate docker container
- We remove all previous information (everything except auth.json) from codex account folder before we run new agent
- Only information which is theoretically accessible by the client is in `src/agent` folder

# Description of Content of `src/agent` folder

agent.py - main "external" controller which run codex and sends to it different prompts 
... library used by agent.py

prompts folder - set of prompts (notion that follower prompts are not used in master mode we currently use, but agent theoreticaly have access to them)

`workspace_init` - initial workspace folder for the agent (we copy it to `agent_run`)

detailed description of each file in `workspace_init` grouped by functions 


