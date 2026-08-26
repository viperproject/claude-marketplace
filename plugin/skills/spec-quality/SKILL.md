---
name: spec-quality
description: Specification quality principles for Nagini verification. Covers predicate design, correctness properties, and method contract completeness. Use when designing or reviewing specifications for strength and completeness.
---

# Specification Quality

Specifications here does not refer to loop invariants, lemmas or intermediate assertions. These are part of the verification of the implementation. Specifications refer to the method contracts (pre/postconditions) and the predicates and pure functions used in those contracts.

There are two main parts to good specifications:
- A good vocabulary (predicates, pure functions) that enables reasoning and proofs
- Strong, complete specifications that capture the intended behavior and properties of the program using that vocabulary

## Vocabulary

Designing the vocabulary depends heavily on the problem domain. It often includes:

- **Abstract state model**: which mathematical object (`PSeq`, `PSet`, `int`, ...) each data structure is abstracted to, and how concrete state maps to it (see Pure Functions)
- **Permission footprint**: which predicates own which parts of the heap, and where fractional permissions are needed (see Predicates)
- **Structure invariants**: properties that hold across all methods (e.g. sortedness of an internal list) — decide once where they are stated, in a predicate or over the pure representation, rather than repeating them in every contract

### Pure Functions

#### Purification

In most cases, it is better to reason over mathematical representations of objects rather than the heap structures directly. For example, a linked list can be represented as a mathematical sequence.

- If possible, there should be a way to map the heap structure to a pure mathematical representation. If using built-in data structures, this is often provided (and you should always use it if available). If not, you may need to write your own pure function to do this mapping.
- All remaining properties should be stated in terms of the pure representation, not the heap structure. This allows for clearer specifications and easier proofs.

#### Stating properties

Once a pure representation is available, most key functional properties (e.g. sortedness) can be stated in pure terms. Getting the functions properties right is discussed below.

#### Prefer built-ins over custom pure-function wrappers

Nagini ships verified contracts for many Python built-ins (`abs`, `max`/`min`, `len`, `x in xs`, `PSeq` operations). Use them directly in specs — do not write custom `@Pure` helpers that duplicate them (see the `nagini-language` skill: Built-in Functions with Verified Contracts).

Only write a custom pure function when no built-in covers the operation.

#### Opaque heavy definitions

When callers mostly need a few consequences of a pure function rather than the definition, mark it `@Opaque` and state those consequences in its `Ensures` (see Opaque pure functions in the `nagini-language` reference). The `Ensures` is then the whole caller-facing interface — design it to carry what contracts and invariants routinely need.

### Predicates

If using built-in data structures, this is usually not necessary. If designing your own data structures, then this is critical.

There are two options:
- Predicates bundle permissions only, with all functional properties stated in pure functions over the pure representation
- Predicates also capture functional properties (e.g., a `SortedList` predicate that includes both the structural invariant and the sortedness property)

The first approach is usually easier.

#### Permission accounting

Permissions are a conserved resource: each heap location has exactly one write unit in the whole system, split among callers, contracts, and folded predicates. Design the flow of that unit explicitly — where it sits before a call, during it, and after — and check that no point in the design requires more of a location than exists. Amounts must agree everywhere: a predicate's body, the contracts that fold it, and the postconditions that return it.

Reserve full permission for what is actually mutated; every other holder takes a fraction. Whenever more than one party needs the same state at the same time, decide the split deliberately rather than giving each party full access. If write-access is needed after a split, you must plan how to reassemble the pieces to the whole permission.

## Complete Correctness Properties

You need to understand:

- What are the correctness properties of the program?
- How can we express them using the vocabulary?

For example, for common algorithms:

- **Search**: returns the correct index when found, signals absence correctly when not
- **Sort**: output is sorted AND is a permutation of the input
- **Insert/delete**: element present/absent after operation, size changes by exactly one, other elements unchanged

### Method Contract Completeness

You should ensure for each method/function:

- **Return value**: fully characterize the result, not just a weak bound (e.g., `result == len(xs)` not just `result >= 0`)
- **Functional correctness**: capture the key algorithmic property
- **Termination**: `Decreases()` for pure functions, `MustTerminate` for methods/loops
- **Frame conditions**: describe the state that is preserved, not just what is changed
- **Permissions returned**: all permissions acquired in preconditions must be returned in postconditions (unless deliberately consumed)
- **Branch coverage**: all branches of conditionals should be covered by the postcondition, not just the happy path
- **Uncallable preconditions**: avoid preconditions that are so strong (or even unfeasible) that no call site could satisfy them
- **Triggers on quantified properties**: every `Forall` in a contract needs a well-chosen trigger.

### Frame Conditions

Every location the contract takes permission to is havocked by a call, even locations the body never touches. So for a caller to be able to reason after a call, the postcondition must characterize every location that the method takes permission to, in particular everything that is preserved:

- **Field**: `Ensures(self.f == Old(self.f))`
- **Reference identity**: a reference-typed field also loses *which object* it points to — state `Ensures(self.child is Old(self.child))`, not just value equality
- **Container contents**: preserving permissions preserves nothing about the values (see Old Values in the `nagini-language` reference). For example, in addition to `Acc(list_pred(self.xs))` you must also state `Ensures(len(self.xs) == Old(len(self.xs)) and ToSeq(self.xs) == Old(ToSeq(self.xs)))`.
- **Predicate-owned state**: preserve the pure representation, e.g. `Ensures(sl_seq(self) == Old(sl_seq(self)))`

Note that if only a fraction of a location is provided in the precondition, then framing guarantees that the values remain the same, so no `Old` equality is needed. However, facts about these values may not be immediately available to the verifier in the postcondition, so they may require restating as a postcondition. For example, if a postcondition calls a pure function that requires some condition fractionally-held state (e.g. a bound on the length), you may have to restate the condition as an explicit postcondition.

## Performance by Design

Contract and vocabulary shapes determine verification cost before any proof is written; see the `nagini-performance` skill for the cost model and the catalog of cheap shapes, and consult it while designing vocabulary and contracts.

## Proving Termination
Since each caller's measure must strictly dominate its callees', plan measures top-down over the bodies' call chains and leave slack rather than tight constants: a tight measure is brittle — one added recursive call or helper lemma forces bumps in every caller that passes a bound through and proving domination may itself require callee postconditions. For a non-recursive method, just pick a comfortably large constant.

Encoding a lexicographic ordering `(a, b)` into the single integer measure (there is no tuple form):
- When `b` has a proven bound `0 <= b < B` with `B` fixed across the recursion (a constant, or e.g. an unchanging `len(items)`): use `a * B + b`. Steps that decrease `a` may reset `b` freely; steps that keep `a` must decrease `b`. If `B` varies between levels the product becomes nonlinear arithmetic the solver may not discharge.
- Often simpler and more robust: one "remaining work" measure that strictly decreases on *every* recursive edge — e.g. the total count of unprocessed nodes in the whole structure, which shrinks both when descending into a child and when advancing to the next sibling.
- Avoid threading an explicit `fuel` parameter as the measure: fuel must also decrease on every recursive edge (not only structural descent), and it saddles every caller with fuel-sufficiency arithmetic in its preconditions — a size-based measure gives the same power without either cost.
