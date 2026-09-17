from nagini_contracts.contracts import *
from typing import Optional

class Node:
    def __init__(self, value: int, next_node: Optional['Node']) -> None:
        Ensures(Acc(self.value) and self.value == value)
        Ensures(Acc(self.next) and self.next is next_node)
        self.value: int = value
        self.next: Optional[Node] = next_node

@Predicate
def lseg(node: Optional[Node]) -> bool:
    return Implies(node is not None,
        Acc(node.value) and Acc(node.next) and lseg(node.next))

@Pure
def lseg_length(node: Optional[Node]) -> int:
    Requires(lseg(node))
    Decreases(lseg(node))

    if node is None:
        return 0
    return Unfolding(lseg(node), 1 + lseg_length(node.next))

@Pure
def lseg_contains(node: Optional[Node], target: int) -> bool:
    Requires(lseg(node))
    Decreases(lseg(node))

    if node is None:
        return False
    return Unfolding(lseg(node),
        node.value == target or lseg_contains(node.next, target))

def prepend(head: Optional[Node], value: int) -> Node:
    Requires(lseg(head))
    Ensures(lseg(Result()))
    Ensures(lseg_length(Result()) == Old(lseg_length(head)) + 1)
    Ensures(lseg_contains(Result(), value))

    new_node = Node(value, head)
    Fold(lseg(new_node))
    return new_node

def find(head: Optional[Node], target: int) -> bool:
    Requires(lseg(head))
    Ensures(lseg(head))
    Ensures(Result() == lseg_contains(head, target))

    if head is None:
        Fold(lseg(head))
        return False

    Unfold(lseg(head))
    if head.value == target:
        Fold(lseg(head))
        return True

    result = find(head.next, target)
    Fold(lseg(head))
    return result
