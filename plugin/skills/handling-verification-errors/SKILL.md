---
name: handling-verification-errors
description: Nagini debugging and error handling reference. Provides strategies for interpreting Nagini error messages, diagnosing verification failures, and iterating on specs and code to fix issues. Use this skill when you encounter verification errors in Nagini and need to understand and resolve them.
---

# Guiding Principle

- Never make assumptions about the cause of a verification error without evidence. Use the systematic techniques described here to gather information and isolate the true cause to fix the underlying issue.
- When fixing, add only what the evidence shows is missing: each addition responds to a located missing step, and each new failure gets the same diagnostic read.
- Never pre-plan a full proof ("this will need induction, three cases, two helper lemmas") — that leads to proof bloat. Let the verifier fail first, then react to what it actually needs.
- Never weaken or delete a contract just to make verification pass; surface the mismatch instead.

The verifier is reasonably powerful: it should practically always be possible to verify code with the correct specifications, so a correct-looking specification that fails usually means a missing intermediate assertion or lemma, not a limitation. The known limitations are listed in the `nagini-language` skill's limitations reference.

# Debugging strategies

Understand the failure before fixing it: every fix responds to evidence gathered by the strategies below.

- **Probe asserts** — reduce the error to a single failing assertion and measure which facts the solver can derive around it.
<!-- if errors -->
- **Interrogate the verifier** — extract what the verifier saw and did at the narrowed failure: the symbolic state, the solver's reason for giving up, the encoding.
<!-- end -->
- **Minimal reproduction** — capture the missing step in a self-contained candidate file and attack it in isolation.

Any step along the way may already explain or resolve the problem, so re-verify as you go and stop when it does. The strategies also compose: apply several at once when useful, and return to any of them as new evidence arrives. It is also always possible that the state genuinely does not entail the fact you are asserting. No amount of solver help can fix that; it usually requires changes to contracts or loop invariants.

## Probe asserts

First reduce the error to a single failing assertion:

**For method calls**: Assert the preconditions of the callee before the call to find out which one fails.

**For loop invariants**: Assert the loop invariants, either before the loop or at the end of the loop body, to determine which invariant clause is not being established or preserved.

**For branches/multiple returns**: Do *not* assume which branch is the problem. Add asserts to each branch / before each return to find out which one fails.

**For a whole-run timeout** (`TimeoutOccurred`, no position, no diagnostics): localize manually by commenting out proof obligations until the run completes, or inserting `Assert(False)` before a suspect obligation to confirm the run reaches it. Everything after `Assert(False)` verifies vacuously, so walking it down the body and diffing the durations shows which region the time belongs to. A whole-run timeout means you have a performance problem to solve: switch to the `nagini-performance` skill and address it before resuming ordinary fix iteration.

**Separate conjunctions**: If the error occurs for a conjunction of properties, determine which clause is failing:
- Multiple postconditions/invariants: assert each individually
- Assertions with multiple conjuncts: split into separate asserts
- Method calls with multiple preconditions: assert each precondition separately before the call

Then diagnose **what** the solver cannot derive: to further understand the failure and also help it with explicit intermediate facts, insert additional assertions before the failing one and re-run the verifier. Insert several `Assert(...)` probes at once. Every passing probe confirms a fact the solver knows; the first failing one pinpoints the missing step. 

Often the probes themselves are the fix. A few well-placed `Assert(...)` statements give the solver the intermediate facts (or quantifier triggers) it needs to discharge the original goal. When that happens, you are done: keep the asserts that hold the verification together and skip creating and verifying a candidate.

### Choosing probe asserts

To pick candidate intermediate facts to probe with, use the patterns below. You can use multiple strategies at once.

<!-- if errors -->
**Explicit failing SMT-queries**: the `failedAssertion` term (see below) is the exact obligation the solver could not prove. Translate it back to Python and assert it before the failing point.
<!-- end -->

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

