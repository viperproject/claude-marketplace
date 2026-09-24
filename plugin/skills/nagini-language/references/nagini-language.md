# Nagini Language Reference

Comprehensive reference for writing verified Python programs with Nagini.

## Imports

All Nagini contracts come from the `nagini_contracts` package:

```python
from nagini_contracts.contracts import *
from nagini_contracts.obligations import MustTerminate
from nagini_contracts.io_contracts import *  # For I/O verification
```

Nagini uses mypy for type checking, so to import local files, the source file's directory must be a Python package. This means the directory must contain an (usually empty) `__init__.py` file.

## Type Annotations

Nagini requires type annotations on all function parameters and return types. It uses Python's standard type annotation syntax:

```python
from typing import Optional, List, Tuple

def foo(x: int, y: Optional[MyClass]) -> bool:
    ...
```

For local variables, use modern Python annotation syntax — NOT legacy `# type:` comments:

```python
# Correct:
x: int = 0
found: bool = False

# Wrong (legacy syntax, do not use):
x = 0  # type: int
found = False  # type: bool
```

## Method Specifications

### Preconditions and Postconditions

```python
def method_name(param: Type) -> ReturnType:
    Requires(precondition_expression)
    Ensures(postcondition_expression)

    # ... body ...
```

The contracts form one block at the start of the body, in the order `Requires`, `Decreases`, `Ensures`, `Exsures`.

Multiple `Requires`/`Ensures` are conjoined:

```python
def foo(x: int, y: int) -> int:
    Requires(x >= 0)
    Requires(y >= 0)         # Equivalent to Requires(x >= 0 and y >= 0)
    Ensures(Result() >= 0)

    return x + y
```

#### Permission Framing

Every field access needs permission. Methods must declare what permissions they need and return:

```python
def swap(a: Cell, b: Cell) -> None:
    Requires(Acc(a.value) and Acc(b.value))
    Ensures(Acc(a.value) and Acc(b.value))
    Ensures(a.value == Old(b.value) and b.value == Old(a.value))

    tmp: int = a.value
    a.value = b.value
    b.value = tmp
```

#### Constructors

In `__init__`, write the field assignments before the `Ensures` clauses: mypy infers each field's type from its first assignment, so a contract referencing `self.field` above it fails. `Requires` and `Exsures` stay at the top; only the `Ensures` block may trail.

```python
class ListNode:
    def __init__(self, val: int, next: 'Optional[ListNode]') -> None:
        self.val = val
        self.next = next
        Ensures(Acc(self.val) and Acc(self.next) and self.val is val and self.next is next)
```

### Result Reference

Use `Result()` in postconditions to refer to the return value:

```python
def double(x: int) -> int:
    Ensures(Result() == 2 * x)

    return 2 * x
```
Nagini knows the type of `Result()`, but mypy does not. So while most uses will work, a construct that needs the *static* type of the expression, such as the element form of `Forall` over it, will fail with "Encountered Any type". To fix this, use `ResultT(S)` instead, where `S` is the type of the result.

### Old Values

Use `Old(expr)` in postconditions to refer to pre-state values:

```python
def increment(self: Counter) -> None:
    Requires(Acc(self.count))
    Ensures(Acc(self.count))
    Ensures(self.count == Old(self.count) + 1)

    self.count = self.count + 1
```

`Old` of a reference-typed expression yields the old *reference*, not a snapshot of the object's contents. A container field still holds the same object after a call, so `self.xs == Old(self.xs)` compares a reference with itself and states nothing about the contents.

## Permissions

### Permission Amounts

```python
Acc(obj.field)          # Full (write) permission
Acc(obj.field, 1/2)     # Fractional (read) permission
Acc(obj.field, 1/d)     # Any int-valued expression, e.g. a parameter d >= 1
Acc(pred(x), 1/2)       # Half of a predicate instance: every amount in its body halves
```

Reading a location needs any positive fraction. Writing needs the full permission.

### Permission Arithmetic

Permissions are transferred through contracts:

```python
def transfer(src: Cell, dst: Cell) -> None:
    Requires(Acc(src.value))       # Receive full permission to src.value
    Requires(Acc(dst.value))       # Receive full permission to dst.value
    Ensures(Acc(src.value))        # Return permission to src.value
    Ensures(Acc(dst.value))        # Return permission to dst.value
    Ensures(dst.value == Old(src.value))

    dst.value = src.value
```

