# MedoraAI Documentation

This folder is the shared documentation workspace for the team. Keep documents short, current, and placed in the right section so everyone can find updates quickly.

## Folder Structure

- `planning/` - project scope, requirements, architecture, timelines, and design documents.
- `guides/` - setup steps, workflows, demos, onboarding, and repeatable how-to docs.
- `changelog/` - dated progress updates, release notes, and major project changes.
- `team/` - task tracking, meeting notes, decisions, owners, and collaboration docs.
- `references/` - datasets, research links, external docs, and supporting material.

## Start Here

- Local setup and run commands: `guides/setup.md`
- Model evaluation and hallucination controls: `guides/model-evaluation.md`
- Model artifact notes: `../models/readme.md`
- Training notebook notes: `../notebooks/README.md`
- Main project quick start: `../README.md`

Current app ports:

```text
Frontend: http://127.0.0.1:5173
Backend:  http://127.0.0.1:8000
Health:   http://127.0.0.1:8000/health
```

## Update Rules

- Add dates in `YYYY-MM-DD` format.
- Keep task owners explicit.
- Move outdated drafts to the relevant archive section instead of deleting them.
- Update `team/task-board.md` when work starts, changes owner, or is completed.
- Add major changes to `changelog/CHANGELOG.md`.
