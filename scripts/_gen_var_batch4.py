"""Generate the VARIANTS block for S-43..S-57 (8 each) for strategy_variants.py.

Strategy ids in the harness are the registry id lower-cased with the ``-``
dropped (``S-43`` -> ``s43``). Run:  venv/bin/python scripts/_gen_var_batch4.py
"""

from __future__ import annotations

import importlib.util
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("g4", str(ROOT / "scripts" / "_gen_batch4.py"))
g4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g4)
byid = {s["sid"].lower(): s for s in g4.S}


def rnd(x: float) -> float:
    if x == 0:
        return 0.0
    return round(x, max(0, 4 - int(math.floor(math.log10(abs(x)))) + 1)) if abs(x) < 0.1 else round(x, 2)


def fmt(v) -> str:
    if isinstance(v, bool):
        return "True"
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, float):
        return repr(v)
    return str(v)


def variants(sid: str) -> list[tuple[str, dict]]:
    s = byid[sid]
    has1h = not any("h1_" in c for _, c in s["arrays"])
    if s["params"]:
        kin, kexit = s["params"][0][1], s["params"][1][1]
        if kexit > kin:  # "lower is better" (atrpct, upwick)
            stronger = {"k_in": rnd(kin * 0.6), "k_exit": rnd(kexit * 0.7)}
            looser = {"k_in": rnd(kin * 1.5), "k_exit": rnd(kexit * 1.5)}
            wide_exit = {"k_in": kin, "k_exit": rnd(kexit * 1.8)}
            combo = {"k_in": rnd(kin * 0.6), "k_exit": rnd(kexit * 0.7), "ema_gate": True}
        else:
            sk = rnd(kin * 1.5) if kin else kin + 0.5
            lk = rnd(kin * 0.6) if kin else kin - 0.2
            ek = rnd(kexit * 1.5) if kexit else kexit + 0.5
            wk = rnd(kexit * 0.6) if kexit else kexit - 0.2
            stronger = {"k_in": sk, "k_exit": ek}
            looser = {"k_in": lk, "k_exit": wk}
            wide_exit = {"k_in": kin, "k_exit": wk}
            combo = {"k_in": sk, "k_exit": ek, "ema_gate": True}
        v = [("base", {}), ("stronger", stronger), ("looser", looser),
             ("ema_gate", {"ema_gate": True}), ("wide_exit", wide_exit)]
        if has1h:
            v += [("1h", {"timeframe": "1h"}), ("entry_guard", {"entry_guard": True})]
        else:  # 1h-context strategy: no 1h timeframe variant available
            v += [("entry_guard", {"entry_guard": True}),
                  ("entry_ema", {"entry_guard": True, "ema_gate": True})]
        v.append(("combo", combo))
        return v[:8]
    if has1h:
        return [("base", {}), ("ema_gate", {"ema_gate": True}),
                ("entry_guard", {"entry_guard": True}), ("1h", {"timeframe": "1h"}),
                ("ema_guard", {"ema_gate": True, "entry_guard": True}),
                ("1h_ema", {"timeframe": "1h", "ema_gate": True}),
                ("1h_guard", {"timeframe": "1h", "entry_guard": True}),
                ("1h_ema_guard", {"timeframe": "1h", "ema_gate": True, "entry_guard": True})]
    return [("base", {}), ("ema_gate", {"ema_gate": True}),
            ("entry_guard", {"entry_guard": True}),
            ("ema_guard", {"ema_gate": True, "entry_guard": True}),
            ("entry_ema", {"entry_guard": True, "ema_gate": True}),
            ("combo", {"ema_gate": True, "entry_guard": True}),
            ("ema_only", {"ema_gate": True}), ("guard_only", {"entry_guard": True})]


def main() -> None:
    lines = []
    for sid in sorted(byid):
        key = sid.replace("-", "")  # harness key: "S-43" -> "s43"
        _seen: dict[str, dict] = {}
        for n, k in variants(sid):
            if n not in _seen:
                _seen[n] = k
        vs = list(_seen.items())  # de-dup by name, keep order
        if len(vs) < 8:
            raise SystemExit(f"ERROR: {sid} has only {len(vs)} variants")
        lines.append(f'    "{key}": [')
        for n, k in vs:
            body = ",".join(f'"{key}": {fmt(val)}' for key, val in k.items())
            lines.append(f'        ("{n}", {{{body}}}),' if body else f'        ("{n}", {{}}),')
        lines.append("    ],")
    text = "\n".join(lines)
    (ROOT / "scripts" / "_variants_batch4.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
