# Nagini Limitations

Things that Nagini genuinely cannot do. Nagini and Viper are more expressive than you might assume — before concluding that a property cannot be expressed or that a workaround is needed, check this list.

Anything not listed here is expressible until a concrete error shows otherwise: try the direct encoding first, and treat something as a limitation only once you hold the error that demonstrates it.

The reverse does not hold for performance limitations. An entry that says "times out" or "expensive" describes behavior at realistic scale; a small snippet that passes quickly does not refute it and is not a license to use the construct. Follow the entry's workaround anyway.

<!-- Add entries in this format:
- **Limitation**: description
  **Workaround**: recommended approach
-->

- **Limitation**: Mutually recursive `@Pure` functions or predicates whose contracts reference each other. As soon as the postconditions — and in Nagini therefore the result types — rely on each other, one of the pair will always fail.
  **Workaround**: Never design the cycle in. Fuse the pair into one self-recursive `@Pure` engine (over a combined argument or mode flag) with thin non-recursive wrapper functions, or stratify the definitions so the dependency runs one way only.

- **Limitation**: `Exists()` quantifiers. Never use them. Toy snippets with an `Exists` verify in seconds; the same shape inside a real contract — under quantified permissions, in a recursive predicate, or instantiated per loop iteration — causes timeouts that surface far from the `Exists` itself and are near-impossible to debug. A passing probe does not clear it for use.
  **Workaround**: Every existential has a constructive replacement: an explicit witness variable, a pure function that returns the witness, or a pure boolean function defined by recursion.

- **Limitation**: `range(...)` is a frequent source of tricky verification failures. A fact or permission quantified over `range(a, b)` binds to range-membership terms that often cannot be connected to a use site's arithmetic bounds (`a <= i < b`), and `for ... in range(...)` loops inherit the for-loop iterator issues below.
  **Workaround**: Avoid `range()`. In specs, quantify over `int` with an explicit bounds guard: `Forall(int, lambda i: (Implies(lo <= i and i < hi, ...), [[...]]))`. In code, use an indexed `while` loop.

- **Limitation**: Connecting quantified membership facts to the concrete contents of a collection can be difficult or impossible. For example, a set `s` known only through "`x in s` iff `P(x)`" has no terms to trigger the solver, so you cannot derive e.g. the contents `Assert(s == PSet(1))` or its cardinality (`len(s)`) from that alone. 
  **Workaround**: Keep aggregates constructive: build collections operation by operation, or track the count in its own variable updated alongside every mutation. Keep cardinality out of `Decreases` measures.

- **Limitation**: `==` on nested lists cannot be proved. `list.__eq__` compares elements with the generic object equality, which Nagini does not connect to a list's contents, so `a == b` fails for `List[List[int]]` or `List[Tuple[List[int], List[int]]]` even when every inner list is provably equal. Equality of flat lists (`List[int]`) and of tuples of non-list values works.
  **Workaround**: Compare element-wise down to the flat lists: `len(a) == len(b)`, then `a[i][0] == b[i][0]` and so on for each position. In contracts, state the contents through `ToSeq` of the inner lists or a pure function over them rather than `==` on the outer list.

- **Limitation**: Bitwise operators on ints (`&`, `|`, `^`, `<<`, `>>`) will cause verification time to explode. Every application converts its operands from the solver's integer theory into a fixed-width bitvector, applies the operation there, and converts the result back; the solver then has to relate facts across the two theories, which it does poorly. A value known only through equalities (a symbolic argument) is much worse than a literal.
  **Workaround**: Never use bitwise operations, instead, express using integer arithmetic with constant divisors (`x & 1` -> `x % 2`, `x >> k` -> `x // 2**k`, `x << k` -> `x * 2**k`). This stays in one theory and is linear, so the solver evaluates it instantly. This is especially crucial for spec vocabulary (pure step functions, predicates, contracts).

- **Limitation**: String support beyond the basics (literals, `+`, `len()`, equality). String methods, formatting, and slicing are largely unsupported.
  **Workaround**: Use lists of integers to represent strings when string reasoning is needed.

- **Limitation**: `print()` is stubbed with a single `object` argument — no varargs, no keyword args, no f-strings. Anything beyond a single argument fails. 
  **Workaround**: A single concatenated string works fine (`print('Adding ' + name)`). Collapse multi-arg prints into one concatenated string, or drop them.

- **Limitation**: Comprehensions are only partially supported. Single-generator comprehensions translate, but the verifier can prove little about the result.  The body must be pure — statements in the body raise `impure.list.comprehension.body`. Multiple generators (`for x in xs for y in ys`) fail translation.
  **Workaround**: When facts about the resulting collection are needed, rewrite as an explicit loop with invariants.

- **Limitation**: Conditional imports (an `import` inside `if` or `try`) are not supported. Names bound by a guarded import are not resolved, and using them fails translation with `Not supported: Unsupported builtin function '<name>'`. Imports must be unconditional top-level statements.
  **Workaround**: Refactor to remove the import cycle (e.g., split a class that constructs its sub-components into a data-only class plus a separate factory module) so the import can be unconditional.

- **Limitation**: Operations that allocate new heap objects, like `list.copy()`, are rejected inside `@Pure` functions.
  **Workaround**: They work in regular (non-pure) method bodies. For lists, you can also use translation to a PSeq.

- **Limitation**: User-defined `__lt__`/`__le__`/`__gt__`/`__ge__` dunders do not work with the `min()` and `max()` builtins — their contracts expect numeric types. A `@Pure` comparison dunder does drive the comparison operators (`<`, `<=`, `>`, `>=`).
  **Workaround**: For `min()`/`max()`, add explicit comparison-based helpers on the class and rewrite call sites.

- **Limitation**: `for x in c` loops  are difficult to verify. The encoding borrows permissions to `c` and adds hidden invariant conjuncts, so getting the invariants right is hard and unintuitive.
  **Workaround**: Use an indexed `while i < len(xs):` loop whenever there is an index.