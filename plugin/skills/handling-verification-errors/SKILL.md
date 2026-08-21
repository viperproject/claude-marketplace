---
name: handling-verification-errors
description: Nagini debugging and error handling reference. Provides strategies for interpreting Nagini error messages, diagnosing verification failures, and iterating on specs and code to fix issues. Use this skill when you encounter verification errors in Nagini and need to understand and resolve them.
---

# Guiding Principle

- **Never** make assumptions about the cause of a verification error without evidence.
- Instead, always use the systematic techniques described here to gather information and isolate the true cause.
- If you have a theory — "the verifier cannot do X", "this pattern is the problem" — always start by creating a minimal snippet pair that  demonstrates the theory: the failing shape and the closest working variant. Demonstrate before fixing broadly or reporting a limitation.
- Then, you can confidently fix the underlying issue.
- **Never** weaken or delete a contract just to make verification pass; surface the mismatch instead.

# Verifier Limitations

Do not make assumptions about how the verifier works internally. If you make incorrect assumptions, you will make mistakes. The verifier is reasonably powerful. It should practically always be possible to verify code with the correct specifications. If you think you have a correct specification but the verifier cannot prove it, you are likely missing a necessary intermediate assertion or lemma.

There is a list of known verifier limitations in the `nagini-language` skill's capabilities reference. If you think you've encountered a new limitation, confirm it before acting on it:

*Never* assume the verifier has a limitation or bug without first testing it. It is very easy to jump to incorrect conclusions about the reason of a failure. Instead, always try to write a minimal self-contained case that would fail if the limitation exists and verify it. If it verifies, the limitation is not real and the error has another cause.
If you do encounter a real verifier limitation that prevents verification of correct code, report it prominently in your output with a description and the minimal snippet that demonstrates the issue.

# Verifier options

The `mcp__nagini__verify_*` tools and their parameters (per-method selection, `counterexample: true`, `include_viper: true`, `viper_args`) are documented in `nagini-language: Verification tools`; verify only the method(s) you are debugging as one `methods` list in a single call rather than one call each. Read results from the structured response: `message` and `code` identify the error kind, `reason` the failing assertion, `startLine` the location, `counterexample`, `branchConditions` and `debug` the debugging signals. `translationFailed: true` marks syntax/type/translation errors rather than verification failures.

# Dealing with Errors

1. **Phase 1: Isolate** — transform the error into a single failing assertion.
2. **Phase 2: Diagnose** — locate the missing step and reduce it to a self-contained candidate file.
3. **Phase 3: Fix** — verify the candidate file and apply the fix to the original code.

## Phase 1: Isolate the error

Transform the error into a failing assertion.

**For method calls**: Assert the preconditions of the callee before the call to find out which one fails.

**For loop invariants**: Assert the loop invariants, either before the loop or at the end of the loop body, to determine which invariant clause is not being established or preserved.

**For branches/multiple returns**: Do *not* assume which branch is the problem. Add asserts to each branch / before each return to find out which one fails.

**For a whole-run timeout** (`TimeoutOccurred`, no position, no diagnostics): localize manually by commenting out proof obligations until the run completes, or inserting `Assert(False)` before a suspect obligation to confirm the run reaches it. Everything after `Assert(False)` verifies vacuously, so walking it down the body and diffing the durations shows which region the time belongs to.

**Separate conjunctions**: If the error occurs for a conjunction of properties, determine which clause is failing:
- Multiple postconditions/invariants: assert each individually
- Assertions with multiple conjuncts: split into separate asserts
- Method calls with multiple preconditions: assert each precondition separately before the call

## Phase 2: Diagnose
Once Phase 1 has reduced the failure to a single failing assertion, diagnose **what** the solver cannot derive. Diagnosis has two stages:

1. **Locate the missing step** — evidence-guided probing: the `debug` payload classifies the failure and tells you where to aim; `Assert` probes measure what the solver can actually derive and add the missing facts.
2. **Reduce to a candidate** — escalation for the hard cases only: when the missing fact resists inline asserts, build a minimal, self-contained Python file that captures it, and try to verify it in isolation.

Of course, it is also always possible that the state (in particular `assumptions` and `state`) genuinely does not entail the fact you are asserting. No amount of solver help can fix that; it usually requires changes to contracts or loop invariants. 

