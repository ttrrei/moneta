"""VARIANTS block for S-73..S-87 (8 each). Run: venv/bin/python scripts/_gen_var_batch6.py
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


TBL = {
    "s73": [
        ("base", {}),
        ("stronger", {"k_in": 80.0, "k_exit": 50.0}),
        ("looser", {"k_in": 60.0, "k_exit": 30.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 70.0, "k_exit": 20.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 80.0, "k_exit": 50.0, "ema_gate": True})],
    "s74": [  # willr_60: closer to 0 = higher (less oversold); k_exit far = wider
        ("base", {}),
        ("stronger", {"k_in": -30.0, "k_exit": -60.0}),
        ("looser", {"k_in": -60.0, "k_exit": -90.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": -50.0, "k_exit": -95.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": -30.0, "k_exit": -60.0, "ema_gate": True})],
    "s75": [
        ("base", {}),
        ("stronger", {"k_in": 150.0, "k_exit": 75.0}),
        ("looser", {"k_in": 75.0, "k_exit": 25.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 100.0, "k_exit": 0.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 150.0, "k_exit": 75.0, "ema_gate": True})],
    "s76": [
        ("base", {}),
        ("stronger", {"k_in": 85.0, "k_exit": 60.0}),
        ("looser", {"k_in": 75.0, "k_exit": 45.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 80.0, "k_exit": 35.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 85.0, "k_exit": 60.0, "ema_gate": True})],
    "s77": [
        ("base", {}),
        ("stronger", {"k_in": 85.0, "k_exit": 60.0}),
        ("looser", {"k_in": 75.0, "k_exit": 50.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 80.0, "k_exit": 45.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 85.0, "k_exit": 60.0, "ema_gate": True})],
    "s78": [  # atr_pct_120: higher = vol expansion (stronger); k_exit tighter
        ("base", {}),
        ("stronger", {"k_in": 0.008, "k_exit": 0.004}),
        ("looser", {"k_in": 0.004, "k_exit": 0.002}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.006, "k_exit": 0.0015}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.008, "k_exit": 0.004, "ema_gate": True})],
    "s79": [
        ("base", {}),
        ("stronger", {"k_in": 0.04, "k_exit": 0.01}),
        ("looser", {"k_in": 0.01, "k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.02, "k_exit": -0.01}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.04, "k_exit": 0.01, "ema_gate": True})],
    "s80": [
        ("base", {}),
        ("stronger", {"k_in": 0.7, "k_exit": -0.3}),
        ("looser", {"k_in": 0.3, "k_exit": -0.7}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.5, "k_exit": -0.9}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.7, "k_exit": -0.3, "ema_gate": True})],
    "s81": [
        ("base", {}),
        ("stronger", {"k_in": 0.7, "k_exit": -0.3}),
        ("looser", {"k_in": 0.3, "k_exit": -0.7}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.5, "k_exit": -0.9}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.7, "k_exit": -0.3, "ema_gate": True})],
    "s82": [  # tr collapse: lower = stronger; k_exit wider
        ("base", {}),
        ("stronger", {"k_in": 0.0005, "k_exit": 0.001}),
        ("looser", {"k_in": 0.002, "k_exit": 0.004}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.001, "k_exit": 0.003}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.0005, "k_exit": 0.001, "ema_gate": True})],
    "s83": [  # psar_dir flag rule
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True, "entry_guard": True}),
        ("1h_ema", {"timeframe": "1h", "ema_gate": True}),
        ("1h_guard", {"timeframe": "1h", "entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h", "ema_gate": True, "entry_guard": True})],
    "s84": [  # dual-st flag rule
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True, "entry_guard": True}),
        ("1h_ema", {"timeframe": "1h", "ema_gate": True}),
        ("1h_guard", {"timeframe": "1h", "entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h", "ema_gate": True, "entry_guard": True})],
    "s85": [  # h1-st flag rule (5m-only h1_* columns -> no 1h variant)
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("ema_guard", {"ema_gate": True, "entry_guard": True}),
        ("entry_ema", {"entry_guard": True, "ema_gate": True}),
        ("combo", {"ema_gate": True, "entry_guard": True}),
        ("ema_only", {"ema_gate": True}),
        ("guard_only", {"entry_guard": True})],
    "s86": [
        ("base", {}),
        ("stronger", {"k_in": 0.7, "k_exit": -0.3}),
        ("looser", {"k_in": 0.3, "k_exit": -0.7}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.5, "k_exit": -0.9}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.7, "k_exit": -0.3, "ema_gate": True})],
    "s87": [
        ("base", {}),
        ("stronger", {"k_in": 0.04, "k_exit": 0.01}),
        ("looser", {"k_in": 0.01, "k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.02, "k_exit": -0.01}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.04, "k_exit": 0.01, "ema_gate": True})],
}


def main() -> None:
    lines = []
    for sid in sorted(TBL):
        rows = TBL[sid]
        assert len(rows) == 8, f"{sid} has {len(rows)} variants"
        seen = set()
        for name, _ in rows:
            assert name not in seen, f"{sid} duplicate variant {name}"
            seen.add(name)
        lines.append(f'    "{sid}": [')
        for name, kwargs in rows:
            body = ",".join(f'"{k}": {fmt(v)}' for k, v in kwargs.items())
            lines.append(f'        ("{name}", {{{body}}}),' if body else f'        ("{name}", {{}}),')
        lines.append("    ],")
    text = "\n".join(lines)
    (ROOT / "scripts" / "_variants_batch6.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
