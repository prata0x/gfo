# New subcommand checklist

Applies to `src/gfo/cli.py`, `src/gfo/commands/**`, `tests/test_cli.py`.

In `src/gfo/cli.py`, registration and dispatch are far apart, and `tests/test_cli.py` also
has hard-coded expected values. When adding a new subcommand (or a new subaction to an
existing command), change at least the following 4 places in the same PR.

1. **`create_parser()` (from the top of `cli.py`)**: register with argparse via `add_parser` / `add_argument`
2. **`_DISPATCH` (`_DISPATCH: dict[...] = {...}` near the end of `cli.py`)**: register the handler keyed by a `(command, subcommand)` tuple
3. **`commands/*.py`**: implement the handler itself
4. **`tests/test_cli.py`**:
   - Update the count literal in `assert len(_DISPATCH) == N`
   - Add the new key to `expected_keys` in `test_dispatch_table_all_keys()`

(1) and (2) correspond to each other but are defined far apart, so updating only one of
them causes an inconsistency: either `argparse` accepts the command but it is missing from
`_DISPATCH` and errors, or conversely an unreachable handler remains. Missing (4) makes CI
fail on a count mismatch or missing keys.

If a command's argument structure or output format changes, also update `docs/commands.md` (English) /
`docs/commands.ja.md` (Japanese) in the same PR (see the root `AGENTS.md`).
