---
name: nagini-language
description: Nagini language reference and verification tools. Provides the syntax, permission model, and tooling needed to write and verify Nagini Python programs. Use when the user asks to verify, prove, or formally check Python code or to add specifications to it, when writing or reading Nagini specifications, for Nagini syntax questions, or when working with the Nagini verification tools.
---

# Nagini Language & Tools

<!-- if knowledge -->
This skill provides the Nagini language reference, verified examples, and the verification tool contract.

Nagini specifications are Python function calls (`Requires()`, `Ensures()`, `Acc()`, `Fold()`, etc.) from `nagini_contracts.contracts`. Nagini translates annotated Python into the Viper intermediate language and verifies with Silicon.
<!-- if workflow -->
<!-- else -->

Three companion skills carry the methodology: load `handling-verification-errors` when verification fails repeatedly, `nagini-performance` when it is slow or times out, and `spec-quality` when designing contracts.
<!-- end -->

<!-- else -->
This skill provides the Nagini language reference and the verification tool contract.
<!-- end -->

## Verification tools

Verification runs through the `nagini` MCP server.
<!-- if knowledge -->
If a `mcp__nagini__` tool call fails with "No such tool available", load the tools with `ToolSearch("select:mcp__nagini__verify_method,mcp__nagini__verify_snippet,mcp__nagini__verify_file,mcp__nagini__cancel,mcp__nagini__flush_cache")` and retry. If the tools are still unavailable, do not fall back to the `nagini` CLI: diagnose with the plugin README.md and walk the user through the fix. The server spawns once at Claude Code startup with its launch environment, so most fixes require restarting Claude Code.
<!-- end -->

- `mcp__nagini__verify_method(path, methods)` — the primary tool. `path` must be absolute. `methods` is a list of member names: a bare function name, `ClassName.method_name`, or `ClassName` (all its methods). Verify only what you are working on: the one method while iterating on it, and when several methods need (re-)checking, pass them as one list in a single call.
<!-- if knowledge -->
- `mcp__nagini__verify_snippet(code)` — verify inline code without creating a file.
- `mcp__nagini__verify_file(path)` — verify a whole file; on a small file the simpler equivalent of listing every member. Once a whole-file run takes more than a couple of minutes, it is better to verify the changed members and their dependents instead. An optional `methods` list restricts it like `verify_method`, `base_dir` sets the package root for intra-package imports, and `ignore_global` skips top-level statements. With `translate_only: true` it is the standard well-formedness check for a file (e.g. a test file before verification).

Optional parameters on all verify tools:

- `viper_args: [...]` — extra Silicon backend arguments. Sensible defaults are baked into the server launch.
<!-- if timeouts -->
In particular, this includes a whole-run `--timeout` and per-assert SMT budget `--assertTimeout`.
<!-- end -->
<!-- if errors -->
SMT-state collection (`--smtStateOnError`) is among them: every verification failure already carries its `debug` payload.
<!-- end -->

<!-- if errors -->
- `counterexample: true` — include concrete failing variable assignments in each diagnostic.
- `include_viper: true` — return the whole translated Viper program as `viperProgram` (thousands of lines for a large module). A failing diagnostic's `debug.viperExcerpt` already carries the member concerned.

`mcp__nagini__inspect(recorded_at, diagnostic, fields)` reads a diagnostic's archived payload without re-verifying: `recorded_at` is the verify result's `recordedAt`, `diagnostic` the index into its `diagnostics`. Without `fields` it lists what is archived with sizes; with `fields` (e.g. `["assumptions", "state.heap"]`) it returns them, list fields as their newest `last` entries, filtered to those containing `contains` when given.
<!-- end -->
- `translate_only: true` — stop after translation (mypy + Nagini-to-Viper); nothing is verified.