## Predicates

### Definition

```python
@Predicate
def my_list_pred(lst: MyList) -> bool:
    return (Acc(lst.value) and Acc(lst.next) and
            Implies(lst.next is not None, my_list_pred(lst.next)))
```

Do not name your own predicate `list_pred`, `dict_pred`, or `set_pred`. These names are reserved for built-ins.

### Fold and Unfold

```python
Fold(my_list_pred(node))     # Package concrete permissions into predicate
Unfold(my_list_pred(node))   # Extract concrete permissions from predicate
```

### Unfolding Expression

Use `Unfolding` to temporarily unfold a predicate within an expression:

```python
@Pure
def get_value(lst: MyList) -> int:
    Requires(my_list_pred(lst))

    return Unfolding(my_list_pred(lst), lst.value)
```

Unfolded permissions are only available inside the `Unfolding(...)` expression itself, so evaluate a heap-dependent expression inside the scope.

## Pure Functions

Functions used in specifications must be marked `@Pure`:

```python
@Pure
def length(lst: MyList) -> int:
    Requires(my_list_pred(lst))
    Decreases(my_list_pred(lst))

    return Unfolding(my_list_pred(lst), 1 if lst.next is None else 1 + length(lst.next))
```

**Restrictions on pure functions:**
- No side effects (no field assignments, no object creation)
- Must return a value
- Can use `Unfolding` to access predicate contents
- Can be recursive — use `Decreases(measure)` for termination (see Termination section)
- Only need *some* permission to what they read: in a pure function's precondition the amount is irrelevant, `Requires(Acc(x.f))` and `Requires(Acc(x.f, 1/2))` mean the same, and a caller holding any positive fraction may call it
- Called in specifications by normal function call syntax

**Do not self-reference in postconditions.** A pure function's `Ensures` clause may *not* call the function itself in a postcondition.

State the property in terms of `Result()` and other pure helpers instead. For example, idempotence of a "round down to a block boundary" function should be written algebraically:

```python
# DO NOT: self-reference in own postcondition
@Pure
@ContractOnly
def network_address(addr: int, prefix: int) -> int:
    Requires(0 <= addr and addr < 4294967296)
    Requires(0 <= prefix and prefix <= 32)
    Ensures(network_address(Result(), prefix) == Result())   # rejected

# Do: state the same property via existing pure helpers and Result()
@Pure
@ContractOnly
def network_address(addr: int, prefix: int) -> int:
    Requires(0 <= addr and addr < 4294967296)
    Requires(0 <= prefix and prefix <= 32)
    Ensures(net_id(Result(), prefix) * block_size(prefix) == Result())
```

### Opaque pure functions

`@Opaque` (stacked with `@Pure`) hides the function's body from callers: only the contract (`Requires`/`Ensures`) is visible at call sites. `Reveal(f(args))` — an expression returning the application's value — makes the definition of exactly that one application available where it appears.

```python
@Pure
@Opaque
def plus_four(i: int) -> int:
    Ensures(Result() > i)
    return i + 4

def client() -> None:
    a = plus_four(2)
    Assert(a > 2)              # from the Ensures — always visible
    b = Reveal(plus_four(2))
    Assert(b == 6)             # from the body — needs the Reveal
```

`Reveal` is per-application and unrolls one step: `Reveal(tri(2))` for a recursive `tri` yields `tri(2) == 2 + tri(1)` with `tri(1)` still opaque; each further level needs its own `Reveal`.

### Property getters are implicitly pure

A `@property` getter is treated as a pure function automatically. Do not stack `@Pure` on it.

## ContractOnly Functions

To specify functions without providing an implementation:

```python
@ContractOnly
def abstract_size(obj: MyObj) -> int:
    Requires(valid(obj))
    Ensures(Result() >= 0)
```

The verifier does not look at `@ContractOnly` bodies, the contract is **all the information that exists**. In particular, a `@Pure` function which usually gets its definition as an axiom automatically does not if it is `@ContractOnly`.

### Always add `Decreases` to `@Pure @ContractOnly` functions

There is no body to check a measure against, but callers need it: proving termination of anything that calls the stub — including using it as a specification function in contexts that must terminate — requires a `Decreases` measure on the stub itself.

