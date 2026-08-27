from nagini_contracts.contracts import *
from typing import List

@Ghost
@Pure
def is_sorted(a: PSeq[int]) -> bool:
    return Forall2(int, int, lambda i, j: (
        Implies(0 <= i and i < j and j < len(a), a[i] <= a[j]),
        [[a[i], a[j]]]
    ))

def binary_search(a: List[int], key: int) -> int:
    Requires(Acc(list_pred(a)))
    Requires(is_sorted(ToSeq(a)))
    Ensures(Acc(list_pred(a)))
    Ensures(-1 <= Result() and Result() < len(a))
    Ensures(Implies(Result() >= 0, ToSeq(a)[Result()] == key))
    Ensures(Implies(Result() == -1,
        Forall(int, lambda i: (
            Implies(0 <= i and i < len(a), ToSeq(a)[i] != key),
            [[ToSeq(a)[i]]]
        ))))

    low: int = 0
    high: int = len(a)
    result: int = -1

    while low < high and result == -1:
        Invariant(Acc(list_pred(a)))
        Invariant(is_sorted(ToSeq(a)))
        Invariant(0 <= low and low <= high and high <= len(a))
        Invariant(-1 <= result and result < len(a))
        Invariant(Implies(result >= 0, ToSeq(a)[result] == key))
        Invariant(Implies(result == -1,
            Forall(int, lambda i: (
                Implies(0 <= i and i < len(a) and not (low <= i and i < high),
                    ToSeq(a)[i] != key),
                [[ToSeq(a)[i]]]
            ))))

        mid: int = (low + high) // 2
        Assert(a[mid] == ToSeq(a)[mid])
        if a[mid] < key:
            low = mid + 1
        elif key < a[mid]:
            high = mid
        else:
            result = mid
            high = mid

    return result
