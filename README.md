# Dex Developer

Dex Developer is the official coding-agent skill for building, debugging,
testing, and operating applications with [Superdurable Dex](https://docs.superdurable.io).
It covers the public Dex programming model in Python, Go, Java, TypeScript, and
Rust.

This repository is the single source of truth for the `dex-developer` skill.
The `dex` plugin packages that skill for Codex, Claude Code, and Cursor without
adding an MCP server, hooks, or application runtime dependencies.

## Install

### Codex

```bash
codex plugin marketplace add superdurable/skill-dex-developer
codex plugin add dex@superdurable
```

Start a new task after installation. Invoke the skill with `$dex-developer`, or
let Codex select it for Dex application work.

### Claude Code

Run these commands inside Claude Code:

```text
/plugin marketplace add superdurable/skill-dex-developer
/plugin install dex@superdurable
/reload-plugins
```

Invoke the skill with `/dex:dex-developer`.

### Cursor

Cursor loads the portable Agent Plugin in `plugins/dex`. Until it is listed in
the public Cursor Marketplace, import this repository into a team marketplace
or install the skill directly:

```bash
npx skills add superdurable/skill-dex-developer --skill dex-developer
```

For local plugin development, link `plugins/dex` into
`~/.cursor/plugins/local/dex`, then restart Cursor or run **Developer: Reload
Window**. Invoke the skill with `/dex-developer`, or let Cursor select it.

### Other Agent Skills clients

```bash
npx skills add superdurable/skill-dex-developer --skill dex-developer
```

## Updates

Releases use semantic versions. Agents load an installed or cached copy; they do
not fetch the latest GitHub content for every prompt.

- Codex: upgrade the `superdurable` marketplace, reinstall
  `dex@superdurable`, and start a new task.
- Claude Code: update the marketplace and run `/reload-plugins`. Third-party
  marketplace auto-update can also be enabled in the plugin UI.
- Cursor: refresh or reinstall the marketplace plugin. Team marketplaces can
  enable Auto Refresh. Reload the window when testing a local plugin update.
- Direct skill installs: rerun the `npx skills add` command.

The skill version describes this guidance package, not the installed Dex SDK.
The skill requires the agent to inspect the project's installed SDK and
version-matched runnable examples before choosing exact APIs.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for validation and release rules. The
plugin is distributed under the [MIT License](LICENSE).