## Quantification
A quantifier is an expression that states a property holds for all or some values of a type or collection. A quantifier consists of the domain (type or collection), a lambda binding the quantified variable, a body expression and a trigger list.

```python
Forall(int, lambda i: (
    Implies(0 <= i and i < n, arr[i] >= 0),
    [[arr[i]]]
))
```

#### Triggers
Every `Forall` should provide an explicit trigger. A trigger is a list of terms (inside `[[...]]`) mentioning all bound variables; the quantifier fires whenever matching terms appear in the proof context.

- Every quantifier needs a trigger; nested quantifiers each need one (not just the innermost).
- For an empty trigger list `[]` , Nagini supplies its own trigger. These are both incomplete and quite broad, so you should always provide your own.
<!-- if errors -->
- `debug.viperExcerpt` on a failing diagnostic shows the trigger each quantifier ended up with.
<!-- end -->
- Each quantified variable must appear in at least one trigger expression.
- Each trigger expression must mention at least one quantified variable and should contain some structure beyond the variable itself (typically a function application).
- Avoid arithmetic and boolean operators in trigger expressions, they lead to unpredictable instantiation.
- Accessibility predicates (`Acc(...)`) may not appear in trigger expressions.
- Avoid triggers where the quantifier body can re-instantiate on the trigger terms — that produces a matching loop and the verifier will time out.

Bad-trigger example (matching loop):

```python
# The body produces a[i + 1], which matches the trigger and re-instantiates indefinitely.
Forall(int, lambda i: (
    Implies(0 <= i and i < len(a) - 1, a[i] >= a[i + 1]),
    [[a[i], a[i + 1]]]
))
```

#### Quantifying over a collection

The first argument to `Forall` does not have to be a type — it can also be a collection value (a `list`, `set`, `dict`, `PSeq` or `PSet`), in which case the bound variable ranges over the *elements* (or keys) of that collection, rather than over all values of a type. The element-form quantifier avoids the `0 <= i < len(xs)` guard and triggers on element-level expressions.

```python
xs: List[int] = ...
# Element-form: x ranges over the elements of xs
Assert(Forall(xs, lambda x: (x >= 0, [])))

# Equivalent index-form
Assert(Forall(int, lambda i: (Implies(0 <= i and i < len(xs), xs[i] >= 0), [[xs[i]]])))
```

Use the element form when the property is naturally per-element and does not depend on the index; use the index form when you need the index (e.g. to relate `xs[i]` and `xs[i+1]`, or to mix in a second collection at the same position).

### Multi-variable Quantification

`Forall2` through `Forall6` bind several variables in one quantifier: `ForallN` takes `N` domain types followed by a lambda of `N` variables, and accepts one trigger list spanning all of them.

```python
Forall2(int, int, lambda i, j: (
    Implies(0 <= i and i <= j and j < len(a), a[i] >= a[j]),
    [[a[i], a[j]]]  # trigger fires when both a[i] and a[j] are in scope
))
```

### Quantified Permissions

A `Forall` whose body contains `Acc(...)` grants permission to a whole family of heap locations at once. This is called a quantified permission, or QP:

```python
Forall(streams, lambda k: (Acc(streams[k].weight), []))
```

Every QP carries a proof obligation the plain quantifiers do not have: the receiver expression must be **injective** — distinct values of the bound variable must denote distinct objects. If this cannot be proven, verification will fail (`qp.not.injective`). For a QP over container elements this means distinct keys/indices map to distinct objects. Often, you can state it as a pure function and require it alongside the QP:

```python
@Pure
def streams_injective(streams: Dict[int, Stream]) -> bool:
    Requires(Acc(dict_pred(streams), 1 / 100))
    return Forall2(int, int, lambda k1, k2: (
        Implies(k1 in streams and k2 in streams and k1 != k2,
                streams[k1] is not streams[k2]),
        [[streams[k1], streams[k2]]]))
```

## Ghost Code

A Nagini program has two layers: the regular Python program, and ghost code that exists only for the verifier: specifications, proof steps, and the mathematical state they reason about. Information flows can flow from regular code to ghost code, but never back, so erasing the ghost code leaves the same program with the same behavior.

### What is ghost