### Understand the error
Never guess what the reason for a failure is. The error message should contain all the info you need, in particular the error location, reason and the `debug` payload. Read the evidence first.
If a failing diagnostic has no `debug` field, the server was launched without SMT-state collection; pass `viper_args: ["--smtStateOnError", "--assertTimeout=500", "--reportReasonUnknown"]` yourself.

Each failing diagnostic's `debug` object contains the symbolic state at the failure, expressed in the verifier's internal term language:

| Field | Content | Use it to |
|---|---|---|
| `failedAssertion` | The exact goal term the solver could not prove | See the obligation as the solver sees it (after encoding), not as you wrote it |
| `failedAssertionPretty` | The same goal with `@line@col` suffixes stripped and `_checkDefined` shims unwrapped | Read the goal quickly; fall back to the raw term when versions matter |
| `reasonUnknown` | Why the solver returned unknown (see table below) | **Choose the fix strategy** |
| `rlimitDelta` | Prover resources the failing check consumed, in Z3 rlimit units (the budget is `assertTimeout` ms × 9000) | A delta at the budget means the cap bound the check; a delta well below it means the solver stopped on its own |
| `assumptions` | Path-condition terms in scope at the failure, pre-filtered to those sharing a symbol with `failedAssertion` (an `omitted` marker counts the rest) | Scan for gross absences and anomalies. To test whether a specific fact is available, probe it with `Assert` — presence in this list is neither necessary nor sufficient for derivability |
| `branchConditions` | The branch decisions leading to the failing path | Identify which control-flow path fails |
| `state.store` / `state.heap` / `state.oldHeaps` | Local variables, and the heap as a list of chunks (`resource(receiver; snapshot, permission)`) | Trace which symbolic value a variable holds; spot havocked (freshly re-assigned) values after calls; see which permissions the path actually holds |

Bulk fields — the full SMT session (`proverEmits`), the background axioms (`preambleAssumptions`), and the symbol declarations (`functionDecls`/`macroDecls`) — are collected and archived server-side, not sent inline. When a result carries many large diagnostics, later ones may arrive with fields truncated or dropped, each noted in the payload's `omitted` map.

Reading terms: `x@3@05` is a symbolic constant for program variable `x` (numbers are internal versions — successive assignments create new versions). Integers are boxed: `__prim__int___box__`/`int___unbox__` wrap between Python ints and SMT ints, and `_checkDefined(_, x, id)` wraps variable reads (it is identity on the value). `QA x :: body` is a universal quantifier. Pure functions appear applied to a snapshot argument first (`ipow(_, b, e)`).

Every result carries `timings`: seconds spent in each pipeline phase (`typecheck`, `translate`, `chop`, `verify`), and timeout diagnostics repeat them. Read them before diagnosing any timeout. If `translate` or `chop` dominates, the program is pathological to *encode*, not to prove, so shrink or split the member being encoded. Only when `verify` dominates does the rest of this section apply.

A `TimeoutOccurred` for the whole-run `--timeout` means the global budget expired while every individual check stayed within its per-check budget. With a low `assertTimeout` that is a branching problem, not a slow-query one: the member fans out too many sub-budget queries (a path per impure conditional, every `Assert` re-proved on each). Treat it as path explosion and apply the bottleneck classification and path-cutting strategies below. A single 2x `--timeout` re-run is a fair probe; beyond 2x more budget rarely helps — decompose rather than re-budget.


#### Interpreting `reasonUnknown`
For most failures, start by understanding why the SMT-query failed, which is given in the `reasonUnknown` field. :

| Value | Meaning | Strategy |
|---|---|---|
| `(incomplete quantifiers)` | E-matching gave up: the instantiation chain to the proof was never triggered (under-instantiation). More solver time will not help. | Restate the missing fact as a GROUND fact placed where it is always visible: as a postcondition or a local `Assert`. Add only facts the payload shows are missing: speculative extra ground facts feed the instantiation engine and can slow everything down. For quantified goals, also check TRIGGER VOCABULARY: do the premise quantifiers' trigger terms occur under the goal's binder? If not, add a bridging quantified `Assert` whose trigger matches the goal's vocabulary and whose body mentions the premise triggers. |
| `canceled` | The budget ran out while the solver was still working. | One diagnostic probe is worth it: re-run once with ~10x `assertTimeout` and read `rlimitDelta`. If it stops well below the new budget (reason flips to an incompleteness class), time was never the issue. If it scales with the budget, the proof is genuinely slow: a budget of up to 10x the default is an acceptable fix if the check closes within it; beyond 10x, apply the performance strategies below rather than re-budgeting further. On a budget-bound check, prefer cutting context or paths over adding asserts (see the performance strategies). |
| `(incomplete (theory arithmetic))` | Nonlinear integer arithmetic (products, `//`, `%` of variables) is beyond the solver. | More time will not help. Restate the proof with stepping stones that avoid division/modulo OF PRODUCTS entirely: use the Euclid identity (`a == (a // d) * d + a % d`), pure polynomial identities (products may appear; the solver normalizes them), and the bounded-multiple inference (`0 <= m * d < d` implies `m == 0`). `(k * d) // d == k` and `(k * d) % d == 0` are NOT directly provable — derive them via the chain above. |