<!-- if errors -->
`state.heap` at the failure already gives you the acquired-minus-consumed inventory for free; trace manually to find *which statement* along the path consumed a chunk the heap read showed missing.
<!-- end -->

<!-- if errors -->
## Interrogate the verifier

The failing diagnostic carries evidence (the location, the `message`, the `reason`, and the `debug` payload), and the verify tools produce more of it on demand: re-verification with different flags or budgets, the untruncated archive, the Viper encoding. Use them actively: every question of the form "what did the verifier actually see or do here?" has a tool answer.

Often, it is useful to pass `include_viper: true` to any verify tool to get the translated Viper program as `viperProgram`. How an operator, builtin, or contract clause is actually encoded determines what the solver can possibly derive about it. Even small files translate to hundreds of lines, so ideally request it on a reduced snippet, not the full module.

If a failing diagnostic has no `debug` field, the server was launched without SMT-state collection; pass the required `viper_args` (`--smtStateOnError` and `--reportReasonUnknown`) yourself.

Each failing diagnostic's `debug` object contains the symbolic state at the failure, expressed in the verifier's internal term language:

| Field | Content | Use it to |
|---|---|---|
| `failedAssertion` | The exact goal term the solver could not prove | See the obligation as the solver sees it (after encoding), not as you wrote it |
| `failedAssertionPretty` | The same goal with `@line@col` suffixes stripped and `_checkDefined` shims unwrapped | Read the goal quickly; fall back to the raw term when versions matter |
| `reasonUnknown` | Why the solver returned unknown (see table below) | **Choose the fix strategy** |
<!-- if timeouts -->
| `rlimitDelta` | Prover resources the failing check consumed, in Z3 rlimit units (the budget is `assertTimeout` ms × 9000) | A delta at the budget means the cap bound the check; a delta well below it means the solver stopped on its own |
<!-- else -->
| `rlimitDelta` | Prover resources the failing check consumed, in Z3 rlimit units | Compare across probes: a delta that grows with the proof context means the check is budget-bound; a small one means the solver stopped on its own |
<!-- end -->
| `assumptions` | Path-condition terms in scope at the failure, pre-filtered to those sharing a symbol with `failedAssertion` (an `omitted` marker counts the rest) | Scan for gross absences and anomalies. To test whether a specific fact is available, probe it with `Assert` — presence in this list is neither necessary nor sufficient for derivability |
| `branchConditions` | The branch decisions leading to the failing path | Identify which control-flow path fails |
| `state.store` / `state.heap` / `state.oldHeaps` | Local variables, and the heap as a list of chunks (`resource(receiver; snapshot, permission)`) | Trace which symbolic value a variable holds; spot havocked (freshly re-assigned) values after calls; see which permissions the path actually holds |

Bulk fields — the full SMT session (`proverEmits`), the background axioms (`preambleAssumptions`), and the symbol declarations (`functionDecls`/`macroDecls`) — are collected and archived server-side. Oversized results also are truncated in `debug` and noted in the payload's `omitted` map. The result's top-level `recordedAt` names this run's archive directory, and `Read`ing its `result.json` gives the untruncated payloads. Whenever an `omitted` marker hides a field the diagnosis needs, read the archive instead of reasoning around the gap.

Reading terms: `x@3@05` is a symbolic constant for program variable `x` (numbers are internal versions — successive assignments create new versions). Integers are boxed: `__prim__int___box__`/`int___unbox__` wrap between Python ints and SMT ints, and `_checkDefined(_, x, id)` wraps variable reads (it is identity on the value). `QA x :: body` is a universal quantifier. Pure functions appear applied to a snapshot argument first (`ipow(_, b, e)`).


### Interpreting `reasonUnknown`
For most failures, start by understanding why the SMT-query failed, which is given in the `reasonUnknown` field:

