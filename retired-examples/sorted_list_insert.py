from typing import List

from nagini_contracts.contracts import *
from nagini_contracts.obligations import MustTerminate


@Ghost
@Pure
def seq_contains_idx(s: PSeq[int], x: int) -> int:
    """Lemma: if x in s, then there exists an index where s[idx] == x.
    Returns the index as witness."""
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

@Ghost
@Pure
def seq_not_contains(s: PSeq[int], x: int) -> int:
    """Lemma: if no index maps to x, then x not in s."""
    Requires(Forall(int, lambda i:
        (Implies(0 <= i and i < len(s), s[i] != x),
         [[s[i]]])
    ))
    Decreases(len(s))
    Ensures(not x in s)

    if x in s:
        return seq_contains_idx(s, x)

    return 0


@Ghost
@Pure
def is_sorted(s: PSeq[int]) -> bool:
    """The sequence is strictly sorted (ascending, no duplicates)."""
    return Forall(int, lambda i:
        (Implies(0 <= i and i < len(s) - 1, s[i] < s[i + 1]),
         [[s[i]]])
    )


def insert(lst: List[int], x: int) -> None:
    """Insert x into the sorted list, maintaining sortedness and uniqueness."""
    Requires(Acc(list_pred(lst)))
    Requires(is_sorted(ToSeq(lst)))
    Requires(MustTerminate(3 * len(lst) + 3))

    Ensures(Acc(list_pred(lst)))
    Ensures(is_sorted(ToSeq(lst)))
    Ensures(x in ToSeq(lst))
    Ensures(Implies(
        x in Old(ToSeq(lst)),
        len(ToSeq(lst)) == len(Old(ToSeq(lst)))
    ))
    Ensures(Implies(
        x in Old(ToSeq(lst)),
        Forall(int, lambda i:
            (Implies(0 <= i and i < len(Old(ToSeq(lst))),
                     ToSeq(lst)[i] == Old(ToSeq(lst))[i]),
             [[Old(ToSeq(lst))[i]]])
        )
    ))
    Ensures(Forall(int, lambda i:
        (Implies(0 <= i and i < len(Old(ToSeq(lst))),
                 Old(ToSeq(lst))[i] in ToSeq(lst)),
         [[Old(ToSeq(lst))[i]]])
    ))
    Ensures(Implies(
        x in Old(ToSeq(lst)),
        len(lst) == Old(len(lst))
    ))
    Ensures(Implies(
        not x in Old(ToSeq(lst)),
        len(lst) == Old(len(lst)) + 1
    ))
    Ensures(Forall(int, lambda i:
        (Implies(0 <= i and i < len(ToSeq(lst)),
                 ToSeq(lst)[i] in Old(ToSeq(lst)) or ToSeq(lst)[i] == x),
         [[ToSeq(lst)[i]]])
    ))

    old_seq: PSeq[int] = ToSeq(lst)
    n: int = len(lst)

    # Single-pass scan: find insertion position and prove x not in old_seq
    pos: int = n
    is_dup: bool = False
    j: int = 0
    while j < n:
        Invariant(Acc(list_pred(lst)))
        Invariant(ToSeq(lst) == old_seq)
        Invariant(is_sorted(old_seq))
        Invariant(0 <= j and j <= n)
        Invariant(n == len(lst))
        Invariant(0 <= pos and pos <= n)
        Invariant(Implies(pos < n, pos < j))
        # Elements before pos are < x
        Invariant(Forall(int, lambda i:
            (Implies(0 <= i and i < pos and i < j, old_seq[i] < x),
             [[old_seq[i]]])
        ))
        # Duplicate tracking
        Invariant(Implies(is_dup, pos < n and old_seq[pos] == x))
        Invariant(Implies(not is_dup and pos < n, old_seq[pos] > x))
        # Elements from pos onward that we've visited are > x (when not dup)
        Invariant(Implies(not is_dup, Forall(int, lambda i:
            (Implies(pos <= i and i < j, old_seq[i] > x),
             [[old_seq[i]]])
        )))
        Invariant(MustTerminate(n - j + 2))

        if pos == n and lst[j] >= x:
            pos = j
            if lst[j] == x:
                is_dup = True
        Assert(Implies(not is_dup and pos < n and j > pos,
                        old_seq[j - 1] > x and old_seq[j - 1] < old_seq[j]))
        j = j + 1

    # If duplicate, list is unchanged — just prove x is present
    if is_dup:
        return

    # x is not in old_seq
    seq_not_contains(old_seq, x)

    # Insert x at position pos
    lst.insert(pos, x)

    Assert(Forall(int, lambda i:
        (Implies(0 <= i and i < pos, lst[i] == old_seq[i]),
         [[lst[i]]])
    ))
    Assert(Forall(int, lambda i:
        (Implies(pos < i and i < n + 1, lst[i] == old_seq[i - 1]),
         [[lst[i]]])
    ))

    new_seq: PSeq[int] = ToSeq(lst)
    Assert(Forall(int, lambda i:
        (Implies(0 <= i and i < len(new_seq), new_seq[i] == lst[i]),
         [[new_seq[i]]])
    ))
    Assert(is_sorted(new_seq))
