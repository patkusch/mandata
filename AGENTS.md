# Working in mandata

Checks that what your coding-agent instruction files say is still true: commands, file paths, imports and versions. Runs offline.

## Run the tests

You need Python 3.9 or newer.

```bash
python -m unittest discover -s tests
```

Every test should pass before you start and after you finish.

## Where things are

- `tests/`: the tests
- `examples/`: worked examples

## Before you commit

- Make sure the tests pass.
- Put changes people will notice in `CHANGELOG.md`.
- Do not put real passwords, keys or private data in test files or examples. Use made-up ones.
