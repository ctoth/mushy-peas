# MUSH Softcode Parser Plan

This plan is for building a lossless, oracle-validated PennMUSH softcode parser
and then layering progressively richer semantic analysis over it.

The goal is not to invent a clean language that real softcode does not obey. The
goal is to expose the structure PennMUSH actually recognizes, preserve exact
source text, and then build useful semantic projections on top.

## Parser Strategy

Use a handwritten parser for the core CST.

Do not use Lark for the PennMUSH core. `process_expression()` is not a clean
context-free grammar:

- evaluation flags change what syntax is active;
- termination flags change where recursive parses stop;
- function metadata changes argument parsing;
- `FN_NOPARSE` and `FN_LITERAL` alter recursion and delimiter behavior;
- braces suppress function checks in specific modes;
- unknown functions can be treated as literal text unless mandatory function
  checking is active;
- parsing and evaluation are historically intertwined.

A handwritten recursive scanner can model those rules directly and can be
compared against the PennMUSH trace oracle at the same decision points.

Lark may still be useful later for small regular sublanguages, such as report
formats, profile-specific declarations, or a constrained query language over the
semantic graph. It should not own the core softcode parse.

## Ground Rules

Every stage must preserve these invariants:

- Parsed source can be rendered back byte-for-byte.
- Every node has exact source spans.
- PennMUSH trace output is the authority for core parse boundaries.
- Hypothesis failures become regression fixtures.
- Real corpus examples become permanent examples.
- Unknown or dynamic behavior is represented explicitly, not guessed away.
- Higher-level AST and semantic views must point back to CST spans.

## Repository Targets

The initial implementation should live in `mushy_peas.softcode`, with tests in
`tests/softcode` and oracle tests in `tests/oracle`.

Proposed module layout:

```text
mushy_peas/softcode/__init__.py
mushy_peas/softcode/model.py
mushy_peas/softcode/render.py
mushy_peas/softcode/parser.py
mushy_peas/softcode/function_metadata.py
mushy_peas/softcode/inventory.py
mushy_peas/softcode/profiles.py
mushy_peas/softcode/actions.py
mushy_peas/softcode/ast_views.py
mushy_peas/softcode/graph.py
tests/softcode/test_model.py
tests/softcode/test_render.py
tests/softcode/test_parser.py
tests/softcode/test_inventory.py
tests/softcode/test_actions.py
tests/softcode/test_graph.py
```

The first implementation should not add every module at once. Add modules only
when the corresponding stage needs them.

Default verification commands:

```powershell
uv run ruff check .
uv run mypy .
uv run pyright
uv run pytest
```

Targeted commands should be added per stage, but the full gate above remains the
authority before declaring a stage complete.

Current artifact regeneration commands:

```powershell
uv run python -m mushy_peas.softcode.inventory C:\Users\Q\src\wcnh\systems\softcode C:\Users\Q\src\mushcode C:\Users\Q\src\pennmush\test --report reports\softcode-inventory.md

uv run mush-softcode-functions C:\Users\Q\src\pennmush --output tests\fixtures\softcode\pennmush-functions.json --pennmush-commit 4d1d4a9e5cfc3c227b213de242721092a970ad41

uv run python -m mushy_peas.softcode.units C:\Users\Q\src\wcnh\systems\softcode C:\Users\Q\src\mushcode C:\Users\Q\src\pennmush\test --report reports\softcode-units.md --json reports\softcode-units.json

uv run python -m mushy_peas.softcode.seeds C:\Users\Q\src\wcnh\systems\softcode C:\Users\Q\src\mushcode C:\Users\Q\src\pennmush\test tests\fixtures\main --output tests\fixtures\softcode\corpus-seeds.json --max-per-kind 50
```

These commands are executable today. The broader Stage 13 CLI names are still
future tooling targets, not current entry points.

## Execution Order

The stages below are ordered. Do not start broad semantic graph work before the
lossless CST and oracle boundary checks exist.

Allowed parallel work:

- corpus inventory can proceed while trace events are being hardened;
- function metadata export can proceed before the full CST parser exists;
- profile classification can proceed once `SoftcodeUnit` extraction exists.

Blocked dependencies:

- CST oracle agreement depends on trace hardening;
- action-list parsing depends on expression CST;
- semantic AST views depend on CST and action-list CST;
- semantic graph depends on unit extraction and AST views.

## Stage Completion Rules

A stage is complete only when:

- its named files or artifacts exist;
- its acceptance criteria are covered by tests or generated reports;
- the relevant targeted tests pass;
- the full default verification gate passes;
- any unsupported behavior is documented in a repo-local file.

