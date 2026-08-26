# Nagini Limitations

Things that Nagini genuinely cannot do. Nagini and Viper are more expressive than you might assume — before concluding that a property cannot be expressed or that a workaround is needed, check this list.

**If you believe Nagini cannot express something and it is not listed here, assume you are wrong.** Try the direct encoding first. Only treat it as a real limitation once you have a concrete error demonstrating it.

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
  **Workaround**: Keep aggregates constructive: build collections operation by operation, or track the count in its own variable updated alongside every mutation. Keep cardinality out of `Decreases` measures — use fuel-bounded recursion instead.

- **Limitation**: Bitwise operators on ints (`&`, `|`, `^`, `<<`, `>>`) encode through an int-to-bitvector bridge that is very expensive for the solver, especially under quantifiers or in loop invariants — proofs that touch them often time out.
  **Workaround**: When values are nonnegative and the width permits, use the arithmetic equivalents instead (`x & 1` -> `x % 2`, `x >> k` -> `x // 2**k`, `x << k` -> `x * 2**k`); they verify orders of magnitude faster.

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

- **Limitation**: `==` can fail to prove where `is` succeeds. For primitive types like `int` the two *should* be interchangeable, but Nagini internals sometimes leave `==` facts unprovable.
  **Workaround**: Prefer `is`/`is not` for all comparisons — for references, identity is almost always the intended meaning anyway.

- **Limitation**: `for x in iterable:` loops are difficult to verify. The iterator holds part of the iterable's `list_pred` for the loop's duration and references the elements in a way that makes it hard to state anything about it in invariants. On top of that, the iterator translation has some bugs and rough edges that cause unexpected framing and permission failures.
  **Workaround**: Use an indexed `while i < len(xs):` loop instead.