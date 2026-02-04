# Claude Instructions

- Don't run servers or start processes automatically
- Always ask the user to run commands themselves
- Install dependencies using `npm install <package_name>` in the appropriate folder, not by editing package.json directly
- For Python dependencies, use `uv add <package_name>` instead of editing requirements.txt directly

## Working with agent prompts

- When the user shows examples of failure modes (e.g. from logs), use them to understand the underlying issue - don't copy the specific examples directly into agent prompts
- Extract the general principle/rule from the failure, not the literal example