- A call to `Requires`, `Ensures`, `Invariant`, `Assert`, `Fold`, `Unfold`, `Decreases`, `MustTerminate`, or a `@Ghost` function at any statement position of a regular body.
- Ghost values: ghost-typed parameters, fields and locals, ghost arguments of a call, variable of ghost types, the ghost half of a mixed `Tuple` return, and every assignment to them.
- A def or class decorated `@Ghost`, and every `@Predicate`.
- `Unfolding(P, e)` and `Reveal(e)` wrapped around a (possibly non-ghost) expression `e`: Erasing the wrappers leaves just `e`.
- The `nagini_contracts` import and every Nagini decorator.

Ghost code must provably terminate: a `@Ghost` method needs `Requires(MustTerminate(measure))` (see Termination), a `@Ghost @Pure` function proves termination via `Decreases`.

### Ghost types

The P-collections (`PSeq`, `PByteSeq`, `PSet`, `PMultiset`) and the ghost primitives `GInt`, `GFloat`, `GBool`, `GStr`, `GComplex` are ghost types. `MarkGhost` declares a ghost alias of your own:

```python
GIdx = int
MarkGhost(GIdx)
```

A ghost-typed value may appear in contracts and ghost code but not in regular executable code. Assigning one to a non-ghost target is rejected. The reverse direction is fine: regular values may flow into ghost targets.

### Ghost variables and mixed returns

A local, field, or parameter annotated with a ghost type is ghost. Regular functions declare and update ghost variables freely; those statements are ghost statements. A regular function can also return a regular and a ghost part together as a two-element tuple:

```python
def counted_sum(l: List[int]) -> Tuple[int, GIdx]:
    Requires(Acc(list_pred(l), 1/2))
    Ensures(Acc(list_pred(l), 1/2))
    Ensures(Result()[1] == len(l))
    total = 0
    steps: GIdx = 0            # ghost local in a regular function
    i = 0
    while i < len(l):
        Invariant(Acc(list_pred(l), 1/2) and 0 <= i and i <= len(l))
        Invariant(steps == i)
        total += l[i]
        steps += 1             # ghost statement
        i += 1
    return total, steps        # callers unpack: s, n = counted_sum(l)
```

### `@Ghost` functions and classes

`@Ghost` marks a whole def (or class) as ghost. A def whose result depends on ghost inputs must be ghost, since a regular result may not depend on a ghost value: a `@Pure` function over a `PSeq` is `@Ghost @Pure`, as is one whose body uses a specification construct (`Forall`, `Implies`, `Old`) even over regular arguments, a lemma over ghost values is `@Ghost` with `MustTerminate`. A bare call to a `@Ghost` function in a regular body is a ghost statement.

### Ghost expressions and control-flow

An expression is ghost as soon as it mentions a ghost value. An `if` or `while` whose condition is ghost is a ghost statement together with everything inside it. Its body may then hold ghost statements only: a regular assignment inside it is rejected.

### Rules for ghost code
- Ghost code must not `return`, `break`, `continue` or `raise`, and must not use `try` or `with`: that would change the regular control flow.
- Ghost code must not call an impure method on a ghost receiver, since erasing the call would erase its effect. `@Pure` calls are fine and yield a ghost value.
- A plain `assert` runs at runtime and must not mention ghost state. Use `Assert`.
- A `@Ghost` class inherits only from `@Ghost` classes, a regular class only from regular ones.
- Several regular or several ghost return values are grouped into a nested tuple (`Tuple[Tuple[int, bool], GInt]`), and the caller unpacks the result immediately into regular and ghost targets.

### What is not ghost

- A control-flow statement over a regular condition, and every `for`, `with` and `try`.
- A plain `@Pure` function: regular code, only the decorator is ghost.
- A call assigned to ghost targets: the targets are ghost, the call is not.

So a proof over regular code may add ghost code anywhere, including ghost locals naming side-effect-free expressions (a field read, a `@Pure` call) and branches or loops over ghost conditions, but should not add a branch or loop over a regular condition, a regular local, or a ghost local holding the result of a regular call.

## Containers

### Ghost containers

#### Sequences (PSeq)

Immutable mathematical sequences. The supported operations are:

```python
from nagini_contracts.contracts import PSeq

s: PSeq[int] = PSeq()             # Empty sequence (bare constructor + annotation)
s = PSeq(1, 2, 3)                 # Sequence [1, 2, 3] (type inferred from args)
len(s)                            # Length (use in specs)
s[i]                              # Element access
s + t                             # Concatenation
s.take(n)                         # First n elements
s.drop(n)                         # All but first n elements
s.update(i, v)                    # Update at index i
x in s                            # Membership
```

