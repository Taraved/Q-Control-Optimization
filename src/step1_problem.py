# -*- coding: utf-8 -*-
"""
Step 1. Problem statement.

What it does: reads data/config.json, builds the QUBO (losses + penalties), computes the energy of all 16 ways
to switch the lines and finds the classical optimum by brute force. This is the reference the quantum part
is compared with.

Input:  data/config.json
Output: results/step1_problem.json
Run:    python src/step1_problem.py      (in Jupyter: %run src/step1_problem.py)
"""
import importlib
import os
import sys
import time

# Shared functions: if the code of common.py was pasted into a notebook cell above, take them from there,
# otherwise import the file src/common.py (run via python or %run).
if "load_circuits" in globals() and "Problem" in globals():
    import types
    C = types.SimpleNamespace(**globals())
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(
        globals().get("__file__", os.path.join(os.getcwd(), "src", "_")))))
    try:
        import common as C  # noqa: E402
    except ImportError:
        raise SystemExit("Shared functions are missing: run the cell with the code of src/common.py first "
                         "(or put the file src/common.py next to this one).")
    C = importlib.reload(C)   # Jupyter caches modules: reload in case common.py was updated


def main():
    t0 = time.time()
    cfg = C.load_config()
    P = C.Problem(cfg)
    n = P.n
    print("=" * 72)
    print("STEP 1. Problem statement: QUBO and the classical optimum")
    print("=" * 72)
    print(f"Lines: {n}; loss when line i is switched on: {cfg['objective_costs']}")
    for ec in cfg["equality_constraints"]:
        print(f"Equality constraint: exactly {ec['target_sum']} of lines {ec['indices']} on "
              f"(penalty {ec['penalty']} x (sum - {ec['target_sum']})^2)")
    for ic in cfg["inequality_constraints"]:
        print(f"Forbidden: lines {ic['indices'][0]} and {ic['indices'][1]} together - short circuit "
              f"(penalty {ic['penalty']})")
    print(f"\nH(x) = x^T Q x + {P.offset:g},  Q =")
    for row in P.Q:
        print("   " + "  ".join(f"{v:8.1f}" for v in row))

    print("\nAll 16 states sorted by energy (x = x0 x1 x2 x3, 1 = line on):")
    print(f"   {'x':<6}{'H(x)':>9}   assessment")
    for k in sorted(range(2 ** n), key=lambda k: P.E[k]):
        x = P.states[k]
        v = C.violations(x, cfg)
        mark = "OPTIMUM" if P.optimal[k] else ("feasible" if not v else "; ".join(v))
        print(f"   {C.xstr(k, n):<6}{P.E[k]:9.3f}   {mark}")

    opt = P.opt_strings()
    on = [i for i, b in enumerate(opt[0]) if b == "1"]
    print(f"\nClassical optimum (brute force over {2 ** n} states): {opt}, H = {P.E_opt:.3f} "
          f"- switch on lines {on}")
    print(f"Feasible states: {int(P.feasible.sum())} of {2 ** n}")

    C.save_json(C.STEP1_PATH, {
        "config": cfg,
        "Q": P.Q, "offset": P.offset,
        "energies": {C.xstr(k, n): float(P.E[k]) for k in range(2 ** n)},
        "feasible": [C.xstr(k, n) for k in range(2 ** n) if P.feasible[k]],
        "optimum": opt, "E_opt": P.E_opt,
    })
    print(f"\nSaved: {C.rel(C.STEP1_PATH)}   ({time.time() - t0:.1f} s)")


if __name__ == "__main__":
    main()
