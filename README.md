# WSJT-X Free Frequency

Listens to WSJT-X decodes and recommends audio offsets that nobody else is transmitting on, separately for each slot.

This is an early skeleton: the application currently opens an empty window.

## Install

Requires Python 3.10 or newer and PyQt6 (installed automatically).

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For development (tests, linters, type checking):

```sh
pip install -e ".[dev]"
```

## Run

```sh
wsjtx-free-freq
```

This opens a window titled "WSJT-X Free Frequency".

## Platform support

Linux and Windows are the primary targets.

macOS support is best effort. The author has not tested this application on real Mac hardware, so it may not behave correctly there.

## Licence

MIT. See [LICENSE](LICENSE).
