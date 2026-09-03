---
name: nagini-performance
description: Verification performance for Nagini. The cost model, healthy-runtime baselines, and the catalog of contract, predicate, and proof shapes that determine verification cost. Use when designing spec vocabulary and contracts and when verification runs slow or times out.
---

# Verification Performance

Verification time ≈ number of symbolic execution paths × cost per SMT query. Query cost is dominated by the proof context: every axiom, pure-function body, path condition, and heap chunk in scope alongside the goal. Slowness is too many paths, too much context, or both; the two multiply.


Contract and vocabulary shapes determine this cost before any proof is written, and proof effort cannot recover a cheap shape from an expensive one. The fix catalog therefore serves both phases:
- at design time, pick the cheap shape;
- at repair time, diagnose which resource is exhausted (Diagnosis)
<!-- if timeouts -->
- spend budget only within the allowed probes (Budget policy)
<!-- end -->
- restructure toward the cheap shape (the catalog).

## What healthy looks like

A single-member verification takes seconds to low tens of seconds; contract-only stubs, predicates and small pure functions a few seconds. A member that takes minutes is an outlier with a structural cause, not "a big function" — and slow verification is usually many cheap queries (paths × obligations), not a few hard ones. Slow predicates and small pure functions are frequently the real culprit behind a slow method, because their cost is paid again at every unfold or call site: look there before tuning the method.

The vocabulary of a project is the biggest lever for performance. The `@ContractOnly` stubs, predicates and `@Pure` functions need to verify quickly, because they are used everywhere. If verification of these primitives takes longer than a few seconds, verification will likely fail. Fixing the vocabulary should always be the first priority, never carry an expensive vocabulary forward on the promise that proof effort will cope.

## Diagnosis

Three checks route a slow member to the right fix; run them in order.

<!-- if errors -->
**1. Encode or prove?** Every verification result carries `timings`: seconds spent in each pipeline phase (`typecheck`, `translate`, `chop`, `verify`). If `translate` or `chop` dominates, the program is pathological to *encode*, not to prove — shrink or split the member being encoded. Continue only when `verify` dominates.
<!-- else -->
**1. Encode or prove?** Compare the `duration` of a `translate_only: true` run with that of the full verification. If translation dominates, the program is pathological to *encode*, not to prove — shrink or split the member being encoded. Continue only when verification dominates.
<!-- end -->

