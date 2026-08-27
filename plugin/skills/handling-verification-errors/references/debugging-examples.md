# Debugging Examples

## Example: Permission Leak in Loop

**Pattern**: Insufficient permission after a loop that traverses a data structure.
**Quick checks**: (1) Loop invariant includes permissions for the traversed prefix. (2) Loop body extends the prefix correctly. (3) Permissions aren't consumed inside the loop without restoration.

### The Buggy Code

A method traverses a linked list to find an element, but the loop body doesn't preserve permissions for traversed nodes:

```python
from typing import Optional
from nagini_contracts.contracts import *

class Node:
    def __init__(self, value: int, next_node: Optional['Node']) -> None:
        Ensures(Acc(self.value) and self.value == value)
        Ensures(Acc(self.next) and self.next is next_node)
        self.value = value
        self.next = next_node

@Predicate
def lseg(node: Optional[Node]) -> bool:
    return Implies(node is not None, Acc(node.value) and Acc(node.next) and lseg(node.next))

def find(head: Optional[Node], target: int) -> bool:
    Requires(lseg(head))
    Ensures(lseg(head))

    Unfold(lseg(head))
    p: Optional[Node] = head

    while p is not None and p.value != target:
        Invariant(Implies(p is not None, Acc(p.value) and Acc(p.next)))
        Invariant(lseg(p.next) if p is not None else True)
        # BUG MISSING: Invariant tracking lseg from head to p
        next_p: Optional[Node] = p.next
        Unfold(lseg(next_p))
        # Permissions for p.value and p.next are LEAKED here
        p = next_p

    if p is not None:
        result = p.value == target
    else:
        result = False

    # ERROR: Fold might fail. There might be insufficient permission to access Acc(node.value)
    Fold(lseg(head))
    return result

```

### Error Message

```
Fold might fail. There might be insufficient permission to access Acc(node.value). (find.py@31.5)
```

### Diagnosis

**Read the diagnostic**: The verifier cannot fold `lseg(head)` because it can't find `Acc(head.value)`. Folding `lseg(head)` requires its body: `Acc(head.value)`, `Acc(head.next)`, and `lseg(head.next)`. For this failure class the `debug` payload answers directly: `state.heap` lists what the path holds at the failure, and a chunk present in `state.oldHeaps['old']` but absent from `state.heap` means it was consumed along the path.

**Reason about the gap**: Before the loop, we unfold `lseg(head)`, giving us `Acc(head.value)`, `Acc(head.next)`, and `lseg(head.next)`. The loop then advances `p` away from `head`. Each iteration unfolds the next node and moves `p` forward — but what happens to the previous node's permissions? The loop invariant only mentions `p`, nothing about `head` or any previously-visited nodes.

**Probe the verifier's state**:
```python
# Before the loop:
Assert(Acc(head.value))   # PASSES — permission exists here

# After the loop:
Assert(Acc(head.value))   # FAILS — permission is gone
```

This confirms the loop consumes `head`'s permissions without preserving them. Each iteration takes the current node's field permissions and moves on, but those permissions are never stored anywhere.

**Root cause**: The loop invariant doesn't track a prefix segment from `head` to `p`. Permissions for traversed nodes are consumed by the loop body (via unfold and reassignment) but never accumulated into a data structure the verifier can reason about.

### Fix

This requires a more complex traversal pattern that accumulates a prefix. In Nagini, a recursive approach is often simpler for linked lists:

```python
def find(head: Optional[Node], target: int) -> bool:
    Requires(lseg(head))
    Ensures(lseg(head))
    Ensures(Result() == lseg_contains(head, target))

    if head is None:
        return False

    Unfold(lseg(head))
    if head.value == target:
        Fold(lseg(head))
        return True

    result = find(head.next, target)
    Fold(lseg(head))
    return result
```

---

## Example: Weak Loop Invariant

**Pattern**: Postcondition fails after a loop, even though the loop body looks correct.
**Quick checks**: (1) The invariant is true but doesn't carry enough information. (2) Add "progress" made so far (e.g., prefix segment for partial traversal). (3) Add relationships between loop variables and original values. (4) Assert the needed postcondition immediately after the loop to confirm.

### The Buggy Code

Summing list elements but loop invariant doesn't track partial progress:

```python
from nagini_contracts.contracts import *
from nagini_contracts.obligations import MustTerminate
from typing import List

@Ghost
@Pure
def seq_sum(s: PSeq[int]) -> int:
    Decreases(len(s))
    if len(s) == 0:
        return 0
    else:
        return seq_sum(s.take(len(s) - 1)) + s[len(s) - 1]

@Ghost
def seq_sum_step(s: PSeq[int], i: int) -> None:
    Requires(MustTerminate(1))
    Requires(0 < i and i <= len(s))
    Ensures(seq_sum(s.take(i)) == seq_sum(s.take(i - 1)) + s[i - 1])

    Assert(s.take(i).take(len(s.take(i)) - 1) == s.take(i - 1))
    Assert(s.take(i)[len(s.take(i)) - 1] == s[i - 1])

def list_sum(a: List[int]) -> int:
    Requires(Acc(list_pred(a)))
    Ensures(Acc(list_pred(a)))
    Ensures(Result() == seq_sum(ToSeq(a)))

    total: int = 0
    i: int = 0

    while i < len(a):
        Invariant(Acc(list_pred(a)))
        Invariant(0 <= i and i <= len(a))
        # BUG: invariant doesn't say what total equals
        seq_sum_step(ToSeq(a), i + 1)
        total = total + a[i]
        i = i + 1

    return total
```

### Error Message

```
Postcondition of list_sum might not hold. Assertion Result() == seq_sum(ToSeq(a)) might not hold. (list_sum.py@7.5)
```

