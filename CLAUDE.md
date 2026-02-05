# Claude Instructions

- Don't run servers or start processes automatically
- Never manually edit dependency tracking files (package.json, pyproject.toml, requirements.txt) — always use `npm install <package>` or `uv add <package>` to install dependencies

## Working with agent prompts

- When the user shows examples of failure modes (e.g. from logs), use them to understand the underlying issue - don't copy the specific examples directly into agent prompts
- Extract the general principle/rule from the failure, not the literal example