Passing a narrow test is not stage completion unless the stage acceptance
criteria are narrow enough for that test to cover them.

## Stage 0: Baseline Inventory

Record the current implementation authorities and corpora.

Inputs:

- `C:/Users/Q/src/pennmush`
- `C:/Users/Q/src/wcnh`
- `C:/Users/Q/src/mushcode`
- `mushy-peas` database readers
- any extracted PennMUSH DB attributes available locally

Outputs:

- inventory note listing available corpora;
- counts by source repository;
- counts by file type and candidate softcode unit type;
- explicit list of skipped directories and why.

Implementation target:

- `mushy_peas/softcode/inventory.py`
- `tests/softcode/test_inventory.py`
- generated report path such as `reports/softcode-inventory.md`

Initial CLI or callable API:

```text
collect_softcode_inventory(paths: list[Path]) -> SoftcodeInventory
```

Suggested first paths:

```text
C:/Users/Q/src/wcnh/systems/softcode
C:/Users/Q/src/mushcode
C:/Users/Q/src/pennmush/test
```

Acceptance:

- The inventory can be regenerated.
- The inventory distinguishes source code, data files, docs, and softcode.
- The inventory does not mutate any corpus repository.
- The report includes exact path counts and candidate unit counts.
- The test suite uses temporary fixtures for parser behavior and marks external
  corpus inventory tests as skipped unless those paths exist.

Current status:

- Done: `mushy_peas/softcode/inventory.py` provides a read-only
  `collect_softcode_inventory(paths)` API.
- Done: `reports/softcode-inventory.md` records current local counts for WCNH
  softcode, `mushcode`, and PennMUSH tests.
- Done: tests use temporary fixtures and cover missing roots, skipped
  directories, file-kind classification, unit-kind classification, and report
  determinism.
- Limitation: the first unit counter recognizes PennMUSH-style attribute
  install-script lines. PennMUSH `.t` tests are classified as softcode files,
  but they do not yet produce expression-level seed units.

## Stage 1: Harden The PennMUSH Trace Oracle

The current oracle proves the path works. It must become rich enough to compare
our parser's boundaries against PennMUSH's own decisions.

Add or refine trace events for:

- recursive `process_expression()` entry;
- recursive exit;
- copied literal spans;
- terminators selected by `tflags`;
- brace groups;
- eval groups;
- percent substitutions;
- dollar substitutions;
- escape handling;
- function lookup;
- unknown function handling;
- function metadata: name, flags, min args, max args;
- raw function source span;
- raw argument source span;
- evaluated argument value;
- denied function path;
- `FN_NOPARSE` behavior;
- `FN_LITERAL` behavior;
- function arity errors.

Acceptance:

- Python can request a trace for one expression through real `netmud`.
- Trace output is valid JSONL.
- Trace spans refer to offsets in the original input.
- Trace output is stable enough for tests.
- Existing PennMUSH server-load oracle tests still pass.

Implementation target:

- `C:/Users/Q/src/pennmush/src/parse.c`
- `C:/Users/Q/src/pennmush/src/bsd.c`
- `C:/Users/Q/src/pennmush/hdrs/parse.h`
- `tests/oracle/pennmush_softcode_oracle.py`
- `tests/oracle/test_pennmush_softcode_oracle.py`

Targeted verification:

```powershell
uv run pytest tests/oracle/test_pennmush_softcode_oracle.py
uv run pytest tests/oracle/test_pennmush_oracle.py tests/oracle/test_pennmush_softcode_oracle.py
```

PennMUSH verification:

```powershell
wsl -u q -- bash -lc "cd /mnt/c/Users/Q/src/pennmush && make -j4"
```

Current status:

- Done: the trace includes recursive `enter` and `exit` events.
- Done: the trace includes function lookup events with function name, flags,
  minimum args, and maximum args.
- Done: the trace includes raw and evaluated argument data for ordinary,
  `FN_NOPARSE`, and `FN_LITERAL` functions.
- Done: the trace includes `terminator` events with delimiter spans,
  delimiter text, and active `tflags` when `process_expression()` exits on a
  tflag-selected terminator.
- Done: the trace includes `literal` events with source spans, raw text, and
  copied value for non-speculative literal chunks, literal-mode delimiters,
  copied default-path punctuation, compressed/uncompressed space copies, ANSI
  passthrough, non-evaluating percent copies, and markup tag bytes covered by
  the fast literal chunk path.
