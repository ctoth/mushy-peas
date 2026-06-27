# mushy-peas execution plan

## Scope

Build a Python reader/writer toolkit for PennMUSH database files.

This project is not a LambdaMOO reader, not a LambdaMOO/PennMUSH converter, and
not a shared abstraction over both families. `lambdamoo-db-py` is useful only as
an example of project shape and round-trip discipline. The implementation target
is PennMUSH's on-disk database family.

Supported deliverables:

- main object database, current labeled format;
- main object database, oldstyle readable formats covered by PennMUSH `dbtools`;
- gzip-compressed, bzip2-compressed, and explicitly configured external-filter
  database files for main, mail, and chat paths;
- mail database, including mail aliases;
- chat database, current labeled format;
- chat database, oldstyle readable format.

The current main object database format is PennMUSH's labeled flatfile format as
emitted by the checked-out PennMUSH tree:

- header line: `+V...`
- optional/current `dbversion`
- `savedtime`
- global `+FLAGS LIST`
- global `+POWER LIST`
- global `+ATTRIBUTES LIST`
- object capacity line: `~<count>`
- object records: `!<dbref>`
- end marker: `***END OF DUMP***`

The current mail database format is the format emitted by `dump_mail()`: an
optional `+<mail_flags>` header, optional mail aliases, message count, message
records, and an end marker.

The current chat database format is the format emitted by `save_chatdb()`: a
`+V<chat_flags>` header, `savedtime`, channel count, labeled channel records,
labeled channel-user records, and an end marker.

## Non-goals

- Do not parse or write LambdaMOO databases.
- Do not model LambdaMOO values, tasks, waifs, anonymous objects, verbs, or
  v4/v17 sections.
- Do not create a conversion layer between MOO and MUSH.
- Do not use our own writer output as the only proof of correctness.
- Do not normalize away source data needed for round-trip fidelity unless the
  mode explicitly says it is semantic-only.
- Do not defer a PennMUSH format merely because it is older or auxiliary if the
  PennMUSH source contains the reader/writer code for it.

## Source authority

The PennMUSH source tree is the format authority.

Primary files:

- `C:\Users\Q\src\pennmush\src\db.c`
- `C:\Users\Q\src\pennmush\src\extmail.c`
- `C:\Users\Q\src\pennmush\src\malias.c`
- `C:\Users\Q\src\pennmush\src\extchat.c`
- `C:\Users\Q\src\pennmush\src\game.c`
- `C:\Users\Q\src\pennmush\dbtools\db_labelsv1.cpp`
- `C:\Users\Q\src\pennmush\dbtools\db_oldstyle.cpp`
- `C:\Users\Q\src\pennmush\dbtools\io_primitives.cpp`
- `C:\Users\Q\src\pennmush\dbtools\database.h`
- `C:\Users\Q\src\pennmush\hdrs\extmail.h`
- `C:\Users\Q\src\pennmush\hdrs\extchat.h`

Important contracts observed from those files:

- `+V` stores DB flags as `((value - 2) / 256) - 5`.
- Current writer emits DB version `6`.
- Current object types are numeric:
  - room: `0x1`
  - thing: `0x2`
  - exit: `0x4`
  - player: `0x8`
  - garbage: `0x10`
- Current labeled objects contain, in writer order:
  - `name`
  - `location`
  - `contents`
  - `exits`
  - `next`
  - `parent`
  - `lockcount` plus lock records
  - `owner`
  - `zone`
  - `pennies`
  - `type`
  - `flags`
  - `powers`
  - `warnings`
  - `created`
  - `modified`
  - `attrcount` plus object attribute records