| Value | Meaning | Strategy |
|---|---|---|
| `(incomplete quantifiers)` | E-matching gave up: the instantiation chain to the proof was never triggered (under-instantiation). More solver time will not help. | If the failing goal is numerically obvious over ints, check the int-identity trap. Otherwise restate the missing fact as a GROUND fact placed where it is always visible: as a postcondition or a local `Assert`. Add only facts the payload shows are missing: speculative extra ground facts feed the instantiation engine and can slow everything down. For quantified goals, also check TRIGGER VOCABULARY: do the premise quantifiers' trigger terms occur under the goal's binder? If not, add a bridging quantified `Assert` whose trigger matches the goal's vocabulary and whose body mentions the premise triggers. |
<!-- if timeouts -->
| `canceled` | The budget ran out while the solver was still working. | One diagnostic probe is worth it: re-run once with ~10x `assertTimeout` and read `rlimitDelta`. If it stops well below the new budget (reason flips to an incompleteness class), time was never the issue. If it scales with the budget, the proof is genuinely slow — apply the `nagini-performance` skill's budget policy and strategies. |
<!-- end -->
| `(incomplete (theory arithmetic))` | Nonlinear integer arithmetic (products, `//`, `%` of variables) is beyond the solver. | More time will not help. Restate the proof with stepping stones that avoid division/modulo OF PRODUCTS entirely: use the Euclid identity (`a == (a // d) * d + a % d`), pure polynomial identities (products may appear; the solver normalizes them), and the bounded-multiple inference (`0 <= m * d < d` implies `m == 0`). `(k * d) // d == k` and `(k * d) % d == 0` are NOT directly provable — derive them via the chain above. |

### The int-identity trap

A special case of `(incomplete quantifiers)` worth checking before anything else: the failing fact is *numerically obvious* over ints — `PSeq(y) == PSeq(x)` from `y == x`, a `f(y)` fact not transferring to `f(x)` for `@Pure` `f`, `x in s` from `1 in s and x == 1`, a goal embedding `(1 if v == x else 0)`. The cause is that `x` is not known to be exactly `int` (the static type admits subclasses such as `bool`), so `==` gives value equality but not the object identity these positions need — semantics and failing shapes in the `nagini-language` reference, Integers → Typing.

The fix: ensure the type of the variables involved is exactly `int`, excluding subtypes, via **`type(x) == int`**. State it where you state any other fact about `x`, and carry it along like a permission.

| Place | Write |
|---|---|
| `int` parameter | `Requires(type(x) == int)` |
| `int` return value | `Ensures(type(Result()) == int)` |
| `int` field | `type(self.n) == int` next to `Acc(self.n)` in the predicate / postcondition of `__init__` |
| contents of a `List[int]` / `Set[int]` / `PSeq[int]` | `Forall(xs, lambda e: (type(e) == int, []))` in the same pre/post/invariant as `list_pred(xs)` — the element form; it is preserved across `append` of exact ints and through loops that build the list, whereas the index form `Forall(int, lambda i: Implies(0 <= i and i < len(xs), type(xs[i]) == int))` needs extra frame assertions after each mutation |
| loop counter / accumulator | `Invariant(type(i) == int)` (preserved by `i += 1`) |
| `Forall(int, ...)` whose body identifies `i` (membership, `@ContractOnly`) | add `type(i) == int` to the guard: `Implies(type(i) == int and lo <= i and i < hi, ...)`. The guard then has to be discharged at every use: the concrete index must carry its own `type(x) == int` fact (parameter: `Requires`; local: `Assert`), or the instantiation silently fails. Leave the guard out when the body does not need it |

If no `type(x) == int` fact can be carried to a use site (e.g. an element read from a `List[int]` verified without an element-type invariant), use the fact that every arithmetic result is exactly `int`: `f(x + 0)` supports the identity reasoning that `f(x)` lacks. A local rescue only, for when proper typing is not possible.

### Interpreting `state.heap`
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
Worked payload reads — a fact failure and a permission failure — are in `references/debugging-examples.md`.
<!-- end -->

## Minimal reproduction

