# Nagini Claude Plugin

A [Claude Code](https://claude.com/claude-code) plugin for formally verifying Python programs with [Nagini](https://github.com/marcoeilers/nagini), the Python verifier built on the [Viper](https://viper.ethz.ch) infrastructure.

The plugin provides:

- **Skills** — `nagini-language` (language and tooling reference with verified examples), `spec-quality` (specification design principles), `handling-verification-errors` (debugging playbook), and `nagini-performance` (verification-cost model and shape catalog).
- **MCP tools** — `verify_method`, `verify_snippet`, and `verify_file` for in-session verification with caching, plus `cancel` and `flush_cache`, via a bundled Nagini MCP server launcher.

## Prerequisites

You need:

1. **uv**: to install Nagini and its dependencies in an isolated environment. Check out the install instructions [here](https://docs.astral.sh/uv/getting-started/installation/)

The first server start downloads nagini and its dependencies. Later starts use uv's cache.

To use your own nagini instead, set `NAGINI_FROM` to any `uvx --from` source in the environment you start Claude Code from — a different release (`NAGINI_FROM='nagini[mcp]==1.3.0'`), a source checkout (`NAGINI_FROM=/path/to/nagini`), or a git URL. uvx caches builds, so after editing a source checkout run `uv cache clean nagini` to pick up the changes.

2. **A 64-bit Java runtime (JDK/JRE 11+)** for the Viper backend.



## Installation

In Claude Code:

```
/plugin marketplace add viperproject/nagini-claude-plugin
/plugin install nagini@viperproject
```

Skills are then available under the `nagini:` namespace (e.g. `/nagini:nagini-language`), and the MCP verification tools as `mcp__nagini__verify_method`, `mcp__nagini__verify_snippet`, `mcp__nagini__verify_file`, `mcp__nagini__cancel`, and `mcp__nagini__flush_cache`.

To update later, run `/plugin marketplace update viperproject`. Auto-update is off by default for third-party marketplaces. The plugin's version tracks the git commit, so every push to this repository is picked up by the next update.

## Usage

Ask Claude to verify, prove, or add specifications to Python code — the `nagini-language` skill triggers and provides the language reference, verified examples, and the verify-tool contract; `handling-verification-errors` kicks in when verification fails or times out. Skills can also be invoked directly (e.g. `/nagini:nagini-language`).

## Development

```sh
# validate manifest and structure
claude plugin validate ./plugin

# run a session with the local checkout instead of the installed version
claude --plugin-dir /path/to/nagini-claude-plugin/plugin
```

Inside a session, `/reload-plugins` picks up local edits without restarting. Alternatively, add the checkout as a local marketplace: `/plugin marketplace add ./nagini-claude-plugin`.

Layout — the plugin itself lives in `plugin/`; everything outside it (tests, CI) stays out of users' installed copies:

- `.claude-plugin/marketplace.json` — same-repo marketplace (`viperproject`), pointing at `./plugin`
- `plugin/.claude-plugin/plugin.json` — plugin manifest (no `version` field: versions track git commits while under active development)
- `plugin/.mcp.json` — MCP server wiring: runs the pinned nagini via uvx, isolated from any Python environment on the machine. The single source of truth for the nagini and Python pins; both are env-overridable (`NAGINI_FROM`, `NAGINI_PYTHON`). The `--with mcp>=1.2,<2` cap is needed because nagini releases up to 1.3.1 declare no upper bound on `mcp`, and mcp 2.0 lacks the embedded FastMCP server API; it can go once the default release carries the bound itself
- `plugin/skills/<name>/SKILL.md` — skills, with supporting material in `references/` and `examples/`

## Troubleshooting

The MCP server's error output appears in `/mcp` (or the `/plugin` errors view).

- **"No JVM shared library file (libjvm.so) found"** (or the server dies at startup with a `JVMNotFoundException` traceback) — install a 64-bit JDK/JRE 11+. The JVM is located via `JAVA_HOME` or the platform's standard install locations; set `JAVA_HOME` if yours lives somewhere unusual.
- **`uvx` fails to spawn ("command not found" / ENOENT)** — install uv (see Prerequisites) and make sure `uvx` is on the `PATH` of the shell you launch Claude Code from.

## License

[MPL-2.0](LICENSE)