The varargs form `PSeq(x, y, ...)` is usable inline in any spec expression. For an empty sequence, avoid using the subscripted spelling `PSeq[int]()`, the verifier treats the result as an arbitrary value, not even empty. In a spec, express emptiness with `len(s) == 0`.

#### Sets (PSet)

Immutable mathematical sets:

```python
from nagini_contracts.contracts import PSet

s: PSet[int] = PSet()             # Empty set (bare constructor + annotation)
s = PSet(1, 2, 3)                 # Set {1, 2, 3} (type inferred from args)
x in s                            # Membership
len(s)                            # Cardinality
s + t                             # Union
s - t                             # Difference
```

There is no intersection operator, so you must express intersection with a quantifier or build it constructively. Same constructor rules as `PSeq`: the varargs form is usable inline in specs; for a known-empty set use `s: PSet[int] = PSet()`, never the subscripted `PSet[int]()`.

#### Multisets (PMultiset)

```python
from nagini_contracts.contracts import PMultiset

m: PMultiset[int] = PMultiset()   # Empty multiset (bare constructor + annotation)
m = PMultiset(1, 2, 2)            # Multiset {|1, 2, 2|} (type inferred from args)
m.num(x)                          # Count of x in m
```

Same constructor rules as `PSeq`: the varargs form is usable inline in specs; for a known-empty multiset use `m: PMultiset[int] = PMultiset()`, never the subscripted `PMultiset[int]()`.

There is no `.count` and no `x in m` for multisets, check membership with `m.num(x) > 0`.

### Python containers

Python lists, dicts and sets are heap objects. Accessing them requires permissions, which are expressed with built-in predicates:

```python
Requires(Acc(list_pred(xs)))          # full: read and mutate xs
Requires(Acc(dict_pred(d), 1 / 2))    # a fraction: read only
Requires(Acc(set_pred(s), 1 / 2))
```
As opposed to user-defined predicates, the built-in predicates do not require folding and unfolding.

### Bridging between the two

| Container | Pure view | Content |
|-----------|-----------|---------|
| `List[T]` | `ToSeq(xs)`: `PSeq[T]` | the elements, in order |
| `Set[T]` | `ToSet(s)`: `PSet[T]` | the elements |
| `Set[T]` | `ToSeq(s)`: `PSeq[T]` | the elements, without duplicates, in an unspecified but fixed order |
| `Dict[K, V]` | `ToSet(d)`: `PSet[K]` | the keys |
| `Dict[K, V]` | `ToSeq(d)`: `PSeq[K]` | the keys, as for a set; the values are `d[k]` |

`ToMS()` is the multiset view of a `PSeq`.
### Membership

`x in c` means different things per container. In a list or `PSeq` it holds when some element is `==` to `x`. In a set, dict or `PSet` it holds when `x` itself is an element (or key), by object identity. So `x in s` and `x in ToSet(s)` are the same fact, while for an arbitrary `int` `x in ToSeq(s)` does not give `x in s`: `x` may be a different object with the same value.

### Mutators

Modeled list mutators: `append`, `extend`, `insert`, `remove`, `reverse`, `copy`, `xs[i] = v`, `xs.pop()` (no-argument form only), `del xs[i]`, and `del xs[i:j]` (any bound may be omitted or negative; no step). For `xs.pop(i)`, capture `xs[i]` and write `del xs[i]` instead. Modeled dict mutators: `d[k] = v`, `d.pop(k)` (no-default form only), `del d[k]`. Modeled set mutators: `add`, `remove`, `clear`. `list.sort`, `list.clear`, and `list.count` are not modeled. `pop`/`del` require a non-empty list, an in-range index, or a present key — the same obligations as the equivalent read.

Every mutator's contract entails the corresponding mutation on the pure view:

```python
xs.append(x)   # ToSeq(xs) == Old(ToSeq(xs)) + PSeq(x)
s.add(x)       # ToSet(s) == Old(ToSet(s)) + PSet(x)
d[k] = v       # ToSet(d) == Old(ToSet(d)) + PSet(k) and d[k] == v
```

## Built-in Functions with Verified Contracts