Result shape:
```json
{"success": bool, "translationFailed": bool, "cancelled": bool, "crashed": bool, "duration": float,
 "diagnostics": [{"file": str, "startLine": int, "startCol": int, "endLine": int, "endCol": int,
                  "code": str, "message": str, "reason": str, "reasonPosition": [int, int],
                  "counterexample": str, "branchConditions": [str], "vias": []}]}
```
Pass/fail is the `success` field. `translationFailed: true` marks syntax/type/translation errors as opposed to verification failures. `cancelled: true` means the run was stopped by the `cancel` tool or by the whole-run budget; a whole-run timeout is always reported as a `TimeoutOccurred` diagnostic. `crashed: true` means the backend died with an exception, reported in a `verifier.crashed` diagnostic; an identical re-run usually crashes again. `startLine` is 1-indexed. `reasonPosition` is the line and column of the clause the `reason` names, such as the failing postcondition; `[0, 0]` when there is none. `branchConditions` are the branch decisions, as Python conditions with their positions, on the path the failure was found on. `vias` lists intermediate positions the error was routed through.
<!-- if errors -->
With diagnostics on, the result also carries `timings` (seconds per pipeline phase: typecheck, translate, chop, verify) and `recordedAt` (this run's archive directory), and every verification failure a `debug` payload. `include_viper` adds `viperProgram`.
<!-- end -->
<!-- end -->

`mcp__nagini__cancel(job_token)` cancels an in-flight verification; `mcp__nagini__flush_cache()` clears the verification result cache.

<!-- if knowledge -->

The result cache keys entries on the file content and backend; verifier flags are not part of the key. Editing a file therefore changes its cache key — after an edit, re-verifying needs no flush. Flush only when re-running *unchanged* content under different `viper_args`, where the old flags' result would be served back; `--disableCaching` on the probe is a flush-free alternative. `flush_cache()` clears the whole cache for every agent sharing the server, so a spurious flush makes everyone re-pay verification that a warm cache would have served.
<!-- if timeouts -->
A raised `--assertTimeout` probe on unchanged content is the typical case.
<!-- end -->
<!-- if errors -->
A failure served from the cache carries a `[note: result served from the verification cache …]` marker and no `debug` payload.
<!-- end -->

Only *methods* are cached: pure functions and predicates re-pay their full verification cost on every call.

Re-verifying an unchanged member is waste either way — a cached method replays its old result, an uncached member re-pays its cost for the identical outcome.
<!-- end -->

## Resources

### references/nagini-language.md
The Nagini language reference: the specification constructs, their syntax and semantics, and the rules for using them. **Read this first when writing Nagini code.**

<!-- if knowledge -->
### references/limitations.md
Confirmed Nagini limitations — what the language cannot express or prove, with workarounds. Consult before concluding that a property is inexpressible or that a workaround is needed; cited as the canonical authority for "is X really a Nagini limitation?" decisions.

### examples/
Working verified `.py` files. Load individual files as needed.

| File | Description | Key techniques |
|------|-------------|----------------|
| `binary_search.py` | Binary search on a sorted list | `@Ghost @Pure` boolean predicate, `PSeq`/`ToSeq()`, quantified specs (`Forall`), `Acc(list_pred(a))`, pure function in loop invariant |
| `linked_list.py` | Linked list with prepend and find | `@Predicate`, `Fold`/`Unfold`, `Unfolding` in pure functions, `Decreases(pred)`, `Optional[Node]`, `is` for reference identity in `Ensures` |
| `quicksort.py` | Quicksort with partitioning | `for` loops with `Previous(item)`, fractional permissions (`Acc(..., 2/3)`), `MustTerminate`, recursive method, list concatenation |
| `sorted_list_insert.py` | Sorted list insert maintaining sortedness and uniqueness | `list.insert`, `PSeq.drop`, inductive lemma as `@Ghost @Pure` function, proof by contradiction, `ToSeq` bridge pattern |

<!-- if errors -->
### references/viper-language.md
Viper intermediate language reference. Load this when inspecting the encoded Viper. It documents the syntax, permissions, and constructs that appear in that output.
<!-- end -->
<!-- end -->