- Quoted strings escape only `"` and `\` by prefixing `\`.
- Missing object numbers inside the `~<count>` range represent garbage slots.
- The current reader accepts labeled fields by name, but the writer should emit
  the canonical PennMUSH order.
- `dbtools` supports uncompressed, gzip, and bzip2 main databases.
- PennMUSH runtime compression can also be configured through external programs
  in `game.c`; Python support should include built-in gzip and bzip2 plus an
  explicit external filter mode for workflows such as old `.Z` files.
- `dump_mail()` writes mail flags `MDBF_SUBJECT`, `MDBF_ALIASES`,
  `MDBF_NEW_EOD`, and `MDBF_SENDERCTIME`.
- `save_malias()` stores mail aliases before message count when
  `MDBF_ALIASES` is present.
- `save_chatdb()` writes chat flags with `CDB_SPIFFY` and labeled channel
  fields.
- `load_chatdb()` falls back to oldstyle chat parsing when the file does not
  begin with `+V`.

Observed oracle behavior from the checked-out PennMUSH tree:

- PennMUSH built successfully under WSL Debian with:
  - `./configure --disable-sql --disable-info_slave --disable-ssl_slave`
  - `make -j4`
- The built server is `C:\Users\Q\src\pennmush\src\netmud`.
- The server refuses to run as root; run it through the WSL `q` user.
- `src/netmud --version` reports `PennMUSH 1.8.8 patchlevel 0`.
- A clean oracle run uses a copied `game/` tree under `/tmp`, not the source
  checkout's live `game/` directory.
- Send SIGINT for shutdown. SIGTERM is wired to PennMUSH panic handling and
  creates `PANIC.db`; it is not an acceptable oracle stop signal.
- GNU `timeout` returns non-zero when it sends SIGINT, so acceptance must be
  based on log markers, not process exit alone.
- Successful all-DB load markers are:
  - `LOADING: data/indb`
  - `LOADING: data/indb (done)`
  - `LOADING: data/maildb`
  - `LOADING: data/maildb (done)`
  - `LOADING: data/chatdb`
  - `LOADING: data/chatdb (done)`
  - `RESTART FINISHED.`
  - `MUSH shutdown completed.`
- Failure markers include `ERROR: Unable to read mail database!`,
  `ERROR: Unable to read chat database!`, `PANIC:`, and missing `(done)` lines.
- With `compress_suffix` set, PennMUSH appends that suffix to main, mail, and
  chat configured filenames. Compressed oracle fixtures must therefore prepare
  all three files consistently, such as `indb.gz`, `maildb.gz`, and
  `chatdb.gz`.
- `uncompress_program gunzip` takes the libz path; `uncompress_program bunzip2`
  takes the external pipe path. Both paths have been proven against generated
  baseline main/mail/chat files.

## Package shape

Use a small package with format-specific names.

```text
mushy_peas/
  __init__.py
  cli.py
  compression.py
  constants.py
  errors.py
  main_model.py
  main_reader.py
  main_writer.py
  mail_model.py
  mail_reader.py
  mail_writer.py
  chat_model.py
  chat_reader.py
  chat_writer.py
  oldstyle.py
  primitives.py
tests/
  fixtures/
  oracle/
  test_primitives.py
  test_properties.py
  test_main_reader.py
  test_main_writer.py
  test_main_oldstyle.py
  test_mail_reader.py
  test_mail_writer.py
  test_chat_reader.py
  test_chat_writer.py
  test_compression.py
  test_roundtrip.py
