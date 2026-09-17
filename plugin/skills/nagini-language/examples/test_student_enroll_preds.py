# Any copyright is dedicated to the Public Domain.
# http://creativecommons.org/publicdomain/zero/1.0/

from nagini_contracts.contracts import *
from nagini_contracts.io_contracts import *
from nagini_contracts.obligations import MustTerminate
from typing import List, Set


class Student:
    def __init__(self, name: str) -> None:
        Requires(MustTerminate(2))
        self.name: str = name
        self.courses: List[str] = []
        Fold(self.undecided())
        Ensures(Acc(self.name) and self.name == name and self.undecided())

    def enroll(self, course_name: str) -> None:
        Requires(self.undecided())
        Requires(MustTerminate(2))
        Ensures(self.enrolled(course_name))

        Unfold(self.undecided())
        self.courses.append(course_name)
        Fold(self.enrolled(course_name))

    @Predicate
    def enrolled(self, course_name: str) -> bool:
        return Acc(self.courses) and Acc(
            list_pred(self.courses)) and course_name in self.courses

    @Predicate
    def undecided(self) -> bool:
        return Acc(self.courses) and Acc(list_pred(self.courses))


class GradStudent(Student):
    def __init__(self, name: str, advisor_name: str) -> None:
        Requires(MustTerminate(3))
        super().__init__(name)
        self.advisor_name = advisor_name
        self.research_only = True
        Fold(self.undecided())
        Ensures(Acc(
            self.name) and self.name == name and self.undecided())
        Ensures(Acc(
            self.advisor_name) and self.advisor_name == advisor_name)

    def enroll(self, course_name: str) -> None:
        Requires(self.undecided())
        Requires(MustTerminate(2))
        Ensures(self.enrolled(course_name))

        Unfold(self.undecided())
        self.courses.append(course_name)
        self.research_only = False
        Fold(self.enrolled(course_name))

    @Predicate
    def enrolled(self, course_name: str) -> bool:
        return Acc(self.research_only) and not self.research_only

    @Predicate
    def undecided(self) -> bool:
        return Acc(self.research_only) and self.research_only


def enroll_all(students: Set[Student], course_name: str) -> None:
    Requires(Acc(set_pred(students), 1 / 2) and
             Forall(students, lambda s: (s.undecided(), [])))
    Requires(MustTerminate(3))
    Ensures(Acc(set_pred(students), 1 / 2) and
            Forall(students, lambda s: (s.enrolled(course_name), [])))
    for student in students:
        Invariant(Forall(students, lambda s: (
        Implies(s not in Previous(student), s.undecided()), [])) and
                  Forall(Previous(student),
                         lambda s: (s.enrolled(course_name), [[s in students]])))
        Invariant(MustTerminate(len(students) - len(Previous(student))))
        student.enroll(course_name)


def client() -> None:
    Requires(MustTerminate(4))
    s1 = Student('Marc')
    course = 'COOP'
    enroll_all({s1}, course)
    Unfold(s1.enrolled(course))
    assert course in s1.courses
    #:: ExpectedOutput(assert.failed:assertion.false)
    assert 'sae' in s1.courses