**2. Fact-starved or budget-bound?** A stepping-stone `Assert` that supplies a fact the solver was missing makes the checks after it cheaper — that is the fix for an under-instantiated goal
<!-- if errors -->
(the `(incomplete quantifiers)` diagnosis in the handling-verification-errors skill).
<!-- else -->
(the handling-verification-errors skill's probe-assert strategy).
<!-- end -->
But on a check that is budget-bound and making progress rather than fact-starved, each added assert is one more query against the same budget: there, cut context or paths instead of adding proof steps.
<!-- if errors -->
A failing diagnostic's `debug` payload tells the two apart — `reasonUnknown`, and whether `rlimitDelta` sits at the cap.
<!-- else -->
Probing tells the two apart: a fact-starved check closes as soon as the missing fact is asserted, while a budget-bound check keeps getting slower as the proof context grows.
<!-- end -->

**3. Which bottleneck class?** Two signals identify the class, which picks the catalog family:

<!-- if timeouts -->
- A `TimeoutOccurred` for the whole-run `--timeout` means the global budget expired while every individual check stayed within its per-check budget. With a low `assertTimeout` that means the member fans out too many sub-budget queries (a path per impure conditional, every `Assert` re-proved on each) → path explosion; cut paths.
<!-- else -->
- A `TimeoutOccurred` for the whole-run `--timeout` usually means the member fans out too many queries (a path per impure conditional, every `Assert` re-proved on each) → path explosion; cut paths.
<!-- end -->
- A member that verifies only under a `viper_args` flag has identified its bottleneck: `--moreJoins 1` (join branches after impure conditionals) passes now → path explosion; cut paths. `--exhaleMode 0` (greedy heap reasoning; incomplete under disjunctive aliasing, so a *new* error under it proves nothing) passes now → heap-exhale cost; shrink the permission footprint and keep predicates folded.

<!-- if timeouts -->
## Budget policy

Raised budgets are probes, not fixes. On a whole-run timeout, a single 2x `--timeout` re-run is a fair probe; beyond 2x more budget rarely helps — decompose rather than re-budget. For a single budget-bound check (`canceled`), up to 10x the default `assertTimeout` is an acceptable fix if the check closes within it; beyond 10x, restructure rather than re-budget.

Every escalation is temporary: after the change it motivated, turn the budget back down and re-verify at the standard limits. A member that can only iterate under escalated budgets will drag the rest of the verification down permanently. Apply the fix catalog until the standard budgets carry it again.
<!-- end -->

## The fix catalog

Match the family to the diagnosis: fact-starved goals want a well-placed fact or trigger (Triggers), path explosion wants fewer paths (Cut symbolic paths), and everything budget-bound on context wants a smaller context (Shrink the proof context).

### Shrink the proof context

- **Hide quantifiers in predicates.** Every `Forall` will add to the proof context. Wrap it in a predicate to remove it from the context, especially in contracts or invariants. Unfold only when necessary, possibly in a targeted lemma to avoid bloating the proof context. Note that this does not only hold for permissions, any quantifier can be put in a predicate.
- **Heap facts behind one predicate, exposed via accessors.** Keep a structure's permissions and invariants in a single predicate, and read them through `@Pure` accessors that take the predicate and unfold it. Phrase contracts as relations over those accessors (`parent(self, k) == Old(parent(self, k))`) rather than `Forall`s over `xs[k].field`: the predicate is one chunk, while a quantified heap access is re-justified on every path of every check mentioning the contract.
- **Plain `@Pure` bodies are global axioms; use `@Opaque` to hide them.** Every plain `@Pure` body compiles to a definitional axiom (`forall args: f(args) == body`) that E-matching chases automatically wherever the function appears — wrapping a heavy condition in a plain `@Pure` function shrinks nothing. Only `@Predicate` bodies (opaque until unfolded) and `@Opaque` `@Pure` functions actually hide a definition. Mark heavy, widely-used pure definitions `@Opaque`, put what callers routinely need in the `Ensures`, and `Reveal` at the few sites that need the definition itself. Ideally, only call `Reveal` in controlled limited environments like inside a targeted lemma, to avoid introducing the expensive body into every caller's proof context.
- **Keep predicates folded.** In loop invariants, hold the predicate folded; `Unfold`/`Fold` inside the body, `Unfolding(...)` for value reads. An unfolded predicate costs as much as no predicate.
- **Pointwise or recursive instead of sliced.** A pure function whose body slices a sequence (`s.take(i)`, `s.drop(j)`) injects nested take/drop terms into every obligation of every caller. For vocabulary used across a file, define the property pointwise over indices or recursively, and derive take/drop equalities inside lemmas where a caller needs them. A cheap-looking `Assert` that introduces one `take`/`drop` term is not cheap either: terms persist in the context, assertions do not.
- **One heap per contract.** Phrase postconditions against the current state wherever possible; every `Old(...)` equality over a container or representation puts two families of terms plus the bridge between them into each obligation. Read-only state framed via fractions needs no `Old` clause at all.
- **Recursive instead of quantified.** A recursive pure-function definition needs no trigger; a `Forall`-based definition needs a well-chosen trigger and joins the instantiation search of every obligation that mentions it.
- **Move proof steps into a lemma.** A lemma's proof context is exactly its precondition, and its facts reach the caller only through its postcondition.
- **Split large methods**; extract inner loops into helper methods with contracts.

### Cut symbolic paths

- **Split branchy predicates.** A predicate body with N `Implies`-guarded conjuncts forks 2^N symbolic paths at every unfold site. Move each guarded part into its own predicate, unfolded on demand.
- **Split flat `elif` chains** across two or more helper functions — a many-branch body can fail its own postcondition as a hard incompleteness, not only as a timeout.
- **One lemma per disjunct.** Split a lemma precondition of the form `A or B` into one lemma per disjunct, selected at the call site by `if`. A disjunctive goal gives the solver no branch to take; each disjunct on its own path is a one-step goal.
- **Replace `Exists()` with an explicit witness** — a witness variable or a pure function returning it (see the `nagini-language` limitations reference).

### Triggers

- Give every `Forall` an explicit trigger: the most restrictive terms that still fire (see Trigger rules in the `nagini-language` reference).
- Collapse nested `Forall` over independent domains into `Forall2`/.../`Forall6` with a joint trigger.
- When two consumers phrase a quantified fact's terms differently, give one `Assert` both trigger sets as alternatives.
- Establish a quantified fact before the branch that consumes it, not only where the invariant is re-established at the end of the loop body.
- A matching loop — instantiation produces a new term matching the same trigger — consumes any budget; fix the trigger, more budget will not help.

## While iterating

- **Measure every change.** After a performance change, compare the duration and revert it if it did not win.

- **Termination last.** Comment out `Decreases()`/`MustTerminate` measures and verify partial correctness first; restore them once the functional proof passes. Every run otherwise re-pays the termination obligations, and their failures mix into the functional signal.