```

File responsibilities:

- `compression.py`: open uncompressed, gzip, bzip2, and explicit-filter
  database streams.
- `constants.py`: DBF, MDBF, CDB, object type, and writer default constants.
- `errors.py`: parse errors with file, line, expected value, and actual text.
- `main_model.py`: dataclasses for object databases.
- `mail_model.py`: dataclasses for mail databases and mail aliases.
- `chat_model.py`: dataclasses for chat databases, channels, locks, and users.
- `primitives.py`: line reader, label parsing, quoted string parsing/writing,
  dbref parsing/writing, DB header flag decoding/encoding, and shared EOD
  handling.
- `main_reader.py`: parse current labeled main object databases.
- `main_writer.py`: write current labeled main object databases.
- `oldstyle.py`: parse oldstyle main object databases and oldstyle chatdbs.
- `mail_reader.py`: parse maildb files.
- `mail_writer.py`: write maildb files.
- `chat_reader.py`: parse current labeled chatdb files.
- `chat_writer.py`: write current labeled chatdb files.
- `cli.py`: thin commands for inspection and verification.
- `tests/oracle/`: repo-local oracle harness code and log parsing helpers. The
  harness shells out to the built PennMUSH server; it is test support, not
  production library code.

## Data model

The model should preserve source details needed for round-trip work.

`PennMainDatabase`:

- `raw_dbflags: int`
- `dbversion: int | None`
- `savedtime: str`
- `flags: dict[str, PennFlag]`
- `powers: dict[str, PennFlag]`
- `attributes: dict[str, PennAttribute]`
- `objects: dict[int, PennObject]`
- `object_count: int`
- `line_ending: str`
- `format_kind: Literal["main-current", "main-oldstyle"]`

`PennFlag`:

- `name: str`
- `letter: str`
- `types: tuple[str, ...]`
- `perms: tuple[str, ...]`
- `negate_perms: tuple[str, ...]`
- `aliases: tuple[str, ...]`

`PennAttribute`:

- `name: str`
- `flags: tuple[str, ...]`
- `creator: int`
- `data: str`
- `aliases: tuple[str, ...]`

`PennLock`:

- `type: str`
- `creator: int`
- `flags: tuple[str, ...]`
- `derefs: int`
- `key: str`

`PennObject`:

- `dbref: int`
- `name: str`
- `location: int`
- `contents: int`
- `exits: int`
- `next: int`
- `parent: int`
- `locks: dict[str, PennLock]`
- `owner: int`
- `zone: int`
- `pennies: int`
- `type: int`
- `flags: tuple[str, ...]`
- `powers: tuple[str, ...]`
- `warnings: tuple[str, ...]`
- `created: int`
- `modified: int`
- `attributes: dict[str, PennAttribute]`

Represent garbage by absence from `objects` inside `range(object_count)`, not by
inventing fake object records unless a source fixture requires preserving an
explicit garbage record.

`PennMailDatabase`:

- `raw_mail_flags: int`
- `aliases: list[PennMailAlias]`
- `messages: list[PennMailMessage]`
- `eod: str`
- `line_ending: str`

`PennMailAlias`:

- `owner: int`
- `name: str`
- `description: str`
- `name_flags: int`
- `member_flags: int`
- `members: tuple[int, ...]`

`PennMailMessage`:

- `to: int`
- `from_: int`
- `from_ctime: int`
- `time_text: str`
- `subject: str`
- `body: str`
- `read_flags: int`

`PennChatDatabase`:

- `raw_chat_flags: int`
- `savedtime: str | None`
- `channels: list[PennChannel]`
- `format_kind: Literal["chat-current", "chat-oldstyle"]`
- `line_ending: str`

`PennChannel`:

- `name: str`
- `description: str`
- `flags: int`
- `creator: int`
- `cost: int`
- `buffer_blocks: int | None`
- `mogrifier: int | None`
- `locks: dict[str, str]`
- `users: list[PennChannelUser]`

`PennChannelUser`:

- `dbref: int`
- `flags: int`
- `title: str`

## Phase 0: project bootstrap

Goal: create a Python package that can run tests without implementing format
logic yet.

Tasks:

1. Create `pyproject.toml` with a package named `mushy-peas`.
2. Use `uv` for all Python commands.
3. Add `pytest` and `hypothesis` as test authorities.
4. Add empty package files and a trivial smoke test.
5. Add fixture directories:
   - `tests/fixtures/main/`
   - `tests/fixtures/mail/`
   - `tests/fixtures/chat/`
   - `tests/fixtures/oldstyle/`

Acceptance:

- `uv run pytest` runs and passes.
- No unrelated untracked source directories are staged or committed.

## Phase 1: primitives

Goal: implement the irreversible low-level rules before object parsing.

Tasks:

1. Implement line-ending detection.
2. Implement quoted string read/write:
   - require a leading `"`;
   - unescape `\"` and `\\`;
   - preserve all other escaped characters as the escaped character, matching
     PennMUSH's simple escape behavior;
   - writer escapes only `"` and `\`.
3. Implement labeled line parsing:
   - label is the first non-space token;
   - value is the rest of the line parsed according to the expected type.
4. Implement dbref parsing and writing:
   - read `#<int>`;
   - write `#<int>`.
5. Implement DB flag header decode/encode for `+V`.
6. Implement shared end-marker handling for both current EOD spellings:
   - `***END OF DUMP***`
   - `*** END OF DUMP ***`

Tests:

- quote/backslash round trips;
- labels with leading spaces used in nested records;
- dbrefs including `#-1` and `#-2`;
- known PennMUSH DBF header round trip.
- both EOD spellings parse and write under the appropriate mode.
- Hypothesis-generated quoted strings round-trip through read/write, including
  quotes, backslashes, spaces, tabs, and high latin-1 bytes.
- Hypothesis-generated DBF flag integers round-trip through header
  encode/decode.