### Diagnosis

**Read the diagnostic**: The verifier can't prove `total == seq_sum(ToSeq(a))` at the return point, after the loop. In the `debug` payload this shows as `state.store` binding `total` to a fresh symbol version after the loop — the havoc signature of a variable modified in the loop but unconstrained by its invariant.

**Reason about the gap**: This requires understanding how the verifier reasons about loops. After a loop completes, the verifier *only* knows:
- What the loop invariant states
- That the loop guard is false (i.e., `i >= len(a)`)

All other information about variables modified in the loop is **discarded** (havocked). This is loop abstraction — the verifier doesn't replay loop iterations; it checks: (1) the invariant holds on entry, (2) assuming the invariant and the guard, the body re-establishes the invariant, and (3) after the loop, only the invariant plus the negated guard are known.

The invariant constrains `i` (bounds) and permissions (`list_pred(a)`), but says nothing about `total`. So after the loop, `total` is effectively arbitrary — the verifier has no information about it.

**Probe the verifier's state**: After the loop:
```python
Assert(i == len(a))                             # PASSES — from invariant (i <= len(a)) + negated guard (i >= len(a))
Assert(total == seq_sum(ToSeq(a).take(i)))      # FAILS — total is unconstrained
```

The verifier knows `i == len(a)` because that follows from the invariant and the negated guard. But it knows nothing about `total` because `total` is modified in the loop yet absent from the invariant.

**Root cause**: The loop invariant is too weak. Any variable modified in the loop body that needs to carry information to the postcondition must be constrained by the invariant. `total` is modified but unconstrained.

### Fix

Add the partial sum invariant:

```python
while i < len(a):
    Invariant(Acc(list_pred(a)))
    Invariant(0 <= i and i <= len(a))
    Invariant(total == seq_sum(ToSeq(a).take(i)))   # ADDED
    seq_sum_step(ToSeq(a), i + 1)
    total = total + a[i]
    i = i + 1
```

Now after the loop: `i == len(a)` and `total == seq_sum(ToSeq(a).take(i))`, so `total == seq_sum(ToSeq(a).take(len(a)))` which equals `seq_sum(ToSeq(a))`.

---

## Example: Bridging Index-Based and Value-Based Sequence Reasoning

**Pattern**: The verifier can reason about sequence elements by index (`s[i] == x` implies `x in s`) but cannot reason in the reverse direction (`x in s` implies some `s[i] == x`). A loop establishes index-based facts, but a lemma or postcondition requires value-based membership facts.
**Quick checks**: (1) Can the verifier prove `x in s` from `s[i] == x`? Yes — this direction works. (2) Can the verifier prove `not (x in s)` from `Forall(i, s[i] != x)`? No — this requires a lemma. (3) Can the verifier derive an index from `x in s`? No — this also requires a lemma.

### The Problem

A sorted list insert method uses a loop to scan all elements and determine that `x` is not present:

```python
while j < n:
    Invariant(Forall(int, lambda i:
        (Implies(0 <= i and i < pos and i < j, old_seq[i] < x),
         [[old_seq[i]]])
    ))
    Invariant(Implies(not is_dup, Forall(int, lambda i:
        (Implies(pos <= i and i < j, old_seq[i] > x),
         [[old_seq[i]]])
    )))
    ...
```

After the loop (when `j == n` and `not is_dup`), we know by index that every element is either `< x` or `> x`, so none equals `x`. But the verifier cannot derive `not (x in old_seq)` from this:

```python
# This fails — the verifier can't bridge from indices to membership
Assert(not (x in old_seq))  # ERROR: might not hold
```

The gap is fundamental: `x in s` for `PSeq` is defined as a value-level membership predicate. The verifier has an axiom that `s[i] == x` implies `x in s` (index to membership), but not the reverse (membership to index). Without the reverse direction, the verifier cannot conclude that the absence of `x` at every index means `x` is absent from the sequence.

### Fix: Inductive Lemma Pair

The solution is two lemmas that bridge the gap between indices and values.

**Lemma 1 — Reverse containment** (`x in s` → index witness): Proved by structural induction on the sequence. If `x` equals the first element, return index 0. Otherwise, recurse on the tail (`s.drop(1)`) and add 1 to the result.

```python
@Ghost
@Pure
def seq_contains_idx(s: PSeq[int], x: int) -> int:
    """If x in s, returns an index where s[idx] == x."""
    Requires(x in s)
    Decreases(len(s))
    Ensures(0 <= Result() and Result() < len(s))
    Ensures(s[Result()] == x)

    if s[0] == x:
        return 0
    else:
        tail: PSeq[int] = s.drop(1)
        idx: int = seq_contains_idx(tail, x)
        return idx + 1
```

**Lemma 2 — Not-contains** (all indices ≠ `x` → `x` not in `s`): Proved by contradiction using Lemma 1. Assume `x in s`, then `seq_contains_idx` returns an index `i` where `s[i] == x`, contradicting the precondition that `s[i] != x` for all `i`.

```python
@Ghost
@Pure
def seq_not_contains(s: PSeq[int], x: int) -> int:
    """If no index maps to x, then x not in s."""
    Requires(Forall(int, lambda i:
        (Implies(0 <= i and i < len(s), s[i] != x),
         [[s[i]]])
    ))
    Decreases(len(s))
    Ensures(not (x in s))

    if x in s:
        return seq_contains_idx(s, x)

    return 0
```

With these lemmas, the call site becomes straightforward — the loop's index-based invariants directly satisfy `seq_not_contains`'s precondition:

```python
# After the loop: invariants give us Forall(i, old_seq[i] != x)
seq_not_contains(old_seq, x)  # Now verifies
```
