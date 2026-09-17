# Any copyright is dedicated to the Public Domain.
# http://creativecommons.org/publicdomain/zero/1.0/

from nagini_contracts.contracts import *
from nagini_contracts.obligations import MustTerminate

class Cell:
    def __init__(self, n: object) -> None:
        Requires(MustTerminate(1))
        self.cnts = n
        Fold(self.val())
        Ensures(self.val() and self.get_contents() is n)

    @Predicate
    def val(self) -> bool:
        return Acc(self.cnts)

    @Pure
    def get_contents(self) -> object:
        Requires(self.val())
        Decreases(1)
        return Unfolding(self.val(), self.cnts)

    def set(self, n: object) -> None:
        Requires(self.val())
        Requires(MustTerminate(1))
        Ensures(self.val() and self.get_contents() is n)
        Unfold(self.val())
        self.cnts = n
        Fold(self.val())


class ReCell(Cell):
    def __init__(self, n: object) -> None:
        Requires(MustTerminate(2))
        self.bak: object = None
        super(ReCell, self).__init__(n)
        Fold(self.val())
        Ensures(self.val() and self.get_contents() is n)

    @Predicate
    def val(self) -> bool:
        return Acc(self.bak)

    @Pure
    def get_last(self) -> object:
        Requires(self.val())
        Decreases(1)
        return Unfolding(self.val(), self.bak)

    def set(self, n: object) -> None:
        Requires(self.val())
        Requires(MustTerminate(1))
        Ensures(self.val() and self.get_contents() is n and
                self.get_last() is Old(self.get_contents()))
        Unfold(self.val())
        self.bak = self.cnts
        self.cnts = n
        Fold(self.val())

    def undo(self) -> None:
        Requires(self.val())
        Requires(MustTerminate(1))
        Ensures(self.val() and self.get_contents() is Old(self.get_last()))
        Unfold(self.val())
        self.cnts = self.bak
        Fold(self.val())