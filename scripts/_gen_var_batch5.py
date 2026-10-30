"""Generate the VARIANTS block for S-58..S-72 (8 each) for strategy_variants.py.

Strategy ids in the harness are the registry id lower-cased with the ``-``
dropped (``S-58`` -> ``s58``). Run:  venv/bin/python scripts/_gen_var_batch5.py
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def fmt(v) -> str:
    if isinstance(v, bool):
        return "True"
    if isinstance(v, str):
        return f'"{v}"'
    return repr(v) if isinstance(v, float) else str(v)


# Per-strategy 8 variants (name, kwargs). Strategies using only h1_* columns
# cannot take a ``timeframe: "1h"`` variant (the 1h feature parquet has no
# h1_* context block), so those use the entry_guard / entry_ema flag combos
# in slots 6 and 7 instead.
TBL = {
    "s58": [  # roc, standard (k_in up = stronger)
        ("base", {}),
        ("stronger", {"k_in": 0.008, "k_exit": 0.001}),
        ("looser", {"k_in": 0.002, "k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.004, "k_exit": -0.001}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.008, "k_exit": 0.001, "ema_gate": True})],
    "s59": [  # stoch kd-turn; k_exit (exit) lower = tighter
        ("base", {}),
        ("stronger", {"k_in": 20.0, "k_exit": 50.0}),
        ("looser", {"k_in": 40.0, "k_exit": 80.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 30.0, "k_exit": 90.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 20.0, "k_exit": 50.0, "ema_gate": True})],
    "s60": [  # aroon-down collapse; lower k_in = stricter, higher k_exit = wider
        ("base", {}),
        ("stronger", {"k_in": 20.0, "k_exit": 80.0}),
        ("looser", {"k_in": 40.0, "k_exit": 60.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 30.0, "k_exit": 90.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 20.0, "k_exit": 80.0, "ema_gate": True})],
    "s61": [  # mom sign-turn
        ("base", {}),
        ("stronger", {"k_in": 1.0, "k_exit": -0.25}),
        ("looser", {"k_in": 0.25, "k_exit": -0.75}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.5, "k_exit": -1.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 1.0, "k_exit": -0.25, "ema_gate": True})],
    "s62": [  # hv-up + trend
        ("base", {}),
        ("stronger", {"k_in": 0.004, "k_exit": 0.002}),
        ("looser", {"k_in": 0.0015, "k_exit": 0.0008}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.0025, "k_exit": 0.0005}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.004, "k_exit": 0.002, "ema_gate": True})],
    "s63": [  # bbupper flag rule
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True, "entry_guard": True}),
        ("1h_ema", {"timeframe": "1h", "ema_gate": True}),
        ("1h_guard", {"timeframe": "1h", "entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h", "ema_gate": True, "entry_guard": True})],
    "s64": [  # dcupper flag rule
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True, "entry_guard": True}),
        ("1h_ema", {"timeframe": "1h", "ema_gate": True}),
        ("1h_guard", {"timeframe": "1h", "entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h", "ema_gate": True, "entry_guard": True})],
    "s65": [  # lower-wick rejection (higher k_in = stricter entry)
        ("base", {}),
        ("stronger", {"k_in": 0.35, "k_exit": 0.1}),
        ("looser", {"k_in": 0.7, "k_exit": 0.25}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.5, "k_exit": 0.05}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.35, "k_exit": 0.1, "ema_gate": True})],
    "s66": [  # volbb; vmin is the only knob
        ("base", {}),
        ("stronger", {"vmin": 1.5}),
        ("looser", {"vmin": 0.8}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"vmin": 1.2}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"vmin": 1.5, "ema_gate": True})],
    "s67": [  # h1 adx + h1 st; 5m-only columns -> no 1h variant
        ("base", {}),
        ("stronger", {"k_in": 30.0, "k_exit": 25.0}),
        ("looser", {"k_in": 20.0, "k_exit": 15.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 25.0, "k_exit": 18.0}),
        ("entry_guard", {"entry_guard": True}),
        ("entry_ema", {"entry_guard": True, "ema_gate": True}),
        ("combo", {"k_in": 30.0, "k_exit": 25.0, "ema_gate": True})],
    "s68": [  # dual-st flag rule
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True, "entry_guard": True}),
        ("1h_ema", {"timeframe": "1h", "ema_gate": True}),
        ("1h_guard", {"timeframe": "1h", "entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h", "ema_gate": True, "entry_guard": True})],
    "s69": [  # stok mid-turn
        ("base", {}),
        ("stronger", {"k_in": 60.0, "k_exit": 45.0}),
        ("looser", {"k_in": 45.0, "k_exit": 35.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 50.0, "k_exit": 30.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 60.0, "k_exit": 45.0, "ema_gate": True})],
    "s70": [  # h1 low-vol coil; lower = stricter
        ("base", {}),
        ("stronger", {"k_in": 0.005, "k_exit": 0.01}),
        ("looser", {"k_in": 0.012, "k_exit": 0.025}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.008, "k_exit": 0.03}),
        ("entry_guard", {"entry_guard": True}),
        ("entry_ema", {"entry_guard": True, "ema_gate": True}),
        ("combo", {"k_in": 0.005, "k_exit": 0.01, "ema_gate": True})],
    "s71": [  # aroon + stoch confluence
        ("base", {}),
        ("stronger", {"k_in": 20.0, "k_exit": 80.0}),
        ("looser", {"k_in": 40.0, "k_exit": 60.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 30.0, "k_exit": 90.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 20.0, "k_exit": 80.0, "ema_gate": True})],
    "s72": [  # roc + vol confluence
        ("base", {}),
        ("stronger", {"k_in": 0.008, "k_exit": 0.001}),
        ("looser", {"k_in": 0.002, "k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.004, "k_exit": -0.001}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.008, "k_exit": 0.001, "ema_gate": True})],
}


def main() -> None:
    lines = []
    for sid in sorted(TBL):
        rows = TBL[sid]
        assert len(rows) == 8, f"{sid} has {len(rows)} variants"
        seen = set()
        for name, _ in rows:
            assert name not in seen, f"{sid} duplicate variant name {name}"
            seen.add(name)
        lines.append(f'    "{sid}": [')
        for name, kwargs in rows:
            body = ",".join(f'"{k}": {fmt(v)}' for k, v in kwargs.items())
            lines.append(f'        ("{name}", {{{body}}}),' if body else f'        ("{name}", {{}}),')
        lines.append("    ],")
    text = "\n".join(lines)
    (ROOT / "scripts" / "_variants_batch5.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