When the missing fact resists inline asserts and digging into the diagnostics does not provide a solution, capture the failure in a minimal, self-contained Python file and attack it in isolation.

After locating the facts that hold at the failure site (every probe assert that passed) and the one that doesn't (the failing fact), create a **candidate lemma**: holding facts become preconditions, the failing fact becomes the postcondition, the body starts as `pass`.

A **lemma** is a function whose preconditions state assumptions, postconditions state the conclusion, and the body is the proof. Lemmas are always `@Ghost` and always carry a termination measure; the technique templates in `references/proof-techniques.md` show only the proof structure and omit that boilerplate. A pure lemma returns `bool` with the proof written as an expression:

```python
@Ghost
@Pure
def lemma_property_name(params: Type) -> bool:
    Requires(assumptions)
    Ensures(conclusion)

    return True
```

**Procedure.**

1. **Build the candidate.** Create `<method>_repro.py`. Define a fresh function with:
- **Parameters:** exactly the variables referenced in its pre- and postconditions. No return value.
- **Postcondition:** the identified failing assertion.
- **Preconditions:** a selection of passing asserts in the original method at or before the failure site — if you want to use a fact that isn't yet asserted there, go assert it in the original first; if the assert passes, you may include it, if it fails, the fact does not actually hold there and is not a valid precondition. Pick the **minimal** subset of those passing asserts that you believe should suffice.
- **Body:** `pass`.
2. **Verify the candidate.** Make it verify without editing the original source:
<!-- if errors -->
probe asserts and interrogation apply to the candidate exactly as to the original.
<!-- else -->
probe asserts apply to the candidate exactly as to the original.
<!-- end -->
When the body needs real proof machinery, consult `references/proof-techniques.md` for the technique templates.

There are three possible outcomes:

- **Nothing required.** The reduced context proved the failing fact for free. Promote the candidate to a lemma and apply it in the original method.
- **Just asserts.** A flat sequence of `Assert(...)` statements (or non-recursive lemma calls) makes the body verify. Try inlining them at the failure site in the original method. If that verifies, no lemma is needed — delete the candidate file. If not, promote to a lemma and call it.
- **Real proof machinery.** The body needs induction, fuel decrement, `Unfolding`, case analysis, or recursive lemma calls. Promote to a lemma and call it from the original method.

### Lemma promotion procedure

Promotion is mostly mechanical: the candidate is already a verified, lemma-shaped function. This step just gives it a permanent home.

**File conventions.** Lemmas live in a separate file `lemma_<lemma_name>.py` (same directory as the source) and are imported into the original file. If the lemma needs predicates or pure functions defined in the source file, extract those shared definitions into a `<source_file_name>_definitions.py` file first (to avoid circular imports) and have both files import from it. Check whether a `_definitions.py` file already exists before creating a new one.
**Contract interface.** Phrase the contract so that instantiation lands on the caller's exact goal terms. Often it is better to take those expressions as parameters instead of baking their values in as constants: a conclusion over a constant leaves the caller to rewrite its term into that shape in its own, expensive context. The same principle cuts the other way: every heavy term the contract mentions must be proven or is re-imported at each call site.

**Procedure.**
1. Rename the candidate `<method>_repro.py` to `lemma_<lemma_name>.py`. 
By default the lemma is a `@Ghost` method. Use `@Ghost @Pure` with `Decreases` only if the lemma must be invoked from a pure context (inside another `@Pure` function, a predicate body, or any other place that admits only pure expressions).
2. Import the lemma into the source file and invoke it where the missing step is. Continue verifying the original method.

## Function unrolling and concrete-value obligations

Some proof obligation (in particular concrete-value facts) may require multiple unfoldings of a pure function. The verifier by default unfolds a pure function only once per syntactic application, so such assertions may fail or time out.

