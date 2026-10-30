"""VARIANTS block for S-88..S-102 (8 each). Run: venv/bin/python scripts/_gen_var_batch7.py
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
    "s88": [
        ("base", {}),
        ("stronger", {"k_in": 65.0, "k_exit": 50.0}),
        ("looser", {"k_in": 45.0, "k_exit": 30.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 55.0, "k_exit": 25.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 65.0, "k_exit": 50.0, "ema_gate": True})],
    "s89": [
        ("base", {}),
        ("stronger", {"k_in": 50.0, "k_exit": 20.0}),
        ("looser", {"k_in": 15.0, "k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 30.0, "k_exit": 0.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 50.0, "k_exit": 20.0, "ema_gate": True})],
    "s90": [  # macd_hist_6_24 flag rule
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True, "entry_guard": True}),
        ("1h_ema", {"timeframe": "1h", "ema_gate": True}),
        ("1h_guard", {"timeframe": "1h", "entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h", "ema_gate": True, "entry_guard": True})],
    "s91": [
        ("base", {}),
        ("stronger", {"k_in": 65.0, "k_exit": 50.0}),
        ("looser", {"k_in": 45.0, "k_exit": 30.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 55.0, "k_exit": 25.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 65.0, "k_exit": 50.0, "ema_gate": True})],
    "s92": [
        ("base", {}),
        ("stronger", {"k_in": 70.0, "k_exit": 55.0}),
        ("looser", {"k_in": 50.0, "k_exit": 35.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 60.0, "k_exit": 30.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 70.0, "k_exit": 55.0, "ema_gate": True})],
    "s93": [  # willr_12: closer to 0 = higher (less oversold)
        ("base", {}),
        ("stronger", {"k_in": -40.0, "k_exit": -60.0}),
        ("looser", {"k_in": -70.0, "k_exit": -90.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": -50.0, "k_exit": -95.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": -40.0, "k_exit": -60.0, "ema_gate": True})],
    "s94": [
        ("base", {}),
        ("stronger", {"k_in": 0.5, "k_exit": 0.3}),
        ("looser", {"k_in": 0.3, "k_exit": 0.15}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.4, "k_exit": 0.1}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.5, "k_exit": 0.3, "ema_gate": True})],
    "s95": [  # hv_120: lower = quieter; k_exit wider
        ("base", {}),
        ("stronger", {"k_in": 0.0005, "k_exit": 0.001}),
        ("looser", {"k_in": 0.002, "k_exit": 0.005}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.001, "k_exit": 0.004}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.0005, "k_exit": 0.001, "ema_gate": True})],
    "s96": [  # bb_width_60: squeeze-then-release; k_in high = wider release
        ("base", {}),
        ("stronger", {"k_in": 0.006, "k_exit": 0.002}),
        ("looser", {"k_in": 0.003, "k_exit": 0.001}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.005, "k_exit": 0.001}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.006, "k_exit": 0.002, "ema_gate": True})],
    "s97": [  # triosc: 3 oscillators
        ("base", {}),
        ("stronger", {"r_in": 65.0, "k_in": 65.0, "m_in": 65.0}),
        ("looser", {"r_in": 45.0, "k_in": 45.0, "m_in": 45.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"r_exit": 40.0, "k_exit": 40.0, "m_exit": 40.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"r_in": 65.0, "k_in": 65.0, "m_in": 65.0, "ema_gate": True})],
    "s98": [  # quadosc: 4 oscillators
        ("base", {}),
        ("stronger", {"r_in": 65.0, "w_in": -40.0, "d_in": 65.0, "m_in": 65.0}),
        ("looser", {"r_in": 45.0, "w_in": -70.0, "d_in": 45.0, "m_in": 45.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"r_exit": 40.0, "w_exit": -90.0, "d_exit": 40.0, "m_exit": 40.0}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"r_in": 65.0, "w_in": -40.0, "d_in": 65.0, "m_in": 65.0, "ema_gate": True})],
    "s99": [
        ("base", {}),
        ("stronger", {"k_in": 0.01, "k_exit": 0.005}),
        ("looser", {"k_in": 0.002, "k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.005, "k_exit": -0.005}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.01, "k_exit": 0.005, "ema_gate": True})],
    "s100": [  # macdcross624 flag rule
        ("base", {}),
        ("ema_gate", {"ema_gate": True}),
        ("entry_guard", {"entry_guard": True}),
        ("1h", {"timeframe": "1h"}),
        ("ema_guard", {"ema_gate": True, "entry_guard": True}),
        ("1h_ema", {"timeframe": "1h", "ema_gate": True}),
        ("1h_guard", {"timeframe": "1h", "entry_guard": True}),
        ("1h_ema_guard", {"timeframe": "1h", "ema_gate": True, "entry_guard": True})],
    "s101": [
        ("base", {}),
        ("stronger", {"k_in": 0.04, "k_exit": 0.01}),
        ("looser", {"k_in": 0.01, "k_exit": 0.0}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.02, "k_exit": -0.01}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.04, "k_exit": 0.01, "ema_gate": True})],
    "s102": [
        ("base", {}),
        ("stronger", {"k_in": 0.8, "k_exit": 0.5}),
        ("looser", {"k_in": 0.6, "k_exit": 0.3}),
        ("ema_gate", {"ema_gate": True}),
        ("wide_exit", {"k_in": 0.7, "k_exit": 0.25}),
        ("1h", {"timeframe": "1h"}),
        ("entry_guard", {"entry_guard": True}),
        ("combo", {"k_in": 0.8, "k_exit": 0.5, "ema_gate": True})],
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
    (ROOT / "scripts" / "_variants_batch7.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