#### Interpreting `state.heap`
A `insufficient.permission`, `fold.failed`/`unfold.failed`, or `leak_check.failed` diagnostic means that a required permission chunk or obligation could not be exhaled. Start from the heap listing `state.heap`, which is a short list of what the path holds at the failure: `resource(receiver; snapshot) # amount`. Compare it against what the failing construct demands (`failedAssertion` names the demanded chunk). The read classifies the failure into one of two shapes:

**The demanded chunk is absent:**

| What you see in `state.heap` | Cause |
|---|---|
| A folded predicate chunk (`Box_mypred(...; x) # W`) and the demanded field/`dict_pred`/`list_pred` chunk is absent | The permission is **inside the folded predicate** — access it under `Unfolding(...)` / add `Unfold` on this path |
| The chunk existed in `state.oldHeaps['old']` but is gone from `state.heap` | **Consumed along the path** — by a `Fold`, or by a call that did not return it; walk the statements between entry and failure |
| The heap is empty or unrelated on this branch | The contract/invariant never provided it on this path — check `branchConditions` for which path, then the precondition or invariant |

**A matching chunk is present but not provably applicable:**

| What you see in `state.heap` | Missing fact |
|---|---|
| A **conditional/quantified chunk** covering the receiver under a guard (`QA r,s :: MyPred(r,s) -> ... # (r == r_0 && s == s_0 ? W : Z)`) | The solver cannot prove your receiver satisfies the guard / lies in the quantified domain — assert the guard equalities as ground facts before the failing point |
| The chunk on a **different receiver symbol** than the demanded one (`self_2@10` held, `self@14` demanded) | A receiver equality (aliasing fact) is missing — or the expression genuinely evaluates against the wrong object |
| The chunk with a **symbolic amount** (`# $k@50`) | The solver cannot prove the amount suffices (`$k > 0`, `$k >= 1/2`, ...) — assert where the fraction came from |
| The chunk fractional (`# 1/2`) where a write or full-permission fold is demanded | Deliberate split not reassembled — see the spec's permission accounting |
| A `MustTerminate`/obligation chunk in a `leak_check.failed` | Read the obligation measures in `failedAssertion` — the inequality states the budget deficit directly (e.g. a callee's `MustTerminate` measure not strictly below the caller's remaining budget) |

#### Fact failures — worked example

A loop that swaps `heap[pos]` and `heap[parent]` fails its invariant with
`invariant.not.preserved:assertion.false`, reason `Assertion ToMS(ToSeq(heap)) == Old(ToMS(ToSeq(heap))) might not hold`, and this payload (abridged):

```json
{
  "failedAssertionPretty": "PMultiset___eq__((_, (_, _)),
      __toMS(PSeq___sil_seq__(_, heap)), Old(__toMS(...)))",
  "reasonUnknown": "(incomplete quantifiers)",
  "rlimitDelta": 4500000,
  "branchConditions": [],
  "assumptions": ["issubtype(typeof(heap), list(int))",
                   "PSeq___update__(_, sq, pos, tmp) == ..."],
  "state": {"store": "TreeSeqMap(heap -> heap@13@07, pos -> pos@4@07, ...)",
             "heap": ["list_acc(heap@13@07; sm@8@01, 1/1)"]}
}
```