- Hypothesis-generated dbrefs round-trip through dbref read/write.

Acceptance:

- `uv run pytest tests/test_primitives.py` passes.
- `uv run pytest tests/test_properties.py -k primitives` passes.

## Phase 1.5: compressed streams

Goal: make compression a real I/O capability, not a caller-side workaround.

Tasks:

1. Implement stream opening for uncompressed files.
2. Implement gzip read/write using Python's standard `gzip`.
3. Implement bzip2 read/write using Python's standard `bz2`.
4. Detect compression by explicit option first and extension second.
5. Implement explicit external-filter read/write mode:
   - caller supplies the decompressor/compressor command;
   - no command is inferred from the file extension;
   - command failures surface as parse/open errors with stderr when available.
6. Support old Unix `.Z` files through the external-filter path.
7. Support `-`/stdin/stdout only for uncompressed text streams in the first
   CLI slice; binary compressed stdin/stdout can be added once the file API is
   stable.

Tests:

- same tiny database fixture reads from plain text, `.gz`, and `.bz2`.
- same tiny database fixture reads through an explicit external filter.
- writer output compressed as `.gz` and `.bz2` decompresses to expected text.
- writer output through an explicit external filter round-trips when a local
  filter command is available.
- wrong compression mode fails with a clear error.

Acceptance:

- `uv run pytest tests/test_compression.py` passes.

## Phase 2: global lists reader

Goal: parse the three global list sections independently.

Tasks:

1. Parse `+FLAGS LIST` into canonical flags plus aliases.
2. Parse `+POWER LIST` using the same structure.
3. Parse `+ATTRIBUTES LIST` into canonical attributes plus aliases.
4. Preserve ordering enough for stable writer output.

Tests:

- hand-written fixture with one flag, one alias, one power, one global attr;
- labels must be exact;
- alias entries must attach to an existing canonical item.
- Hypothesis-generated small global-list sections parse and re-emit with stable
  canonical names, aliases, and word lists.

Acceptance:

- The reader parses global sections from a fixture without reading object data.

## Phase 3: object reader

Goal: parse current PennMUSH object records.

Tasks:

1. Parse `~<object_count>`.
2. Parse each `!<dbref>` record until the next `!` or `*`.
3. Parse object core fields by label.
4. Parse `lockcount` and spiffy lock records:
   - `type`
   - `creator`
   - `flags`
   - `derefs`
   - `key`
5. Parse object attributes:
   - `name`
   - `owner`
   - `flags`
   - `derefs`
   - `value`
6. Reject unknown object labels in strict mode.
7. Preserve object gaps as missing dbrefs.

Tests:

- room object with no locks and no attrs;
- player object with attrs;
- object with multiple locks;
- sparse object range where one dbref is absent.
- Hypothesis-generated small object records parse without losing scalar fields,
  lock records, or object attributes.

Acceptance:

- `read(path)` returns a complete `PennDatabase` for the fixture.
- Invalid labels fail with a line-numbered error.

## Phase 4: writer

Goal: emit canonical current PennMUSH format from the model.

Tasks:

1. Write `+V` using current PennMUSH default flags.
2. Write `dbversion 6`.
3. Preserve `savedtime` by default for round-trip mode.
4. Write global lists in canonical order:
   - flags;
   - powers;
   - attributes.
5. Write `~<object_count>`.
6. Write only non-garbage object records.
7. Write object fields in PennMUSH writer order.
8. Write `***END OF DUMP***`.

Tests:

- primitive writer tests;
- object writer fixture comparison;
- read/write/read semantic equality.
- Hypothesis-generated small `PennDatabase` instances write and read back with
  semantic equality.

Acceptance:

- Writer output can be parsed by our reader.
- Writer output for a controlled fixture matches expected text exactly.

## Phase 4.5: oldstyle main database reader

Goal: read oldstyle PennMUSH main databases using the source-backed dbtools
reader contracts.

Tasks:

1. Port the oldstyle dispatch from `dbtools\db_oldstyle.cpp`.
2. Support quoted and unquoted old strings according to `DBF_NEW_STRINGS`.
3. Support oldstyle object records after `!<dbref>`.
4. Support oldstyle locks:
   - spiffy locks through the shared labeled lock path;
   - `DBF_NEW_LOCKS` `_Type|...` records;
   - pre-new-locks fixed Basic, Use, and Enter locks.