- Done: speculative function-name prefixes before `(` are deliberately not
  reported as `literal` events; successful calls are represented by `function`
  events and failed calls are represented by `unknown_function` events.
- Done: the trace includes complete `brace_group` and `eval_group` source spans
  after their recursive parses consume the closing delimiter.
- Done: the trace includes `percent_sub` events with source spans, raw source
  text, and produced value for evaluated percent substitutions.
- Done: the trace includes `dollar_sub` events with raw source text and
  produced value for regexp replacement substitutions such as `regedit()`.
  Byte-identical copied replacement argument buffers are temporarily mapped
  back to their original input spans; transformed copied buffers remain
  unmapped rather than reporting false source offsets.
- Done: the trace includes `escape` events with source spans, raw source text,
  and produced value for evaluated backslash escapes, literal-mode backslashes,
  and trailing backslashes.
- Done: the trace includes `arity_error` events with source spans, raw call
  text, function metadata, actual argument count, and produced error value.
- Done: the trace includes `unknown_function` events with source spans,
  normalized function names, raw call text, produced values, and a mandatory
  mode flag that distinguishes literal fallback from eval-bracket errors.
- Done: the trace includes `denied_function` events for config-disabled
  functions, with source spans, function metadata, actual argument count, raw
  call text, denial reason, and produced error value.
- Done: the trace includes `denied_function` events for non-disabled
  permission-denied functions by running the trace oracle with a non-God
  executor.
- Done: the trace includes `function_limit` events for function invocation
  and recursion limit failures, with source spans, function metadata, raw call
  text, limit reason, and produced error value.
- Done: every required Stage 1 trace event family above is either emitted with
  original-input spans or deliberately left unmapped only when a copied buffer
  no longer has a byte-identical source span.

Not complete until every required event family above is either emitted with
spans or documented as unsupported with a test fixture.

Status: complete for the required trace event families as of 2026-06-28.

## Stage 2: Function Metadata Export

The parser needs PennMUSH function metadata without hand-maintained guesses.

Generate or extract:

- function name;
- alias or clone information when observable;
- min args;
- max args;
- flags;
- builtin versus user-defined where observable;
- `FN_NOPARSE`;
- `FN_LITERAL`;
- `FN_LOCALIZE`;
- `FN_STRIPANSI`;
- `FN_BUILTIN`;
- `FN_USERFN`.

Possible approaches:

- add a PennMUSH trace/list mode that dumps function metadata as JSONL;
- parse `function.c` only as a fallback;
- store generated metadata as a test fixture with provenance.

Acceptance:

- Parser tests use generated metadata.
- Metadata fixture records the PennMUSH commit it came from.
- Tests fail loudly if required metadata is missing.

Implementation target:

- `mushy_peas/softcode/function_metadata.py`
- `tests/softcode/test_function_metadata.py`
- fixture such as `tests/fixtures/softcode/pennmush-functions.json`

Minimum metadata model:

```text
FunctionMetadata
  name: str
  min_args: int
  max_args: int
  flags: int
  is_builtin: bool
```

First acceptance tests:

- `ADD` exists and has two required args.
- at least one `FN_NOPARSE` function is present.
- at least one `FN_LITERAL` function is present.
- fixture provenance includes PennMUSH commit SHA.

Current status:

- Done: `mush-softcode-functions` regenerates
  `tests/fixtures/softcode/pennmush-functions.json` from the PennMUSH source
  table.
- Done: the generated fixture records PennMUSH commit
  `4d1d4a9e5cfc3c227b213de242721092a970ad41`.
- Done: the fixture currently contains 527 non-debug built-in source-table
  entries and parser tests consume it.
- Limitation: this source-table fixture does not include runtime user-defined
  `@function` entries, `@function/alias` additions, or config-time function
  restrictions.

## Stage 3: Softcode Unit Extraction

Create a neutral source-unit model before parsing expressions.

Model:

```text
SoftcodeUnit
  id
  source_path
  source_kind
  profile_hint
  object_ref
  attribute_name
  attribute_kind
  command_pattern
  body
  source_span
```

Attribute kinds:

- `cmd`
- `fn`
- `map`
- `filter`
- `lock`
- `data`
- `doc`
- `raw`
- `unknown`

Sources:

- WCNH `.mush` files;
- Volund/mushcode files;
- PennMUSH test softcode;
- database attrs read by `mushy-peas`;
- future user-provided DB dumps.

Acceptance:

- Extraction is read-only for source corpora.
- Units can be serialized to JSON.
- Unit IDs are stable.
- WCNH naming conventions classify `cmd.`, `fn.`, `map.`, and `filter.`
  attributes.
