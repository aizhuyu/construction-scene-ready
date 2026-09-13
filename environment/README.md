# Reproducible environments

The project intentionally separates the CPU research environment from the
NVIDIA/Isaac runtime.

- `mac-cpu-lock.txt` records the verified Mac environment used for IFC
  generation, scene compilation, deterministic validation, fault injection,
  repair, statistics, tests, and manuscript preparation.
- `ubuntu-rtx-lock.txt` records the school workstation used for the verified
  headless Isaac Sim smoke tests. It is kept separate because NVIDIA runtime
  packages must not leak into the Mac dependency graph.

Create the local environment with:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r environment/mac-cpu-lock.txt
python -m pip install -e .
pytest -q
```

`usd-core` is used for standards-level OpenUSD authoring and inspection on the
Mac. NVIDIA Omniverse and Isaac packages are deliberately excluded.