5. Support old flags/powers conversion only to the extent encoded by real
   PennMUSH source tables and fixtures.
6. Write oldstyle input back as current labeled output, matching `dbtools`
   upgrade behavior.

Tests:

- fixture without `DBF_LABELS` reads through `oldstyle.py`.
- oldstyle input writes as current labeled format.
- generated current output is accepted by our current main reader.
- oldstyle lock fixtures preserve parsed lock keys.

Acceptance:

- `uv run pytest tests/test_main_oldstyle.py` passes.
- A real oldstyle fixture is located or generated from an older PennMUSH sample
  and upgrades to current labeled format.

## Phase 4.6: mail database reader/writer

Goal: fully support PennMUSH maildb files, including mail aliases.

Tasks:

1. Implement `MDBF_*` constants:
   - `MDBF_SUBJECT = 0x1`
   - `MDBF_ALIASES = 0x2`
   - `MDBF_NEW_EOD = 0x4`
   - `MDBF_SENDERCTIME = 0x8`
2. Parse optional `+<mail_flags>` header.
3. Parse mail aliases when `MDBF_ALIASES` is set:
   - alias count;
   - owner;
   - name;
   - description;
   - name flags;
   - member flags;
   - member count;
   - member dbrefs;
   - quoted `*** End of MALIAS ***` marker.
4. Parse message count.
5. Parse message records:
   - recipient;
   - sender;
   - sender creation time when `MDBF_SENDERCTIME` is set;
   - time string;
   - subject when `MDBF_SUBJECT` is set;
   - body;
   - read/status flags.
6. Support both mail EOD forms:
   - `***END OF DUMP***` with `MDBF_NEW_EOD`;
   - `*** END OF DUMP ***` without it.
7. Write canonical current maildb output using all current flags emitted by
   `dump_mail()`.

Tests:

- empty maildb with current EOD;
- maildb with aliases and zero messages;
- maildb with one message and subject;
- maildb without subject flag derives no subject in preserve mode and preserves
  body/status fields;
- Hypothesis-generated small maildbs read/write/read semantically.

Acceptance:

- `uv run pytest tests/test_mail_reader.py tests/test_mail_writer.py` passes.
- Writer output follows `dump_mail()` order exactly for fixture cases.

## Phase 4.7: chat database reader/writer

Goal: fully support PennMUSH chatdb files in current labeled and oldstyle forms.

Tasks:

1. Implement `CDB_SPIFFY = 0x01`.
2. Parse current chatdb header:
   - `+V<flags>`;
   - `savedtime`;
   - `channels`.
3. Parse labeled channels:
   - `name`;
   - `description`;
   - `flags`;
   - `creator`;
   - `cost`;
   - `buffer` when `CDB_SPIFFY`;
   - `mogrifier` when `CDB_SPIFFY`;
   - five locks: `join`, `speak`, `modify`, `see`, `hide`;
   - `users`.
4. Parse labeled channel users:
   - `dbref`;
   - `flags`;
   - `title`.
5. Parse oldstyle chatdb when the file does not start with `+V`:
   - channel count;
   - channel name and description;
   - flags, creator, cost;
   - five boolexp locks;
   - users.
6. Write canonical current chatdb output with `CDB_SPIFFY`.
7. Preserve lock text as text; do not build a semantic boolexp AST until a real
   requirement demands lock transformations.

Tests:

- empty current chatdb;
- one current channel with no users;
- one current channel with all lock types and users;
- oldstyle chatdb fixture upgrades to current output;
- Hypothesis-generated small chatdbs read/write/read semantically.

Acceptance:

- `uv run pytest tests/test_chat_reader.py tests/test_chat_writer.py` passes.
- Current writer output follows `save_chatdb()` order exactly for fixture cases.

## Property-based testing strategy

Hypothesis is part of the core plan. Use it where the format has crisp
invariants and many edge cases, but keep examples bounded so failures shrink
quickly and stay readable.

Use Hypothesis for:

- quoted string bodies:
  - empty strings;
  - quotes;
  - backslashes;
  - leading and trailing spaces;
  - tabs;
  - printable latin-1 text;
  - embedded carriage-return characters only if PennMUSH fixtures prove they
    are legal inside current quoted strings.
- labels and word lists:
  - canonical flag names;
  - aliases;
  - permission/type word lists;
  - empty and multi-word lists.