Read it in this order:
1. `reasonUnknown` is `(incomplete quantifiers)` and `rlimitDelta` sits exactly at the budget (500ms × 9000) — the instantiation search was still churning when the cap hit. Strategy row 1 applies: do **not** re-run with a bigger budget.
2. The goal (pretty form) is a multiset equality over `__toMS(...)` of the sequence; the `assumptions` list has facts about `PSeq___update__` (the element writes) but **nothing connecting a sequence update to its `__toMS` image** — the bridge the goal needs is absent, not slow.
3. `state.store` shows `heap` still bound to the same version (`heap@13@07`) on both sides — so the failure is not a havocked variable; it really is the missing seq-to-multiset bridging fact.

Fix accordingly: state the bridge as a ground stepping stone before the invariant re-check — `Assert(ToMS(ToSeq(heap)) == old_ms - PMultiset(a, b) + PMultiset(b, a))`-style — or extract a `lemma_seq_update_multiset` with that postcondition and call it after the two writes.

##### Permission failures — worked example

A pure helper fails with `application.precondition:insufficient.permission` ("There might be insufficient permission") and this payload (abridged):

```json
{
  "failedAssertion": "... dict_acc(self._fwd, ...) ...",
  "reasonUnknown": "(incomplete quantifiers)",
  "state": {"store": "TreeSeqMap(self -> self_2@10@06, key -> key@4@06, ...)",
             "heap": ["Box_pair_state(sm@14@06; self_2@10@06) # W"]}
}
```

Read it in this order:
1. `state.heap` — one chunk: the folded predicate `pair_state(self_2)` at full permission, and nothing else. The `dict_acc(self._fwd)` the application demands is not in the heap, so it must live **inside the folded predicate**: the cause is identified before any probe. The call must be wrapped in `Unfolding(self.pair_state(), ...)`, or the function's own precondition must require the predicate and the body unfold it.
2. Cross-check receivers: the held chunk's receiver (`self_2@10@06`) matches the store's binding for `self` — so this is a folding problem, not an aliasing problem. If they differed, the fix would instead be establishing the aliasing fact or evaluating against the right object.
3. `reasonUnknown` still gets a look, as a sanity check rather than the router. Here it says `(incomplete quantifiers)`, which adds nothing beyond the heap read (the exhale search gave up — expected when the chunk is plainly absent).


### Adding probe asserts
To further understand the failure and also help it with explicit intermediate facts, you can insert probe asserts. Before the failing assertion, insert additional assertions and re-run the verifier. Insert several `Assert(...)` probes at once. Every passing probe confirms a fact the solver knows; the first failing one pinpoints the missing step. 

If an intermediate assert fails, then you can repeat the process on this assertion to narrow down the failure. Otherwise, you can add more intermediate asserts.
Often the probes themselves are the fix. A few well-placed `Assert(...)` statements give the solver the intermediate facts (or quantifier triggers) it needs to discharge the original goal. When that happens, you are done: keep the asserts that hold the verification together and skip creating and verifying a candidate.

#### Choosing probe asserts

To pick candidate intermediate facts to probe with, use the patterns below. You can use multiple strategies at once.

**Explicit failing SMT-queries**: the `failedAssertion` term is the exact obligation the solver could not prove. Translate it back to Python and assert it before the failing point.

**Weakest-precondition backtracking** to move a failing assert earlier. To debug a failing `assert P`, move it earlier by computing the weakest precondition over the preceding statement. Repeat until the assert passes (bug is between the two positions) or reaches method entry (precondition too weak).

| Failing pattern | Insert before the statement |
|---|---|
| `x := E;` `assert P;` | `assert P[x := E];` |
| `if B {` `  assert P; ...` `}` | `assert B ==> P;` |
| `if B { ... } else {` `  assert P; ...` `}` | `assert !B ==> P;` |
| `if B { ... } else { ... }` `assert P;` | push `assert P;` to end of **each** branch |
| `assert A == C;` across a call | chain: `assert A == B;` then call then `assert B == C;` |
| `Assert(Implies(A, B))` | `if A: Assert(B)` |
| `assert A && B;` | `assert A;` `assert B;` |
| `ensures P ==> Q` on a method | change to `requires P` `ensures Q` |
| `assert forall i \| 0 < i <= m :: P(i);` | split: `assert forall i \| 0 < i < m :: P(i);` and `assert P(m);` |
| `assert forall i \| i == m :: P(i);` | `assert P(m);` (instantiate the singleton range) |

**Partial-property probes** for specific facts the verifier may not know.

*Check permissions:*

