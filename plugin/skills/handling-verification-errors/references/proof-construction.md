# Proof Construction

Patterns and techniques for writing proof annotations in Nagini — loop invariants and lemma bodies — when the SMT solver needs explicit help.

## Writing proofs

When writing a proof body to make a lemma verify, follow these two rules:

**Add only what the failure shows is missing.** Read the verifier's error carefully — it tells you what the solver doesn't know. Common patterns:

- **Missing case distinction**: add an `if`/`else` matching the structure
- **Missing recursive fact**: add one recursive lemma call (often on a smaller part of the structure)
- **Missing predicate contents**: add an `Unfold(...) ... Fold(...)` block

Verify after each addition. Stop as soon as verification succeeds.

**Never pre-plan a full proof.** Do not look at the lemma and think "this will need induction with three cases and two helper lemmas" before trying anything. That reasoning leads to proof bloat. Let the verifier fail first, then react to what it actually needs.

---

## Loop Invariant Structure

A complete set of loop invariants typically covers:
1. **Bounds**: `0 <= i and i <= n`
2. **Permissions**: `Acc(list_pred(items))` or `Acc(obj.field)`
3. **Progress property**: what has been computed for elements `[0..i)`
4. **Current state**: properties of loop variables
5. **Pure function facts**: restate pure-function preconditions the loop body needs (e.g., `Invariant(is_sorted(ToSeq(a)))`)

---

## When the Verifier Needs Help

The SMT solver struggles with:

- **Inductive properties**: Properties over recursive structures require explicit induction
- **Multi-step heap reasoning**: Following pointer chains through predicates needs unfolding guidance
- **Recursive function properties**: Properties relating recursive calls at different fuel levels
- **Cross-predicate reasoning**: Connecting facts about different predicates or abstract states

**Signal that you need a proof**: verification fails even though the property is intuitively true, and no amount of assertion/invariant strengthening fixes it.

---

## Lemma Functions

A **lemma** is a function whose preconditions state assumptions, postconditions state the conclusion, and the body is the proof.

**Default form: regular method.** Because lemmas are normally called from method bodies, most lemmas can simply be methods themselves.

**`@Pure`lemmas:** If the lemma needs to be applied inside a *pure context* — i.e., inside another `@Pure` function's body, inside a predicate, or anywhere only pure expressions are allowed — define it as `@Pure` returning `bool` and write the proof as an expression:

```python
@Pure
def lemma_property_name(params: Type) -> bool:
    Requires(assumptions)
    Ensures(conclusion)

    return True
```

---

## Proof Techniques

### Structural Induction

Unfold to expose structure, recurse on substructure, let the verifier combine the result.

```python
def lemma_structural(x: Optional[Node]) -> None:
    Requires(predicate(x))
    Ensures(predicate(x))
    Ensures(property(x))

    if x is None:
        pass
    else:
        Unfold(predicate(x))
        lemma_structural(x.child)
        Fold(predicate(x))
```

**Why it works**: Each recursive call operates on a strictly smaller predicate instance exposed by `Unfold`. The base case needs no recursion.

**Common uses**: element membership, invariant preservation, function equivalence, size bounds.

#### Nagini example (list length non-negative)

```python
def lemma_length_nonneg(node: Optional[Node]) -> None:
    Requires(lseg(node))
    Ensures(lseg(node))
    Ensures(lseg_length(node) >= 0)

    if node is None:
        pass
    else:
        Unfold(lseg(node))
        lemma_length_nonneg(node.next)
        Fold(lseg(node))
```

### Case Analysis

Split the proof into cases, proving the property separately in each.

```python
def lemma_by_cases(x: int, y: int) -> None:
    Requires(precondition(x, y))
    Ensures(conclusion(x, y))

    if condition1:
        pass
    elif condition2:
        pass
    else:
        lemma_general(x, y)
```

### Proof Chaining

Multiple lemma calls in sequence, each building on the previous:

```python
def lemma_chained(params: Type) -> None:
    Requires(preconditions)
    Ensures(conclusion)

    lemma_a(params)
    lemma_b(params)
```

### Loop-Based Universal Proofs

To prove `forall i :: P(i)`, iterate and call per-element lemmas:

```python
k: int = 0
while k < size:
    Invariant(0 <= k and k <= size)
    Invariant(Forall(int, lambda j: (
        Implies(0 <= j and j < k, P(j)),
        [[P(j)]]
    )))
    lemma_p(data, k)
    k += 1
```

---

## Fuel-Based Recursion Pattern

