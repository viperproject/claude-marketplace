# Proof Techniques

## Structural Induction

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

### Nagini example (list length non-negative)

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

## Case Analysis

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

## Proof Chaining

Multiple lemma calls in sequence, each building on the previous:

```python
def lemma_chained(params: Type) -> None:
    Requires(preconditions)
    Ensures(conclusion)

    lemma_a(params)
    lemma_b(params)
```

## Loop-Based Universal Proofs

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

## Formulation Diversity

Before reporting a lemma or postcondition as unprovable, attempt at least two structurally different formulations: change the induction variable, generalize the hypothesis with an accumulator, or restate over one combined sequence/value instead of relating two.

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