For example, consider a digits function that returns its digits via `PSeq(n % 10) + digits(n // 10)` for a given integer. An assert like `Assert(digits(1234) == PSeq(4, 3, 2, 1))` may fail. The solution is to break the proof into asserts that each need a single unfolding, from the innermost value outward:

```python
Assert(digits(1) == PSeq(1))
Assert(digits(12) == PSeq(2, 1))
Assert(digits(123) == PSeq(3, 2, 1))
Assert(digits(1234) == PSeq(4, 3, 2, 1))
```

If the same value is needed in several places, or the chain is long enough to slow down the enclosing method, move it into a lemma so it is proved once and only its conclusion is used.

Alternatively, there is a trick that removes the per-application limit for a single function: a quantified `Assert` whose trigger is the function application and whose body also contains the function. The body must be a true, non-trivial fact that contains the function, for example, the function's own postcondition:

```python
Assert(Forall(int, lambda n: (Implies(n >= 0, len(digits(n)) >= 1), [[digits(n)]])))
Assert(digits(1234) == PSeq(4, 3, 2, 1))
```

Why it works: the body is unrolled once, this contains the recursive application, which triggers the quantifier again, which repeats the process one unfolding deeper. Caution: unconstrained function unrolling can lead to performance problems, in particular the solver will diverge if the such a function is applied to unconstrained symbolic arguments.

## Dead ends
Report a dead end only once the strategies above are exhausted and no longer produce new evidence about the failure.

<!-- if errors -->
Demonstrate it with a minimal snippet pair: the minimal failing shape and all the collected evidence about what fails on which layer (encoding, SMT) and why.
<!-- else -->
Demonstrate it with a minimal snippet pair: the minimal failing shape and all the collected evidence about what fails and why.
<!-- end -->

Recommend whether the spec needs redesign, whether a proof technique is needed, or whether the limitation is a Nagini bug.

# Resources

## references/debugging-examples.md
<!-- if errors -->
Worked debugging examples: two payload reads (a fact failure and a permission failure) and three full diagnose-probe-fix arcs in Nagini/Python syntax — permission leak in loop, weak loop invariant, and bridging index-based to value-based sequence reasoning with an inductive lemma pair.
<!-- else -->
Worked debugging examples: three full diagnose-probe-fix arcs in Nagini/Python syntax — permission leak in loop, weak loop invariant, and bridging index-based to value-based sequence reasoning with an inductive lemma pair.
<!-- end -->

## references/proof-techniques.md
Proof-technique templates for lemma bodies — structural induction, case analysis, proof chaining, loop-based universal proofs — and the lemma catalog (content, preservation, equivalence, bound) as a vocabulary for the kind of fact you are proving.

# Appendix: Symptom Diagnostic Table

Quick-reference for mapping a verification error or symptom to its likely cause and concrete fix. The strategies above remain the disciplined approach; this table only catalogs symptom→cause→fix pairs and assumes you have already isolated the failing assertion.

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
<!-- if errors -->
| Fact about a field/container provable before a call, unprovable after it (`state.store` shows the value re-assigned across the call) | Callee's `Ensures` re-grants permission to the location without stating value/content preservation — the call havocs it | Add the frame condition to the callee's `Ensures` (e.g. `ToSeq(x.xs) == Old(ToSeq(x.xs))`) | Report as a contract weakness — a missing frame condition cannot be recovered caller-side |
<!-- else -->
| Fact about a field/container provable before a call, unprovable after it | Callee's `Ensures` re-grants permission to the location without stating value/content preservation — the call havocs it | Add the frame condition to the callee's `Ensures` (e.g. `ToSeq(x.xs) == Old(ToSeq(x.xs))`) | Report as a contract weakness — a missing frame condition cannot be recovered caller-side |
<!-- end -->
| The goal relates a recursive function's values at different arguments (`f(xs)` vs `f(xs.drop(1))`) | The solver does not discover induction; the connecting fact needs an explicit inductive step | Add one recursive lemma call on the smaller structure (proof-techniques: Structural Induction) | Same |