Nagini ships verified contracts for many Python built-ins, usable directly in specs and pure functions:

| Use this | Don't write |
|----------|-------------|
| `abs(x)`, `abs(a - b)` | `abs_diff(a, b)`, custom `abs` |
| `max(a, b)`, `min(a, b)` | `max_of(a, b)`, `min_of(a, b)` |
| `len(xs)` | `list_len(xs)`, manual length recursion over a list/PSeq |
| `x in xs` (`List`, `PSeq`, `PSet`) | custom `contains(xs, x)`, existential over indices |
| `xs[i]`, `xs.take(n)`, `xs.drop(n)`, `xs + ys` (`PSeq`) | manual sequence rebuild via recursion |

## Integers

### Typing

Python's `int` can be subclassed (`bool` is one). So something of type `int` is only known to be *some* int-subtype object. It has the numeric value you expect, but it is not known to be *the* int object for that value. This can lead to some unexpected behavior:

```python
def f(s: Set[int], x: int) -> None:
    Requires(Acc(set_pred(s)))
    Requires(1 in s and x == 1)
    Assert(x in s)        # FAILS: x is not known to be the object 1

def g(x: int) -> None:
    Requires(Q(0) and Q(1))          # Q is @ContractOnly
    Requires(x == 0 or x == 1)
    Assert(Q(x))          # FAILS for the same reason

Similarly `P(0) and P(1)` does not give `Forall(int, lambda i: Implies(0 <= i and i <= 1, P(i)))`

def h(x: int, y: int) -> None:
    Requires(x == y)
    Assert(PSeq(x) == PSeq(y))   # FAILS: collection equality compares the objects
    Assert(cnt(x) == cnt(y))     # FAILS for any @Pure cnt: an ==-equal int cannot be
                                 # substituted into a function application
```

### Size limits

`int` is unbounded: arithmetic (`+`, `-`, `*`, `//`, `%`) has no size limits and needs no configuration. Two constructs do have limits:

**Bitwise operations** on `int` are encoded through fixed-width bitvectors sized by the verifier's bitops width (default 8; set at launch via `--int-bitops-size` or with the `configure` tool's `intBitopsSize`). `&`, `|`, `^` require both operands in `[-(2**N), 2**N - 1]` on every application; shifts require a non-negative count and require the operand range only when the count exceeds 64. Out-of-range operands fail with a bare precondition error on the bitwise expression (the message does not name the flag). The arithmetic forms are unbounded and need no flag: `x & (2**k - 1)` is `x % 2**k`, `x >> k` is `x // 2**k`, `x << k` is `x * 2**k` (exact equalities for all ints).

**Power expressions**: `**` with a constant exponent is evaluated by unrolling one step per solver instantiation, so only small exponents evaluate (tens, not hundreds); with a symbolic exponent it is essentially opaque without manual lemmas. Exponents must be non-negative. Write large constants as numeral literals (decimal or hex), in code and contracts alike:

```python
MASK64 = 0xFFFFFFFFFFFFFFFF  # == 2**64 - 1; written as `2**64 - 1` it stays an opaque term
```

## Loops

**Every loop must have invariants** that:
1. Hold on entry to the loop
2. Are preserved by each iteration
3. Together with loop exit condition, imply proof obligations after the loop

Inside the body, and after the loop, the invariant is all that is known about anything the loop touches. Permissions left out of the invariant are framed around the loop.

```python
i = 0
total = 0
while i < n:
    Invariant(0 <= i and i <= n)
    Invariant(total == sum_up_to(items, i))
    Invariant(Acc(list_pred(items)))     # Permission invariant
    total += items[i]
    i += 1
```

### `for` loops
If at all possible, prefer `while` loops over `for` loops. Write `while i < len(xs)` for a list, a range, or anything else that has an index, even where a `for` loop reads more naturally. Use a `for` loop only for a container without an index.

`for x in c` walks `ToSeq(c)`. The loop needs at least 1/10 of the container's permission. It automatically keeps a fraction of it as an invariant. So you can read `c` in the body and the other invariants for free, and writing it is impossible because a portion of the permission is not available.

`x` is assigned only when `c` is non-empty: guard invariants about it with `Implies(len(c) > 0, ...)`.

`Previous(x)` is the `PSeq` of the values `x` took in the completed iterations. Be careful with it, use of `y in Previous(x)` inside a quantifier can make the verifier diverge.