When defining recursive functions over non-recursive data (arrays, sequences), use an explicit **fuel** parameter to bound recursion depth.

1. **Bounded function** `funcB(data, x, fuel)` — recurses with decreasing fuel, returns default at fuel=0
2. **Wrapper function** `func(data, x)` — calls `funcB` with `|data|` as sufficient fuel
3. **Monotonicity lemma** — proves `funcB(x, fuel) == funcB(x, fuel + 1)` when fuel is sufficient
4. **Stability lemma** — proves `funcB(x, fuel1) == funcB(x, fuel2)` when both sufficient

The monotonicity and stability lemmas are essential. Without them, the verifier can't relate `funcB(x, fuel)` to `funcB(x, fuel + k)`.

---

## Lemma Catalog

### Content Lemma

**Purpose**: Prove a data structure contains/represents certain values (element membership, sequence representation).

**When needed**: Relating two recursively-defined functions — the solver can't prove this automatically.

```python
def lemma_contains_in_elems(head: Optional[Node], v: int) -> None:
    Requires(lst(head))
    Requires(list_contains(head, v))
    Ensures(lst(head))
    Ensures(v in elems(head))

    if head is None:
        pass
    else:
        Unfold(lst(head))
        if head.elem != v:
            lemma_contains_in_elems(head.next, v)
        Fold(lst(head))
```

### Preservation Lemma

**Purpose**: Prove a local structural invariant entails a global property.

**When needed**: Predicate encodes local invariant (e.g., adjacent-pair ordering) and you need a global consequence.

```python
def lemma_sorted_all_geq_head(head: Node, v: int) -> None:
    Requires(sorted_list(head) and head is not None)
    Requires(v in sorted_elems(head))
    Ensures(sorted_list(head))
    Ensures(Unfolding(sorted_list(head), v >= head.elem))

    Unfold(sorted_list(head))
    if v != head.elem and head.next is not None:
        lemma_sorted_all_geq_head(head.next, v)
    Fold(sorted_list(head))
```

### Equivalence Lemma

**Purpose**: Prove two expressions compute the same value.

**When needed**: Relating two recursively-defined views of the same structure.

```python
def lemma_length_equiv(head: Optional[Node], acc: int) -> None:
    Requires(lst(head))
    Ensures(lst(head))
    Ensures(length_tr(head, acc) == length(head) + acc)

    if head is None:
        pass
    else:
        Unfold(lst(head))
        lemma_length_equiv(head.next, acc + 1)
        Fold(lst(head))
```

**Pitfall**: The postcondition must generalize over `acc`. The inductive step requires the generalized form.

### Bound Lemma

**Purpose**: Prove a value is within a range (height ≤ size, length ≥ 0).

```python
def lemma_height_bounded_by_size(node: Optional[TreeNode]) -> None:
    Requires(tree(node))
    Ensures(tree(node))
    Ensures(height(node) <= size(node))

    if node is None:
        pass
    else:
        Unfold(tree(node))
        lemma_height_bounded_by_size(node.left)
        lemma_height_bounded_by_size(node.right)
        Fold(tree(node))
```

### Monotonicity Lemma (fuel-based)

**Purpose**: Prove a fuel-bounded function returns the same result with more fuel, once it has enough.

```python
def lemma_root_more_fuel(parent: List[int], x: int, fuel: int) -> None:
    Requires(well_formed(parent) and valid_index(parent, x))
    Requires(fuel >= 0 and reaches_root(parent, x, fuel))
    Requires(MustTerminate(fuel + 1))
    Ensures(root_b(parent, x, fuel) == root_b(parent, x, fuel + 1))

    if not is_root(parent, x):
        lemma_root_more_fuel(parent, parent[x], fuel - 1)
```

### Stability Lemma (fuel-based)

**Purpose**: Prove the result is the same for any two sufficient fuel levels.

```python
def lemma_depth_stable(parent: List[int], x: int, fuel1: int, fuel2: int) -> None:
    Requires(well_formed(parent) and valid_index(parent, x))
    Requires(0 <= fuel1 and fuel1 <= fuel2)
    Requires(reaches_root(parent, x, fuel1))
    Requires(MustTerminate(fuel1 + 1))
    Ensures(depth_b(parent, x, fuel1) == depth_b(parent, x, fuel2))

    if not is_root(parent, x):
        lemma_depth_stable(parent, parent[x], fuel1 - 1, fuel2 - 1)
```

**Pitfall**: Recurse on `fuel1`, not `fuel2`. Only `fuel1` is guaranteed to reach 0.
