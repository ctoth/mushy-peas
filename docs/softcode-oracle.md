# PennMUSH Softcode Trace Oracle

`tests/oracle/pennmush_oracle.py` proves that generated database files load in a
real PennMUSH server. Softcode parsing needs a different oracle: a
machine-readable trace of PennMUSH's own `process_expression()` decisions.

The oracle uses the WSL PennMUSH checkout at:

```text
C:/Users/Q/src/pennmush
```

`tests/oracle/pennmush_softcode_oracle.py` creates a disposable game directory,
feeds one expression to stdin, runs `netmud`, and extracts JSONL lines from
`log/netmush.log`:

```text
netmud --no-session --softcode-trace-jsonl --eflags PE_DEFAULT --tflags PT_DEFAULT mush.cnf
```

Each line is a JSON object. All non-result events share:

- `kind`
- `depth`
- optional source span fields: `source_start`, `source_end`
- optional output span fields: `output_start`, `output_end`

Function events include:

- `function_name`
- `function_flags`
- `min_args`
- `max_args`

Argument events include:

- `argument_index`
- `raw`: the exact source slice consumed for the argument
- `value`: the evaluated or processed value passed to the function

The final line must be:

```json
{"kind":"result","value":"..."}
```

## Event Kinds

- `enter`: recursive `process_expression()` entry.
- `exit`: recursive `process_expression()` exit.
- `literal`: copied literal text.
- `percent_sub`: percent substitution handling.
- `brace_group`: `{...}` parse group handling.
- `eval_group`: `[...]` evaluation group handling.
- `function`: resolved function call, including function metadata.
- `argument`: captured function argument, including raw source and processed
  value.
- `terminator`: stop character selected by `tflags`.

Current live checks cover:

- ordinary parsed arguments such as `add(1,2)`;
- `FN_LITERAL` argument capture such as `lit(add(1,2))`;
- `FN_NOPARSE` argument capture such as `@@(add(1,2))`.

For `FN_LITERAL` and `FN_NOPARSE`, PennMUSH still emits nested recursive
`enter` and `exit` events while scanning the argument text, but it does not emit
a nested `function` event for the inner `add(...)`. Parser agreement tests
should compare resolved function events separately from lower-level recursive
scan events.

## PennMUSH Patch Points

The source authority is `C:/Users/Q/src/pennmush/src/parse.c`.

The useful instrumentation points are:

- function entry at `process_expression()`;
- `{` handling before the recursive `PT_BRACE` call;
- `[` handling before the recursive `PT_BRACKET` call;
- function resolution after `func_hash_lookup()` / `builtin_func_hash_lookup()`;
- argument capture after each recursive argument parse, before `(*str)++`;
- `exit_sequence` before regular cleanup;
- `bsd.c` command-line parsing, which captures stdin before PennMUSH redirects
  stdout, stderr, and stdin to log files.

This trace is deliberately lower-level than a mushy-peas AST. It should expose
what PennMUSH actually did so Hypothesis can compare our parser's spans,
function boundaries, argument boundaries, and terminators against the oracle.