- Unknown units are preserved, not dropped.

First implementation slice:

- parse `.mush` files as line-oriented install scripts;
- recognize `&ATTR OBJECT=value` forms;
- preserve unrecognized lines as raw units or non-unit records;
- do not try to evaluate object references.

Not complete until WCNH `.mush` files produce stable unit IDs and a reproducible
count report.

Current status:

- Done: `mushy_peas/softcode/units.py` extracts JSON-serializable
  `SoftcodeUnit` records from inventory softcode files.
- Done: install-script attribute lines become typed units with stable IDs,
  source paths, line numbers, exact source spans, object refs, attribute names,
  command patterns where visible, and bodies.
- Done: non-empty unrecognized softcode lines are preserved as `raw` units.
- Done: `reports/softcode-units.md` records current count totals, and
  `reports/softcode-units.json` records the current ordered unit ledger.
- Done: dash-terminated multi-line attribute install bodies are coalesced into
  their owning units.
- Done: non-attribute `@name target=body` install commands such as `@desc` and
  `@set` become typed `cmd` units, including dash-terminated multi-line
  command bodies.
- Current local corpus total: 11,451 units, including 1,948 `cmd` units and
  2,766 raw preserved lines.
- Limitation: non-attribute install command extraction currently recognizes
  `@name target=body` line forms. It does not yet model command-specific
  semantics such as `@set` switches or `@lock` lock syntax.

## Stage 4: Core Lossless CST

Implement a handwritten parser over source text.

Inputs:

- source text;
- `eflags`;
- `tflags`;
- function metadata;
- dialect/profile options.

Initial CST nodes:

```text
Document
Text
Escape
PercentSub
DollarSub
BraceGroup
EvalGroup
FunctionCall
Argument
Terminator
Unknown
```

Each node stores:

- kind;
- source start;
- source end;
- children;
- raw text view;
- parse mode information where relevant.

Acceptance:

- `render(parse(x)) == x`.
- Child spans never overlap incoherently.
- Children plus text gaps cover the parent span exactly.
- Parser does not crash on corpus input.
- Unsupported constructs produce `Unknown` nodes with spans.

Implementation target:

- `mushy_peas/softcode/model.py`
- `mushy_peas/softcode/parser.py`
- `mushy_peas/softcode/render.py`
- `tests/softcode/test_parser.py`
- `tests/softcode/test_render.py`

First node dataclasses:

```text
Document(span, children)
Text(span)
Escape(span, raw)
PercentSub(span, raw)
DollarSub(span, raw)
FunctionCall(span, name_span, name, open_paren, arguments, close_paren)
Argument(span, children)
BraceGroup(span, open_brace, children, close_brace)
EvalGroup(span, open_bracket, children, close_bracket)
Terminator(span, value)
Unknown(span, reason)
```

First parser function:

```text
parse_expression(source: str, metadata: FunctionRegistry, mode: ParseMode) -> Document
```

First renderer function:

```text
render(node: Node, source: str) -> str
```

Initial scope:

- literal text;
- escapes;
- percent substitutions;
- dollar substitutions when `ParseMode.dollar_substitutions` is enabled;
- known function calls;
- comma-separated arguments;
- function argument terminators;
- nested known function calls;
- brace groups;
- eval groups;
- unknown function fallback as text or unknown according to mode.

Out of first slice:

- action lists;
- semantic graph.

## Stage 5: Oracle Boundary Agreement

Compare CST output to PennMUSH trace output.

Properties:

- function call spans agree, using the matching `exit` event for the full call
  span when the current trace's `function` event reports only the call prefix
  through the opening parenthesis;
- function names agree after PennMUSH uppercasing rules;
- argument spans agree;
- group spans agree;
- terminator offsets agree;
- rendered source remains exact.

Hypothesis generators:

- plain text;
- nested braces;
- nested eval groups;
- balanced function calls;
- unknown function calls;
- function calls with empty args;
- function calls with trailing spaces;
- escaped delimiters;
- comma and parenthesis edge cases;
- `FN_NOPARSE` examples;
- `FN_LITERAL` examples.

Acceptance:

- Supported generated inputs agree with oracle.
- Every disagreement is either fixed or captured as a known unsupported case.
- Shrunk failures are checked in as fixtures.

Implementation target:

- `tests/softcode/test_oracle_agreement.py`

First property:

```text
For generated add(<int>,<int>) expressions:
  PennMUSH trace function/argument spans == CST function/argument spans
  render(CST) == source
```

Second property:

```text
For generated nested ADD expressions within bounded depth:
  all oracle function events have matching CST FunctionCall nodes
  all oracle argument events have matching CST Argument nodes
```

Not complete until failures report the input, oracle trace, and CST dump.

## Stage 6: Corpus-Seeded Hypothesis

Hypothesis should not only generate toy expressions.

Seed from:

- WCNH command attrs;
- WCNH function attrs;
- mushcode command attrs;
- PennMUSH test files;
- real DB attributes.

Mutation strategies:

- wrap expression in braces;
- wrap expression in eval brackets;
- insert balanced nested calls;
- vary whitespace;
- insert escaped delimiters;
- replace simple literal args with generated expressions;
- splice real arguments into generated calls.

Acceptance:

- Corpus seeds are reproducible.
- Failing seeds identify original source location.
- The test suite keeps a bounded runtime profile.

Implementation target:

- `tests/softcode/strategies.py`
- `tests/fixtures/softcode/corpus-seeds.json`

Runtime rule:

- keep default Hypothesis example counts low for live oracle tests;
- allow a separate slow mark for expanded corpus mutation runs.

Current status:

- Done: `mushy_peas/softcode/seeds.py` extracts bounded deterministic corpus
  seeds from softcode units and PennMUSH `.t` files.
- Done: `tests/fixtures/softcode/corpus-seeds.json` records 201 current seeds:
  50 WCNH command attrs, 50 WCNH function attrs, 50 mushcode command attrs,
  50 PennMUSH `think ...` test expressions, and 1 current PennMUSH main DB
  object attribute seed.
- Done: `tests/softcode/strategies.py` exposes a bounded Hypothesis strategy
  over the checked seed fixture.
- Done: `tests/softcode/strategies.py` exposes bounded corpus mutation
  strategies for braces, eval brackets, whitespace, numeric edits, final
  delimiter deletion, and nested `lit(...)` wrapping.

## Stage 7: Action-List CST

Build a second parser layer for command/action bodies.

This layer must use the expression CST so semicolon splitting is not naive.

Nodes:

```text
ActionList
CommandStmt
CommandName
Switch
CommandArg
Assignment
CommandPattern
RegexCommandPattern
NestedActionBlock
```

Target forms:

- `@pemit %#=...`
- `@assert ...`
- `@wait ...={...; ...}`
- `@switch ...`
- `@dolist ...`
- `@trigger ...`
- `think ...`
- `$pattern:action-list`
- regex command attrs.

Acceptance:

- Action lists round-trip exactly.
- Semicolon boundaries match PennMUSH behavior for braces and eval groups.
- WCNH command attrs classify into command pattern plus body.
- Nested action blocks retain exact text.

Implementation target:

- `mushy_peas/softcode/actions.py`
- `tests/softcode/test_actions.py`

First action slice:

- Done: split top-level semicolon-separated commands;
- Done: preserve exact whitespace and separators as statement/separator spans;
- Done: do not split inside braces, eval groups, escaped semicolons, or known
  function args.

Second action slice:

- Done: classify command name;
- Done: parse simple `command lhs=rhs`;
- Done: classify command pattern attrs, including `$pattern:action-list` and
  `$^regex:action-list` forms.
- Done: classify brace-wrapped nested action blocks on assignment RHS values.
- Done: first command-specific `@trigger` CST classification with target and
  argument spans.
- Done: first command-specific `@dolist` CST classification with list/body
  spans and nested action block reuse.
- Done: first command-specific `@switch` CST classification with subject span
  and top-level comma case splitting.
- Done: first command-specific `@wait` CST classification with delay/body
  spans and nested action block reuse.
- Done: first command-specific `@assert` CST classification with condition
  span.

## Stage 8: Profiles

Profiles describe conventions. They must not change PennMUSH parse truth.

Initial profiles:

- `pennmush-core`
- `wcnh`
- `volund-mushcode`
- `unknown`

Profile metadata:

- command attr prefixes;
- function attr prefixes;
- map/filter naming;
- command prefix conventions;
- indentation conventions;
- expected no-command attrs;
- RPC conventions;
- DB object/file layout conventions.

Acceptance:

- A unit can be parsed without a profile.
- Profiles add classification and warnings.
- Profiles do not hide CST parse failures.

Implementation target:

- `mushy_peas/softcode/profiles.py`
- `tests/softcode/test_profiles.py`

First profile:

- Done: WCNH prefix classification for `cmd.`, `fn.`, `map.`, `filter.`;
- Done: profile classification runs on `SoftcodeUnit` metadata without
  depending on CST parse success.

