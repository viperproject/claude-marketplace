---
name: nagini-performance
description: Verification performance for Nagini. The cost model, healthy-runtime baselines, and the catalog of contract, predicate, and proof shapes that determine verification cost. Use when designing spec vocabulary and contracts and when verification runs slow or times out.
---

# Verification Performance

Verification time ≈ number of symbolic execution paths × cost per SMT query. Query cost is dominated by the proof context: every axiom, pure-function body, path condition, quantifier, and heap chunk in scope alongside the goal. Slowness is too many paths, too much context, or both; the two multiply.

Contract and vocabulary shapes determine this cost before any proof is written, and proof effort cannot recover a cheap shape from an expensive one. The fix catalog therefore serves both phases:
- at design time, pick the cheap shape;
- at repair time, diagnose which resource is exhausted (Diagnosis)
<!-- if timeouts -->
- spend budget only within the allowed probes (Raising budgets)
<!-- end -->
- restructure toward the cheap shape (the catalog).

## What healthy looks like

A single-member verification takes seconds to low tens of seconds; contract-only stubs, predicates and small pure functions a few seconds. A member that takes minutes is an outlier with a structural cause, not "a big function" — and slow verification is usually many cheap queries (paths × obligations), not a few hard ones. Slow predicates and small pure functions are frequently the real culprit behind a slow method, because their cost is paid again at every unfold or call site: look there before tuning the method.

The vocabulary of a project is the biggest lever for performance. The `@ContractOnly` stubs, predicates and `@Pure` functions need to verify quickly, because they are used everywhere. If verification of these primitives takes longer than a few seconds, verification will likely fail. Fixing the vocabulary should always be the first priority, never carry an expensive vocabulary forward on the promise that proof effort will cope.

## Diagnosis

<!-- if errors -->
*Encoding or proving?* `timings` gives the seconds per pipeline phase. If `translate` or `chop` dominates `verify`, the cause is encoding: shrink or split the member.
<!-- end -->

*Separating paths from context*:
<!-- if timeouts -->
- Whole-run vs. assert timeout: If the assert timeout is set low, then a `TimeoutOccurred` for the whole-run means the problem is almost certainly paths, whereas a single check `canceled` means one expensive query, so context or instantiation.
<!-- end -->

<!-- if errors -->
- `reasonUnknown` `(incomplete quantifiers)` means the query did not close for lack of a fact: a debugging problem, not a performance one.
<!-- end -->
- You can also probe this with two `viper_args` (remember to flush the cache):
   - `--moreJoins 1` (join branches after impure conditionals) passes now → paths;
   - `--exhaleMode 0` (greedy heap reasoning) passes now → heap context.
   - neither passes → unclear.

<!-- if timeouts -->
## Raising budgets
Raised budgets are probes, not fixes. On a whole-run timeout, a single 2x `--timeout` re-run is a fair probe; beyond 2x more budget rarely helps — decompose rather than re-budget. For a single budget-bound check (`canceled`), up to 10x the default `assertTimeout` is an acceptable fix if the check closes within it; beyond 10x, restructure rather than re-budget.

Every escalation is temporary: after the change it motivated, turn the budget back down and re-verify at the standard limits. A member that can only iterate under escalated budgets will drag the rest of the verification down permanently. Apply the fix catalog until the standard budgets carry it again.
<!-- end -->

## The fix catalog

### Shrink the proof context

