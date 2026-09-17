from typing import List
from nagini_contracts.contracts import *
from nagini_contracts.obligations import MustTerminate

def quicksort(arr: List[int]) -> List[int]:
    """Quicksort demonstrating for-loops, Previous, fractional permissions, MustTerminate."""
    Requires(Acc(list_pred(arr), 2/3))
    Requires(MustTerminate(2 + len(arr)))
    Ensures(Acc(list_pred(arr), 2/3))
    Ensures(Implies(len(arr) > 1, list_pred(Result())))
    Ensures(Implies(len(arr) <= 1, Result() is arr))

    less: List[int] = []
    pivotList: List[int] = []
    more: List[int] = []
    if len(arr) <= 1:
        return arr
    else:
        pivot: int = arr[0]
        for i in arr:
            Invariant(list_pred(less) and list_pred(pivotList) and list_pred(more))
            Invariant(len(Previous(i)) == len(less) + len(more) + len(pivotList))
            Invariant(Implies(len(Previous(i)) > 0, len(pivotList) > 0))
            Invariant(MustTerminate(len(arr) - len(Previous(i))))
            if i < pivot:
                less.append(i)
            elif i > pivot:
                more.append(i)
            else:
                pivotList.append(i)
        less = quicksort(less)
        more = quicksort(more)
        return less + pivotList + more
