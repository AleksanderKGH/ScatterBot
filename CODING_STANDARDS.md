# Coding Standards

These standards keep ScatterBot maintainable and safe while we iterate quickly.

## Core Principles

- Prefer small, focused changes over broad rewrites.
- Keep behavior explicit and predictable.
- Prioritize reliability for Discord commands and JSON data persistence.
- Document user-visible behavior changes.

## Python Style

- Target Python 3.10+ syntax.
- Follow PEP 8 and keep line length near 100 characters.
- Use type hints on new/changed function signatures.
- Keep functions single-purpose and short when practical.
- Avoid single-letter variable names except for very local math/plot loops.
- Use descriptive names for command handlers and service helpers.

## Imports and Dependencies

- Group imports: stdlib, third-party, local modules.
- Avoid unused imports.
- Keep dependencies minimal and justify new packages in the PR description.
- Pin or constrain versions in `requirements.txt` when introducing new dependencies.

## Command and Interaction Patterns

- Route command registration through `command_modules/command_registry.py`.
- Keep Discord interaction responses user-friendly and actionable.
- Validate user input early and return clear error messages.
- Respect channel and role checks for restricted commands.

## Data and Storage

- Treat JSON files as durable state. Changes to schema require migration notes.
- Preserve backward compatibility for existing stored data whenever possible.
- Fail safely on malformed JSON and avoid destructive writes.
- Never commit local runtime data files such as generated backups or points state.

## Configuration and Secrets

- Read required env vars through `config.py` helpers.
- Do not hardcode tokens, IDs, secrets, or guild-specific sensitive values.
- Keep `.env` local only and out of commits.

## Plotting and Rendering

- Keep rendering helpers deterministic for identical input data.
- Preserve existing color/label semantics unless intentionally changed.
- Prefer readability over micro-optimizations unless performance is proven to be an issue.

## Logging and Errors

- Log actions and failures with enough context for debugging.
- Raise or propagate clear exceptions in lower-level helpers.
- Avoid broad bare `except:` blocks; catch specific exceptions.

## Testing and Validation

Before opening a PR, run:

```bash
ruff check .
python -m compileall .
```

For behavior changes, also verify relevant slash commands manually in a test guild.

## Documentation Requirements

- Update `readme.md` for user-facing command, setup, env var, or workflow changes.
- Add migration notes in the PR when JSON shape or behavior changes.
- Include short inline comments only where logic is non-obvious.

## Git and Pull Request Hygiene

- Use clear, scoped commit messages.
- Keep PRs focused on one concern.
- Include testing notes and risk assessment in the PR template.
- Do not mix unrelated refactors with feature/bugfix work.