- dbrefs and scalar fields:
  - normal object refs;
  - `#-1` and `#-2`;
  - sparse object ranges;
  - timestamp-sized integers.
- small model round trips:
  - at most 5 objects;
  - at most 3 locks per object;
  - at most 5 attributes per object;
  - at most 5 global flags, powers, and attributes.
- small maildb round trips:
  - at most 5 aliases;
  - at most 5 messages;
  - bounded subjects and bodies;
  - mixed read/status flags.
- small chatdb round trips:
  - at most 5 channels;
  - at most 5 users per channel;
  - all five lock labels;
  - bounded channel names, descriptions, and titles.

Do not use Hypothesis to replace external proof. Property tests prove internal
grammar invariants; real PennMUSH fixtures and PennMUSH tooling prove format
compatibility.

Hypothesis tests should check these invariants:

- `parse(write(x)) == x` for primitives.
- `read(write(db))` is semantically equal to `db` for generated small DBs.
- main, mail, and chat generated DBs keep counts consistent after
  read/write/read.
- writer output never contains unescaped raw quotes inside quoted values.
- strict reader errors always include file and line context.
- generated object gaps remain gaps after read/write/read.

Keep strategies repo-local and reusable:

```text
tests/
  strategies.py
```

Strategy code belongs in tests, not production modules.

## Phase 5: PennMUSH oracle harness and real corpus proof

Goal: prove compatibility against actual PennMUSH artifacts, not circular tests.

Tasks:

1. Add `tests/oracle/pennmush_oracle.py`.
2. Make the oracle harness require an explicit PennMUSH checkout path, defaulting
   to `C:\Users\Q\src\pennmush` when present.
3. Make the harness verify the built server with:
   - `wsl -u q -- bash -lc "cd /mnt/c/Users/Q/src/pennmush && ./src/netmud --version"`
4. If `src/netmud` is absent, build it before running oracle tests:
   - `wsl -- bash -lc "cd /mnt/c/Users/Q/src/pennmush && ./configure --disable-sql --disable-info_slave --disable-ssl_slave"`
   - `wsl -- bash -lc "cd /mnt/c/Users/Q/src/pennmush && make -j4"`
5. Create a disposable oracle game directory under `/tmp/mushy-peas-penn-oracle`
   on each run:
   - copy `game/` from the PennMUSH checkout;
   - copy `aliascnf.dst` to `alias.cnf`;
   - copy `restrictcnf.dst` to `restrict.cnf`;
   - create empty `access.cnf`;
   - ensure `data/`, `log/`, and `save/` exist.
6. Patch only the copied `mush.cnf`:
   - set `port 44201`;
   - set `input_database data/indb`;
   - set `output_database data/outdb`;
   - set `mail_database data/maildb`;
   - set `chat_database data/chatdb`;
   - set compression fields according to the oracle case.
7. Run the server through WSL as user `q`:
   - `timeout -s INT 6s /mnt/c/Users/Q/src/pennmush/src/netmud --no-session mush.cnf`
8. Treat the process exit code as advisory only. Parse `log/netmush.log` for
   required success markers and forbidden failure markers.
9. For uncompressed oracle acceptance, place writer output at:
   - `data/indb`
   - `data/maildb`
   - `data/chatdb`
10. For gzip oracle acceptance, set:
    - `compress_program gzip`
    - `uncompress_program gunzip`
    - `compress_suffix .gz`
    and place files at `data/indb.gz`, `data/maildb.gz`, and `data/chatdb.gz`.
11. For bzip2 oracle acceptance, set:
    - `compress_program bzip2`
    - `uncompress_program bunzip2`
    - `compress_suffix .bz2`
    and place files at `data/indb.bz2`, `data/maildb.bz2`, and `data/chatdb.bz2`.
12. For `.Z` or other legacy external filters, require the user/test
    environment to supply the compressor and decompressor command explicitly;
    do not infer the command from the extension.
13. Build or locate the PennMUSH `dbtools` utilities if Boost is available.
    `dbtools` is useful for main DBs only; it is not the mail/chat oracle.
14. Create or locate real fixtures for:
   - current main object DB;
   - oldstyle main object DB;
   - gzip current main/mail/chat DB set;
   - bzip2 current main/mail/chat DB set;
   - current maildb with aliases and messages;
   - current chatdb;
   - oldstyle chatdb.