Not complete until profile output is independent from CST success/failure.

## Stage 9: Structural AST Views

Build AST projections from CST. Do not discard CST.

Views:

```text
FunctionExpr
SubstitutionExpr
BraceExpr
EvalExpr
CommandStmt
AssignmentStmt
EmitStmt
WaitStmt
AssertStmt
SwitchStmt
DolistStmt
TriggerStmt
RpcCall
AttrRead
AttrWrite
DynamicExpr
UnknownExpr
```

Acceptance:

- Every AST node points back to CST spans.
- AST rendering is not the source of truth.
- Ambiguous dynamic forms become `DynamicExpr` or `UnknownExpr`.
- AST construction is total over CST, even if partially unknown.

Implementation target:

- `mushy_peas/softcode/ast_views.py`
- `tests/softcode/test_ast_views.py`

First AST projection:

- Done: `FunctionExpr` from `FunctionCall`;
- Done: `UnknownExpr` from `Unknown`;
- Done: total fallback to `UnknownExpr` for unsupported CST nodes;
- Done: no semantic claims beyond node shape.

Second AST projection:

- Done: `SubstitutionExpr` from `PercentSub` and `DollarSub`;
- Done: `BraceExpr` from `BraceGroup`;
- Done: `EvalExpr` from `EvalGroup`;
- Done: recursive child projection for brace and eval groups.

Action AST projection:

- Done: action-list AST projection retains the action CST;
- Done: `AssignmentStmt` from generic assignment CST;
- Done: `EmitStmt` from `@emit`, `think`, and `@pemit` action CST;
- Done: `AssertStmt` from the first command-specific `@assert` CST node;
- Done: `TriggerStmt`, `DolistStmt`, and `SwitchStmt` from the first
  command-specific action CST nodes;
- Done: `WaitStmt` from the first command-specific `@wait` CST node;
- Done: empty action statements project to `DynamicExpr`.

## Stage 10: Semantic Graph

Build a graph of definitions, references, and effects.

Definitions:

- command attrs;
- function attrs;
- map attrs;
- filter attrs;
- lock attrs;
- data attrs;
- RPC endpoint assumptions.

References:

- `u()`, `ulocal()`, `ufun()`;
- `trigger()`;
- `get()`, `xget()`;
- `%v`, `%w`, `%x`;
- object/dbref literals;
- attr paths;
- lock references;
- `rpc(Module.method, ...)`;
- q-register reads/writes where statically visible.

Effects:

- attr writes;
- q-register writes;
- emits;
- mail;
- waits/queues;
- parent/set/power operations;
- side-effectful functions and commands.

Acceptance:

- "What commands exist?" is answerable.
- "What calls this function attr?" is answerable.
- "What attrs does this unit read/write?" is answerable where static.
- "What RPC endpoints are assumed?" is answerable.
- Dynamic or unresolved edges are explicit.

Implementation target:

- `mushy_peas/softcode/graph.py`
- `tests/softcode/test_graph.py`

First graph slice:

- Done: definitions for WCNH `fn.*` and `cmd.*` units;
- Done: references for literal `u(fn.name,...)` calls;
- Done: unresolved dynamic `u(...)` calls represented explicitly.

Second graph slice:

- Done: references for literal `ufun(fn.name,...)` and
  `ulocal(fn.name,...)` calls;
- Done: unresolved dynamic `ufun(...)` targets represented explicitly.

Third graph slice:

- Done: references for literal `trigger(object/attr,...)` calls;
- Done: unresolved dynamic `trigger(...)` targets represented explicitly.

Fourth graph slice:

- Done: attribute-read edges for literal `get(attr)` and `xget(obj, attr)`;
- Done: unresolved dynamic `get(...)` attribute reads represented explicitly.

Fifth graph slice:

- Done: q-register read edges for `%q0` and `%q<name>` substitutions.

Sixth graph slice:

- Done: q-register write edges for literal `setq(register, value)` calls;
- Done: unresolved dynamic `setq(...)` register writes represented explicitly.

Seventh graph slice:

- Done: RPC endpoint edges for literal `rpc(Module.method, ...)` calls;
- Done: unresolved dynamic `rpc(...)` endpoints represented explicitly.

Eighth graph slice:

- Done: command-effect edges for `@emit`, `@pemit`, and `think`;
- Done: wait/queue effect edges for `@wait` with nested action effects.

Ninth graph slice:

- Done: attribute-write edges for literal `@set object/attr=value` commands;
- Done: unresolved dynamic `@set` targets represented explicitly.

## Stage 11: Semantic Conformance