## Termination

Nagini has two separate termination mechanisms.

| Context | Mechanism | Where it goes |
|---------|-----------|---------------|
| `@Pure` function | `Decreases(measure)` | Between `Requires` and `Ensures` |
| Non-pure method | `Requires(MustTerminate(measure))` | As a `Requires` precondition |
| Loop (any method) | `Invariant(MustTerminate(measure))` | Inside the loop body |

### `Decreases` — `@Pure` functions only

`Decreases` is **only valid inside `@Pure` functions**. Using it in a regular (non-pure) method causes a translation error.

**Placement is strict**: `Decreases` must appear **after all `Requires` and before any `Ensures`**. Any other position is a translation error.

```python
@Pure
def factorial(n: int) -> int:
    Requires(n >= 0)
    Decreases(n)          # ← after Requires, before Ensures
    Ensures(Result() >= 0)

    if n == 0:
        return 1
    return n * factorial(n - 1)
```

Decreases clauses can also contain a boolean *condition* (`Decreases(measure, condition)` as second argument. The measure is only checked when the condition holds). The condition is a guard, not a second measure component — there is no lexicographic tuple form.

Every `@Pure` function called from a function with a `Decreases` needs to prove termination as well. A non-recursive function (which terminates trivially) needs to be annotated with `Decreases(1)`.

For a `@Pure` function recursing over a heap predicate, the measure can be the predicate instance. The recursive call must then sit inside an `Unfolding` of that same instance. If the predicate guards its recursion (e.g. `Implies(l.next is not None, MyList(l.next))`), guard the call with the same condition. The parameter must not be `Optional`: if the recursive call can pass `None`, the callee's measure predicate does not exist and the termination check fails.

### `MustTerminate` — non-pure methods and loops

For non-pure (regular) methods, use `Requires(MustTerminate(measure))`:

```python
from nagini_contracts.obligations import MustTerminate

def quicksort(arr: List[int]) -> List[int]:
    Requires(Acc(list_pred(arr), 2/3))
    Requires(MustTerminate(100 + 2*len(arr)))   # ← termination measure, with headroom
    Ensures(Acc(list_pred(arr), 2/3))
    ...
    quicksort(less)   # Nagini verifies len(less) < len(arr) satisfies the bound
    quicksort(more)
```

Every call in the body must have a measure strictly below the caller's. Builtin calls count and usually have measure 1.
It is better to leave a good amount of headroom in the measure, so that adding calls later on does not break the termination proof. 

A loop inside a `MustTerminate` method must carry its own termination invariant:

```python
while condition:
    Invariant(MustTerminate(ranking_expression))
    # ...
```

The loop's measure must strictly decrease each iteration, and is independent of the method's measure. The method's measure is unchanged by the loop, so code after it, and calls inside it, are bounded by the *method's* measure as everywhere else, not by the loop's value.

### Non-pure methods without `MustTerminate`

If a non-pure method is recursive but has no `Requires(MustTerminate(...))`, Nagini **does not verify its termination** — it simply accepts it. 

Ghost code however must always terminate. A `@Ghost` method without `Requires(MustTerminate(...))` fails verification..

## Assert

```python
Assert(x > 0)          # Checked by verifier (fails if unprovable)
```

## Let Bindings

`Let(bound_expr, result_type, lambda)` means "let v = bound_expr in lambda-body": `Let(5, int, lambda x: x + 34)` evaluates to 39. The second argument is the type of the lambda's *result* — not of the bound variable — so in a contract it is always `bool`:

```python
Ensures(Let(x + 1, bool, lambda v: v > 0 and v < 100))
```
## Exception Contracts

### Exsures

`Exsures` can name `Exception` itself or any builtin `Exception` subclass (`ValueError`, `KeyError`, ...); builtins are modeled as opaque subclasses of `Exception`, raised via `raise ValueError` or `raise ValueError()` (a message argument is accepted but not modeled). To carry data on the exception, use a module-defined `Exception` subclass:

```python
class DivisionError(Exception):
    def __init__(self, code: int) -> None:
        self.code = code
        Ensures(Acc(self.code) and self.code == code)

def safe_divide(a: int, b: int) -> int:
    Requires(True)
    Ensures(b != 0 and Result() == a // b)
    Exsures(DivisionError, b == 0)

    if b == 0:
        raise DivisionError(1)
    return a // b
```