- **Hide quantifiers in predicates.** Every `Forall` will add to the proof context. Wrap it in a predicate to remove it from the context, especially in contracts or invariants. Unfold only when necessary, possibly in a targeted lemma to avoid bloating the proof context. Note that this does not only hold for permissions, any quantifier can be put in a predicate.
- **Quantified proof steps persist.** An `Assert(Forall(...))` or a quantified invariant stay in the context for the rest of the method, and every later check may suffer from it. Wrap properties in predicates and opaque functions, reveal the quantifiers only in loop bodies or in separate lemmas. 
- **Heap facts behind one predicate, exposed via accessors.** Keep a structure's permissions and invariants in a single predicate, and read them through `@Pure` accessors that take the predicate and unfold it. Phrase contracts as relations over those accessors (`parent(self, k) == Old(parent(self, k))`) rather than `Forall`s over `xs[k].field`: the predicate is one chunk, while a quantified heap access is re-justified on every path of every check mentioning the contract.
- **Plain `@Pure` bodies are global axioms; use `@Opaque` to hide them.** Every plain `@Pure` body compiles to a definitional axiom (`forall args: f(args) == body`) that E-matching chases automatically wherever the function appears — wrapping a heavy condition in a plain `@Pure` function shrinks nothing. Only `@Predicate` bodies (opaque until unfolded) and `@Opaque` `@Pure` functions actually hide a definition. Mark heavy, widely-used pure definitions `@Opaque`, put what callers routinely need in the `Ensures`, and `Reveal` at the few sites that need the definition itself. Ideally, only call `Reveal` in controlled limited environments like inside a targeted lemma, to avoid introducing the expensive body into every caller's proof context.
- **Keep predicates folded.** In loop invariants, hold the predicate folded; `Unfold`/`Fold` inside the body, `Unfolding(...)` for value reads. An unfolded predicate costs as much as no predicate.
- **Pointwise or recursive instead of sliced.** A pure function whose body slices a sequence (`s.take(i)`, `s.drop(j)`) injects nested take/drop terms into every obligation of every caller. For vocabulary used across a file, define the property pointwise over indices or recursively, and derive take/drop equalities inside lemmas where a caller needs them. A cheap-looking `Assert` that introduces one `take`/`drop` term is not cheap either: terms persist in the context, assertions do not.
- **One heap per contract.** Phrase postconditions against the current state wherever possible; every `Old(...)` equality over a container or representation puts two families of terms plus the bridge between them into each obligation. Read-only state framed via fractions needs no `Old` clause at all.
- **Recursive instead of quantified.** A recursive pure-function definition needs no trigger; a `Forall`-based definition needs a well-chosen trigger and joins the instantiation search of every obligation that mentions it.
- **Move proof steps into a lemma.** A lemma's proof context is exactly its precondition, and its facts reach the caller only through its postcondition.
- **Split large methods**; extract inner loops into helper methods with contracts.

#### Triggers

Every instantiation adds terms to every later query; these entries keep quantifiers from instantiating more than the goal needs. A quantifier that instantiates too little is a starved check — the handling-verification-errors skill's problem, not this one.

- Give every `Forall` an explicit trigger: the most restrictive terms that still fire (see Trigger rules in the `nagini-language` reference).
- Collapse nested `Forall` over independent domains into `Forall2`/.../`Forall6` with a joint trigger.
- A matching loop — instantiation produces a new term matching the same trigger — consumes any budget; fix the trigger, more budget will not help.

### Cut symbolic paths

- **Split branchy predicates.** A predicate body with N `Implies`-guarded conjuncts forks 2^N symbolic paths at every unfold site. Move each guarded part into its own predicate, unfolded on demand.
- **Split flat `elif` chains** across two or more helper functions — a many-branch body can fail its own postcondition as a hard incompleteness, not only as a timeout.
- **One lemma per disjunct.** Split a lemma precondition of the form `A or B` into one lemma per disjunct, selected at the call site by `if`. A disjunctive goal gives the solver no branch to take; each disjunct on its own path is a one-step goal.
- **Replace `Exists()` with an explicit witness** — a witness variable or a pure function returning it (see the `nagini-language` limitations reference).

## While iterating

- **Measure every change.** After a performance change, compare the duration and revert it if it did not win.
- **Termination last.** Comment out `Decreases()`/`MustTerminate` measures and verify partial correctness first; restore them once the functional proof passes.