Move from structural understanding toward best-effort semantic parsing.

Semantic categories:

- pure expression;
- effectful expression;
- command statement;
- command matcher;
- function definition;
- data definition;
- lock expression;
- dynamic eval;
- unknown.

Analysis:

- arity checking against function metadata;
- known side-effect detection;
- command surface extraction;
- static dependency graph;
- unreachable or unused attr candidates;
- profile convention warnings;
- likely typo suggestions using PennMUSH function metadata.

Acceptance:

- Semantic diagnostics are advisory unless proven by PennMUSH.
- No diagnostic claims certainty when runtime data could change the answer.
- Each diagnostic links to source spans and evidence.

Implementation target:

- diagnostics can initially live in `mushy_peas/softcode/graph.py`;
- split to `diagnostics.py` only after there are multiple diagnostic families.

First diagnostic slice:

- Done: advisory profile convention diagnostics from profile warnings;
- Done: diagnostics include unit id, source span, code, message, and evidence.

## Stage 12: Locks And Boolexp

Locks are adjacent to softcode but should be staged separately.

Approach:

- preserve lock text as raw text first;
- add a lossless lock CST only after expression CST is stable;
- use PennMUSH boolexp behavior as oracle where practical.

Acceptance:

- Existing DB lock preservation remains exact.
- Lock parsing does not block softcode parsing.
- Lock semantic AST is opt-in until proven useful.

Execution rule:

- do not start this stage until expression CST and action-list CST are stable.

## Stage 13: Tooling

Expose usable commands.

Candidate CLIs:

```text
mush-softcode-inventory PATH
mush-softcode-parse PATH
mush-softcode-trace EXPR
mush-softcode-graph PATH
mush-softcode-report PATH
```

Outputs:

- JSON CST;
- JSON AST projection;
- graph JSON;
- text report;
- corpus coverage report.

Acceptance:

- CLI failures include file and span context.
- CLI output is deterministic.
- CLI can process WCNH and mushcode without modifying them.

Implementation target:

- extend `mushy_peas/cli.py` only after callable APIs exist;
- avoid adding CLI first as a substitute for library behavior.

First tooling slice:

- Done: deterministic JSON `softcode-coverage` subcommand;
- Done: deterministic JSON `mush-softcode-coverage` script entrypoint.

## Stage 14: Coverage And Maturity Gates

Track progress with explicit gates.

Metrics:

- corpus unit count;
- parsed unit count;
- exact round-trip count;
- oracle agreement count;
- semantic graph extraction count;
- unknown node count;
- unsupported construct categories;
- Hypothesis regression fixture count.

Acceptance:

- Coverage reports are checked into test artifacts or generated reports.
- Regressions are visible.
- Unsupported behavior is named, not buried.

First coverage slice:

- Done: library coverage report for unit, expression-parse, action-parse, graph
  edge, diagnostic, unknown-node, and unsupported-category counts.

## Stage 15: Full Conformance Target

The most complete practical target is:

- lossless CST for PennMUSH expression syntax;
- action-list CST for command bodies;
- profile-aware unit classification;
- semantic AST projections;
- dependency/effect graph;
- oracle-validated boundaries;
- corpus-grounded regression suite;
- explicit unsupported/dynamic cases.

The final target is not a compiler that pretends MUSH is statically knowable.
The final target is a conformant structural parser plus a conservative semantic
model that says exactly what it knows, exactly where it knows it from, and where
PennMUSH runtime behavior remains the only true authority.

## First Implementation Milestone

The first milestone should be deliberately narrow:

1. Harden trace events for function and argument spans.
2. Generate function metadata.
3. Implement the first `Document`, `Text`, `FunctionCall`, and `Argument` CST
   nodes.
4. Prove exact round-trip.
5. Prove `add(<int>,<int>)` and a small set of generated function calls agree
   with PennMUSH trace boundaries.

Only after that should the parser expand to braces, eval groups, substitutions,
and action lists.

## Immediate Next Work Items

Execute these in order. Checked items have been completed in the current
implementation stream:

1. Done: commit this plan once reviewed.
2. Done: add `mushy_peas/softcode/model.py` with span and node dataclasses.
3. Done: add `mushy_peas/softcode/render.py` with source-slice rendering.
4. Done: add tests proving text-only documents round-trip.
5. Done: add function metadata fixture generation or a temporary checked fixture with
   PennMUSH commit provenance.
6. Done: add the first handwritten parser slice for `Text`, `FunctionCall`, and
   `Argument`.
