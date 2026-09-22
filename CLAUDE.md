# Claude execution rules

Before changing this repository, read `docs/development-execution-plan.md` in full.

- Work only on the single task named by `current_next` and marked `status: NEXT`.
- Obey that task's allowed paths, forbidden paths, non-goals, acceptance evidence, and
  stop conditions.
- Do not select work from `docs/development-todo.md`; it is a historical investigation log.
- Do not turn a local test into a claim about a real Minecraft run.
- Do not accept the Mojang EULA or run a task that requires that authorization.
- Do not commit or push unless the task packet explicitly delegates that authority.
- If the plan and a more specific contract disagree, stop and report the conflict.