| Check | Nagini |
|---|---|
| Field permission | `Assert(Acc(x.f))` |
| Read permission | `Assert(Acc(x.f, 1/2))` |
| Predicate held | `Assert(list_pred(x))` |

*Check values:*

| Check | Nagini |
|---|---|
| Known value | `Assert(x.f == 42)` |
| Known bound | `Assert(x.f > 0)` |
| Non-null | `Assert(x is not None)` |

*Check aliasing:*

| Check | Nagini |
|---|---|
| Non-aliasing | `Assert(x != y)` |

*Check data structure properties:*

| Check | Nagini |
|---|---|
| Length | `Assert(len(xs) == n)` |
| Element access | `Assert(xs[i] == v)` |
| Membership | `Assert(x in s)` |
| List / Sequence prefix | `Assert(s.take(i) == t)` |
| List / Sequence suffix | `Assert(s.drop(i) == t)` |
| List / Sequence concatenation | `Assert(s + t == u)` |
| List as sequence | `Assert(ToSeq(xs) == s)` |
| Set operations | `Assert(s - t == u)` |
| Multiset count | `Assert(s.count(x) == n)` |

To probe a predicate's contents: unfold, assert individual properties and nested predicates, then fold back. Always restore the predicate.

When a fold fails, assert each component of the predicate body separately (without unfolding) to find which piece is missing. When a postcondition involving a pure function over a predicate fails, unfold and check the function's recursive structure step by step.

**Permission flow tracing**: Track permissions through the method:
1. List permissions **acquired** (preconditions, unfolds, allocations)
2. List permissions **consumed** (folds, method calls, exhales)
3. List permissions **needed** (postconditions, remaining folds)
4. Check: acquired - consumed >= needed?

`state.heap` at the failure already gives you the acquired-minus-consumed inventory for free; trace manually to find *which statement* along the path consumed a chunk the heap read showed missing.

#### Performance strategies

Verification time ≈ number of symbolic execution paths × cost per SMT query. Query cost is dominated by the proof context: every axiom, pure-function body, path condition, and heap chunk in scope alongside the goal. Slowness is too many paths, too much context, or both; the two multiply.

What healthy looks like: a single-member verification takes seconds to low tens of seconds; contract-only stubs, predicates and small pure functions a few seconds; the per-check budget is rarely touched. A member that takes minutes is an outlier with a structural cause, not "a big function" — and slow verification is usually many cheap queries (paths × obligations), not a few hard ones. Slow predicates and small pure functions are frequently the real culprit behind a slow method, because their cost is paid again at every unfold or call site: look there before tuning the method. After a performance change, compare the member's duration (`timings`) and revert it if it did not win.

Asserts cut both ways. A stepping-stone `Assert` that supplies a fact the solver was missing makes the checks after it cheaper — that is the fix for an under-instantiated goal (see the `(incomplete quantifiers)` row above). But on a check that is budget-bound and making progress rather than fact-starved, each added assert is one more query against the same budget: there, cut context or paths instead of adding proof steps. The `debug` payload tells the two apart — `reasonUnknown` and whether `rlimitDelta` sits at the cap.