15. Parse each fixture with the matching `mushy_peas` reader.
16. Write each fixture back in preserve or canonical mode as appropriate.
17. Compare line-by-line in preserve mode where the source format supports it.
18. Feed generated main DBs to PennMUSH `dbtools/dbupgrade` when available and
    always feed the generated main/mail/chat set to the server load oracle.
19. Record exact commands and fixture provenance in `tests/fixtures/README.md`.

Acceptance:

- Our readers parse real PennMUSH main, mail, and chat DB files.
- Our writers emit DB files accepted by PennMUSH tooling or server load paths.
- The oracle harness rejects logs with mail/chat load errors even if
  `RESTART FINISHED.` is present.
- Gzip and bzip2 oracle runs include main, mail, and chat compressed files, not
  only the main DB.
- Differences, if any, are documented and classified as expected or bugs.

## Phase 6: CLI

Goal: expose only commands that help verify and inspect the format.

Commands:

- `mush-inspect PATH --kind main|mail|chat|auto`
  - for main DB: print db version, object count, non-garbage count, flag count,
    power count, global attribute count.
  - for maildb: print mail flags, alias count, message count.
  - for chatdb: print chat flags, channel count, user count.
- `mush-roundtrip PATH --kind main|mail|chat|auto --out OUT`
  - read and write a DB, then report line differences.
- `mush-dump-json PATH --kind main|mail|chat|auto`
  - dump model JSON for debugging.
- `mush-upgrade PATH --kind main-oldstyle|chat-oldstyle --out OUT`
  - read oldstyle input and write current canonical output.

Acceptance:

- Commands use the same reader/writer code as tests.
- CLI failures include file and line context.

## Phase 7: compatibility fixed point

Goal: close gaps found by real fixtures without widening beyond PennMUSH source
formats.

Tasks:

1. Inventory every fixture failure.
2. Map each failure to a PennMUSH source path before patching.
3. Fix one format family at a time:
   - main current;
   - main oldstyle;
   - mail;
   - chat current;
   - chat oldstyle;
   - compression.
4. Keep each source slice committed or fully reverted before starting the next.
5. Stop when all fixture and external-oracle gates pass.

Acceptance:

- Every supported family has at least one real fixture.
- Every supported family has read/write/read tests.
- Every supported family has external PennMUSH acceptance or a documented
  reason why the exact external oracle is unavailable.

## Verification discipline

Use these gates as the project matures:

```powershell
uv run pytest tests/test_primitives.py
uv run pytest tests/test_properties.py
uv run pytest tests/test_compression.py
uv run pytest tests/test_main_reader.py
uv run pytest tests/test_main_writer.py
uv run pytest tests/test_main_oldstyle.py
uv run pytest tests/test_mail_reader.py
uv run pytest tests/test_mail_writer.py
uv run pytest tests/test_chat_reader.py
uv run pytest tests/test_chat_writer.py
uv run pytest tests/test_roundtrip.py
uv run pytest tests/oracle/test_pennmush_oracle.py
uv run pytest
```

For external proof, use PennMUSH itself or PennMUSH `dbtools`. A passing local
round-trip test does not replace external acceptance.

The oracle test file should expose separate marks or test names for:

- `oracle_uncompressed_main_mail_chat`
- `oracle_gzip_main_mail_chat`
- `oracle_bzip2_main_mail_chat`
- `oracle_rejects_partial_mail_or_chat_load`

## First implementation slice

The first code slice should be small:

1. Bootstrap package and tests.
2. Implement `constants.py`, `errors.py`, and `primitives.py`.
3. Add primitive example tests and Hypothesis primitive properties.
4. Commit that slice before starting the reader.

The second code slice should make compressed stream handling real:

1. Implement `compression.py`.
2. Add `.gz` and `.bz2` fixture tests.
3. Commit that slice before starting format-specific readers.

Then proceed by family, committing each kept slice:

1. current main object DB reader;
2. current main object DB writer;
3. oldstyle main reader and current-format upgrade writer path;
4. maildb reader/writer;
5. current chatdb reader/writer;
6. oldstyle chatdb reader and current-format upgrade writer path;
7. external oracle fixture harness.

Do not begin family-specific parsing until the primitive and compression layers
are green. Those layers are the shared contract that keeps every reader and
writer from inventing different string, label, dbref, header, EOD, or stream
behavior.
