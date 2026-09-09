# Contributing

The canonical skill is `plugins/dex/skills/dex-developer/SKILL.md`. Keep
supporting guidance under its `references/` directory and link each reference
from the skill entrypoint.

## Validate a change

Run the repository checks from the root:

```bash
python3 script/check-package.py
python3 /path/to/skill-creator/scripts/quick_validate.py \
  plugins/dex/skills/dex-developer
python3 /path/to/plugin-creator/scripts/validate_plugin.py plugins/dex
claude plugin validate .
```

The last three commands require the corresponding agent tooling. CI runs the
repository-owned structural checks.

## Version a change

Every change under `plugins/dex/skills/dex-developer/` must update `VERSION` and
`CHANGELOG.md` in the same pull request. Keep all plugin manifests on the exact
version in `VERSION`.

- Increment PATCH for corrections and clarifications.
- Increment MINOR for new languages, patterns, or capabilities.
- Increment MAJOR for incompatible identity, invocation, or behavior changes.

Do not put a version on marketplace entries. The plugin manifests are the only
package version source.

## Release

Before creating a release, run all validation commands, install each package
locally, and test the skill in a new agent task or reloaded session. Tag the
validated commit as `v<version>` only after the manifests, changelog, and
documentation agree.