### RaisedException

In `Exsures`, use `RaisedException()` to refer to the exception object. `.args` is not modeled but you can use fields you define on your own exception class:

```python
Exsures(DivisionError, Acc(RaisedException().code) and RaisedException().code == 1)
```

## Global Variables

A module-level name assigned exactly once is a constant: read it freely in any function. A reassigned global needs `Acc(<name>)` in contracts and a `global` declaration to rebind. A global list/dict/set is a constant binding whose *contents* still need the usual container permission — e.g. `Requires(Acc(list_pred(P1), 1/100))` and matching `Ensures`. Module-init facts do not flow into defs: restate what the body needs (`len(P1) == 3`, element values) in the precondition; module-level callers hold the permissions and facts after initialization.

Reads of a global that is never reassigned need no contract permission:

```python
COUNTER: int = 0

def get() -> int:
    Ensures(Result() == COUNTER)
    return COUNTER
```

Writes require `Acc(var)` in the contract and a `global` declaration placed before the contract lines. Return the permission via `Ensures` so the caller keeps it:

```python
def bump() -> None:
    global COUNTER
    Requires(Acc(COUNTER))
    Ensures(Acc(COUNTER) and COUNTER == Old(COUNTER) + 1)
    COUNTER = COUNTER + 1
```
Once any function in the module reassigns the global, even reads require `Acc(<name>)` in the contract — `get` as written above fails alongside a writer like `bump` below.

For shared reads, split the permission into fractions and wrap it in a `@Predicate` (e.g. `Acc(a, 1/2)`), `Fold` it at module scope, and have functions require/ensure the predicate — same pattern as fractional field permissions.

## Threads

Import from `nagini_contracts.thread`:

```python
from nagini_contracts.thread import (
    Thread, MayStart, Joinable, ThreadPost, getMethod, getArg, getOld, arg,
)
```

### Lifecycle

```python
t = Thread(target=worker, args=(x, y))   # yields MayStart(t)
t.start(worker)                          # consumes MayStart + worker's precondition,
                                         # yields Joinable(t) + Acc(ThreadPost(t))
t.join(worker)                           # consumes Acc(ThreadPost(t)), inhales worker's post
```

`start` yields `Joinable(t)` and `Acc(ThreadPost(t))` only if `worker`'s precondition includes a `MustTerminate(...)` obligation; without it the thread cannot be proven joinable.

### Resources

- `Joinable(t)` — bare boolean, not wrapped in `Acc(...)`. Holding `Acc(ThreadPost(t))` already implies `Joinable(t)`, so writing both is redundant.
- `Acc(ThreadPost(t))` — permission to inhale the thread's postcondition on join. Fractional shares are allowed; joining with a fraction inhales that fraction of the postcondition.
- `MayStart(t)` — one-shot permission to start a fresh thread.

### Inspection helpers

- `getMethod(t) == f` — the target is `f`.
- `getArg(t, i)` — the `i`-th argument passed to `args=(...)`. If the target was a bound method `o.m`, the receiver `o` is `getArg(t, 0)` and the `args` tuple starts at index 1.
- `getOld(t, arg(i).field)` — value of `arg(i).field` captured at `start()` time, for referring to `Old(...)` expressions in the target's postcondition.

### Quantifying thread resources — `Joinable` conjunct bug

Quantifying thread resources across a list of threads works, **except** `Joinable(threads[j])` cannot appear as a conjunct alongside anything else inside a `Forall`. This fails translation with `Not supported: Call`:

```python
# FAILS — Joinable as a conjunct
Invariant(Forall(int, lambda j: (
    Implies(0 <= j and j < i,
            Joinable(threads[j])
            and Acc(ThreadPost(threads[j]))),
    [[threads[j]]]
)))
```

Workaround: drop the redundant `Joinable(...)` — `Acc(ThreadPost(...))` already implies it:

```python
# OK
Invariant(Forall(int, lambda j: (
    Implies(0 <= j and j < i,
            Acc(ThreadPost(threads[j]))
            and getMethod(threads[j]) == worker),
    [[threads[j]]]
)))
```

`Joinable(threads[j])` **alone** as the sole body of a `Forall` also works — the bug is specifically its use in a conjunction.