**Shrink the proof context:**
- Keep predicates folded in loop invariants; `Unfold`/`Fold` inside the body, `Unfolding(...)` for value reads. An unfolded predicate costs as much as no predicate.
- Split branchy predicates: a predicate body with N impure implications (`Implies(x.f is not None, P(x.f))`) forks 2^N paths at every unfold site. Move each implication into its own predicate, unfolded on demand.
- Avoid sequence slicing in specs: nested `take`/`drop` terms are among the most expensive obligations, and the cost lands on every caller of the function that mentions them. Define properties in index form or as recursive range functions instead. A cheap-looking `Assert` that introduces one `take`/`drop` term is not cheap: terms persist in the context, assertions do not.
- Hide quantified facts inside predicates; expose them locally where needed. Contracts that are slow merely to check as `@ContractOnly` stubs need this first: predicate + `@Pure` accessors (see the spec-quality skill's Performance by Design).
- Move proof steps into a lemma: a lemma's proof context is exactly its precondition, and its facts reach the caller only through its postcondition.
- Split large methods; extract inner loops into helper methods with contracts.

**Cut symbolic paths:**
- Replace `Exists()` with an explicit witness.
- Split a lemma precondition of the form `A or B` into one lemma per disjunct, selected at the call site by `if`. A disjunctive goal gives the solver no branch to take; each disjunct on its own path is a one-step goal.

**Triggers:**
- Give every `Forall` an explicit trigger: the most restrictive terms that still fire.
- Collapse nested `Forall` into `Forall2`/.../`Forall6` with a joint trigger.
- When two consumers phrase a quantified fact's terms differently, give one `Assert` both trigger sets as alternatives.
- Establish a quantified fact before the branch that consumes it, not only where the invariant is re-established at the end of the loop body.
- A matching loop — instantiation produces a new term matching the same trigger — consumes any budget; fix the trigger, more budget will not help.

**Termination last:** comment out `Decreases()`/`MustTerminate` measures, verify partial correctness first, and restore them once the functional proof passes.

**Bottleneck classification via `viper_args`:** A member that verifies only under a flag has identified its bottleneck class, which picks the strategy above:
- `--moreJoins 1` (join branches after impure conditionals): passes now → path explosion; cut paths.
- `--exhaleMode 0` (greedy heap reasoning; incomplete under disjunctive aliasing, so a *new* error under it proves nothing): passes now → heap-exhale cost; shrink the permission footprint and keep predicates folded.

### Reduce to a self-contained candidate

After locating the facts that hold at the failure site (every probe assert that passed) and the one that doesn't (the failing fact), create a **candidate lemma**: holding facts become preconditions, the failing fact becomes the postcondition, the body starts as `pass`.

**Procedure.**

1. **Build the candidate.** Create `<method>_repro.py`. Define a fresh function with:
- **Parameters:** exactly the variables referenced in its pre- and postconditions. No return value.
- **Postcondition:** the identified failing assertion.
- **Preconditions:** a selection of passing asserts in the original method at or before the failure site — if you want to use a fact that isn't yet asserted there, go assert it in the original first; if the assert passes, you may include it, if it fails, the fact does not actually hold there and is not a valid precondition. Pick the **minimal** subset of those passing asserts that you believe should suffice.
- **Body:** `pass`.
2. **Output.** Hand Phase 3 the candidate file `<method>_repro.py`. Phase 2 does not edit the original source.
3. **Log.** One log entry with `Phase: reduce`, fields: `Precondition count`.

## Phase 3: Fix

### Verify the candidate

Make the candidate verify. Apply the same probing technique as Phase 2's locate stage: add asserts and run the verifier. When the body needs real proof machinery, consult `references/proof-construction.md` for proof techniques.

There are three possible outcomes:

- **Nothing required.** The reduced context proved the failing fact for free. Promote the candidate to a lemma and apply it in the original method.
- **Just asserts.** A flat sequence of `Assert(...)` statements (or non-recursive lemma calls) makes the body verify. Try inlining them at the failure site in the original method. If that verifies, no lemma is needed — delete the candidate file. If not, promote to a lemma and call it.
- **Real proof machinery.** The body needs induction, fuel decrement, `Unfolding`, case analysis, or recursive lemma calls. Promote to a lemma and call it from the original method.

### Lemma promotion procedure

Promotion is mostly mechanical: the candidate is already a verified, lemma-shaped function. This step just gives it a permanent home.

**File conventions.** Lemmas live in a separate file `lemma_<lemma_name>.py` (same directory as the source) and are imported into the original file. If the lemma needs predicates or pure functions defined in the source file, extract those shared definitions into a `<source_file_name>_definitions.py` file first (to avoid circular imports) and have both files import from it. Check whether a `_definitions.py` file already exists before creating a new one.

**Procedure.**
1. Rename the Phase 2 candidate `<method>_repro.py` to `lemma_<lemma_name>.py`. By default the lemma is a regular method; use `@Pure` only when the lemma must be invoked from a pure context (inside another `@Pure` function, a predicate body, or any other place that admits only pure expressions).
2. Import the lemma into the source file and invoke it where the missing step is. Continue verifying the original method.

# Stuck criteria

Verification iteration is bounded; recognise stuck-ness early so the budget is not burned on the same wrong direction:

- **Same verification error on the same source line twice in a row.** The next attempt must be a Phase 2 probing step (not another fix). A repeated identical error means the previous fix did not address the actual missing step; probing will reveal where the missing step actually sits.
- **Same verification error on the same source line three times in a row.** Stop iterating. Report the missing step you have identified, the strategies tried, and your best hypothesis for why it is hard to discharge. Recommend whether the spec needs redesign, whether a proof technique is needed, or whether the limitation is a Nagini bug.

These criteria are checks on the structured log, not on intuition. If two consecutive log entries record the same error code at the same line, the next entry must have `Phase: probe`.

# Resources

## references/debugging-examples.md
Four worked debugging examples showing the full diagnosis process in Nagini/Python syntax: permission leak in loop, missing fold before return, self-framing violation, weak loop invariant. Each example includes a **quick-check pattern summary** for rapid diagnosis.

## references/proof-construction.md
Generic reference for proving lemma bodies in Nagini: proof-writing discipline (add only what the failure shows is missing; never pre-plan), proof techniques (structural induction, fuel-based induction, case analysis, proof chaining), the fuel-based recursion pattern, and the lemma catalog (content, preservation, equivalence, bound, monotonicity, stability) as a vocabulary for the kind of fact you are proving.

# Appendix: Symptom Diagnostic Table

Quick-reference for mapping a verification error or symptom to its likely cause and concrete fix. The Phase 1-2 procedure remains the disciplined approach; this table only catalogs symptom→cause→fix pairs and assumes you have already isolated the failing assertion.

| Symptom | Common causes | Fix with code edits | Fix annotations only |
|---|---|---|---|
| "Postcondition might not hold" | **Self-framing**: value postcondition appears before `Acc()` for that field; **missing Fold**: predicate postcondition needs `Fold()` before return; **weak invariant**: loop doesn't carry enough info to the postcondition | Reorder `Acc()` before value postconditions, add `Fold()` before return, strengthen loop invariants | Same; also check that `Acc()` precedes every field reference in `Ensures` |
| "Insufficient permission to access {field}" | **Predicate not unfolded**: permission is inside a folded predicate; **consumed by fold**: `Fold(pred(x))` consumed `Acc(x.field)`; **consumed by call**: callee took permission but didn't return it; **not in loop invariant**: permission dropped on back-edge | Add `Acc()` to precondition or loop invariant; add `Unfold` before access | Same |
| "Fold might fail" | Missing field permission; missing nested predicate instance; value constraint not yet established | Establish all required permissions and constraints before `Fold` | Add assertions to establish predicate body; adjust predicate definition if a component is missing |
| "Unfold might fail" | The predicate instance is not held at this point (never acquired, or already consumed) | Ensure the predicate instance exists before `Unfold` | Same |
| "Contract might not be well-formed" | Postcondition or precondition references a field without a preceding `Acc()` for it (self-framing violation) | Reorder or add `Acc()` in contracts so every `Acc(x.f)` precedes any expression that reads `x.f` | Same |
| "Predicate body might not be well-formed" | Predicate definition reads a field without `Acc()` for it | Fix the predicate definition so each field access has a corresponding `Acc()` | Same |
| Loop invariant not established (fails before loop) | Invariant is false or permissions are absent before the loop starts | Establish invariant before loop or adjust initialization | Adjust invariant to match pre-loop state; add `Fold`/`Assert` before loop |
| Loop invariant not preserved (fails at end of body) | Missing update in loop body; inductive step needs a lemma | Strengthen invariant or fix loop body | Strengthen or weaken invariant; add `Fold`/`Unfold` inside loop body |
| "Precondition might not hold" / call might fail | Caller doesn't establish what the callee requires | Establish the missing precondition before the call | Same |
| Method verifies but caller fails | Postcondition too weak — caller needs a guarantee the method doesn't provide | Strengthen postcondition | Same |
| Fact about a field/container provable before a call, unprovable after it (`state.store` shows the value re-assigned across the call) | Callee's `Ensures` re-grants permission to the location without stating value/content preservation — the call havocs it | Add the frame condition to the callee's `Ensures` (e.g. `ToSeq(x.xs) == Old(ToSeq(x.xs))`) | Report as a contract weakness — a missing frame condition cannot be recovered caller-side |
| Error disappears when unrelated code is added | Self-framing — the extra code incidentally provides a needed permission | Make the permission explicit in the contract | Same |
| "Function might not terminate" | Missing or incorrect termination measure | Add or fix `Decreases()` on the function/method | Same |
| A fact about an `int` that is numerically obvious fails | `x` is not known to be exactly `int` (static type `int` admits subclasses such as `bool`) | Same as annotations | Thread `type(x) == int` through the contracts |