7. Done: add targeted oracle agreement for `add(<int>,<int>)`.
8. Done: expand function and argument oracle trace metadata before expanding
   parser syntax.

Do not begin action-list parsing until item 7 passes.

## Current Readiness Answer

As of 2026-06-28, the project has:

- a real PennMUSH trace mode;
- a Python wrapper around that mode;
- live oracle tests;
- Hypothesis available;
- known corpora to inventory;
- a reproducible Stage 0 inventory report for the first three local corpus
  roots;
- initial lossless CST model dataclasses;
- source-slice rendering;
- an initial handwritten parser for text, escapes, percent substitutions,
  context-gated dollar substitutions, brace/eval groups, known function calls,
  arguments, and function argument terminators;
- a first action-list CST slice for top-level semicolon splitting that respects
  expression CST protected spans;
- action-list command-name and simple assignment classification;
- command-pattern attribute classification for plain and regex command attrs;
- brace-wrapped nested action block parsing with exact inner action spans;
- WCNH profile-aware unit classification independent from CST success;
- first semantic AST projection for function calls and unknown CST nodes;
- semantic AST projection for substitutions, brace groups, and eval groups;
- first command-specific `@trigger` CST classification;
- first command-specific `@dolist` CST classification;
- first command-specific `@switch` CST classification;
- first command-specific `@wait` CST classification;
- first command-specific `@assert` CST classification;
- action-level AST projections for assignment, trigger, dolist, switch, and
  wait plus assert, emit, and empty dynamic statements;
- first semantic graph slice for WCNH command/function definitions and literal
  or dynamic `u(...)` references;
- semantic graph references for literal `ufun(...)` and `ulocal(...)` calls;
- semantic graph references for literal or dynamic `trigger(...)` calls;
- semantic graph attribute-read edges for literal `get(...)` and `xget(...)`
  calls;
- semantic graph q-register read edges for `%q` substitutions;
- semantic graph q-register write edges for `setq(...)` calls;
- semantic graph RPC endpoint edges for `rpc(...)` calls;
- semantic graph command-effect edges for emits and waits/queues;
- semantic graph attribute-write edges for `@set` commands;
- first advisory semantic diagnostics for profile convention warnings;
- first coverage report API with parser, graph, diagnostic, unknown-node, and
  unsupported-category counts;
- first softcode coverage CLI and script entrypoint;
- a generated PennMUSH function metadata fixture with commit provenance;
- stable, JSON-serializable softcode units and a reproducible unit ledger for
  the first corpus roots;
- bounded corpus seed extraction from WCNH attrs, mushcode command attrs,
  PennMUSH `.t` expressions, and current PennMUSH main DB object attributes;
- bounded corpus mutation strategies beyond fixture sampling;
- PennMUSH trace terminator events for tflag-selected delimiters;
- PennMUSH trace literal events for non-speculative literal chunks,
  literal-mode delimiters, default-path punctuation, copied spaces, ANSI
  passthrough, non-evaluating percent copies, and tag-byte literal chunks;
- PennMUSH trace brace/eval group events with complete source spans;
- PennMUSH trace percent-substitution events with raw and produced values;
- PennMUSH trace dollar-substitution events with raw and produced values,
  including original-input spans for byte-identical copied replacement buffers;
- PennMUSH trace escape events with raw and produced values, including
  trailing and literal-mode backslash edges;
- PennMUSH trace function arity-error events with raw call text and produced
  error values;
- PennMUSH trace unknown-function events for both literal fallback and
  mandatory-function error paths;
- PennMUSH trace disabled-function denial events using per-run oracle
  restrictions;
- PennMUSH trace permission-denied function events using per-run trace
  executor selection;
- PennMUSH trace function invocation-limit and recursion-limit events using
  per-run oracle config;
- targeted oracle agreement for generated `add(<int>,<int>)` expressions.

The PennMUSH trace oracle now reports function metadata and argument raw/value
pairs for ordinary functions, `FN_LITERAL`, and `FN_NOPARSE`. Live traces show
that `FN_LITERAL` and `FN_NOPARSE` still produce recursive `enter` and `exit`
scan events inside their argument text, but they do not produce nested
`function` events for inner calls such as `add(...)`.

The project does not yet have:

- a full expression CST;
- richer command-specific action CST for `@switch`, `@dolist`, and `@trigger`;
- complete semantic AST views;
- complete semantic graph extraction;
- complete maturity and coverage gates.

Therefore the project is past the first parser skeleton, but it is still not
ready to claim that the full parser apparatus exists. The next execution slice
should continue semantic AST view construction beyond the first expression
projection or command-specific action body parsing.
