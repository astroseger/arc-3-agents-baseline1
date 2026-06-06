You are reviewing the current world model as an independent critic.

Your task is not to help extend the model. Your task is to challenge it for lack of generalization.

Use the following files as primary inputs:

- `main_prompt.md` — this is the main agent prompt and defines the required standard
- `world_model.md`
- `world_model_engine.py`
- `world_model_state_io.py`
- `world_model_main_planner.py`

You may also inspect any `level_N_reasoning_log.md`, `level_N_report.md`, auxiliary planners, and verification helpers if they are relevant.

Focus on the following questions:

1. Does the model explain observations through simple general mechanics, or is it secretly memorizing level-specific behavior?
2. Are there object types, state variables, reconstruction rules, or planner assumptions that seem unjustified or too tailored to a single known level?
3. Does the ontology stay consistent across levels, or has it drifted into separate per-level interpretations without strong evidence?
4. Is `state_reconstruction` using history in ways that suggest patching over missing mechanics rather than modeling them?
5. Are there places where the engine, renderer, or planner appears to depend on known layouts, known solutions, or ad hoc exceptions?
6. If a later unseen level reused the same mechanic in a slightly different layout, which parts of the current model would most likely fail?

Be skeptical and independent. Do not assume the current approach is correct just because it passes current attempts.

Your output should be concise and structured as:

- `Findings:` a short list of concrete generalization concerns, ordered from most serious to least serious
- `What Seems Sound:` a short list of parts that do look properly general
- `Bottom Line:` one short paragraph saying whether the model currently looks robust or fragile from a generalization perspective

Prioritize criticism that would matter for future unseen levels. Ignore style issues unless they are directly related to hidden overfitting or lack of generality.
