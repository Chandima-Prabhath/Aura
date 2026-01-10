# Contributing to Aura

Thank you for your interest in contributing to Aura. We welcome issues and pull requests — please follow the guidelines below to make the review process smooth.

## How to contribute

- Open an issue to report bugs or propose features. Provide a concise description, steps to reproduce, and expected behavior.
- When working on a fix or feature, create a branch named `feat/<short-desc>` or `fix/<short-desc>` based off `main`.
- Open a Pull Request describing the problem, your approach, and any relevant testing steps.

## Code style

- Keep code readable and well-structured. Follow existing project patterns.
- Use descriptive names for functions and variables.
- Avoid large, unrelated changes in a single PR.

## Tests

- Add tests for new features and bug fixes when feasible.
- Run existing tests locally before opening a PR:

```powershell
uv sync
uv run python -m pytest -q
```

## Commits & PRs

- Write clear commit messages. Use imperative mood, e.g. `Add feature X`, `Fix bug Y`.
- Squash minor fixup commits before merging if appropriate.

## Review

- Maintainters will review PRs and may request changes. Respond to feedback promptly.
- After approval, a maintainer will merge the PR.

## Security

If you discover a security issue, please open a private issue or contact the maintainers instead of creating a public disclosure.

## License

By contributing, you agree that your contributions will be licensed under the project's MIT license.
