# -*- coding: utf-8 -*-
"""
Step 3. Run on the CPUQVM simulator (pyqpanda3), no internet and no API key needed.

What it does: converts the step-2 circuits into pyqpanda3 programs, runs each of them SHOTS times on CPUQVM,
determines the bit order of the result key from the calibration circuit and compares the frequencies with theory.
There is no noise here, so the only deviation from theory is sampling statistics (TVD about 0.02-0.05).

Input:  results/step2_circuits.json
Output: results/step3_local.json
Run:    python src/step3_local_run.py      (in Jupyter: %run src/step3_local_run.py)
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
    s2, P, gates, exact = C.load_circuits()
    n, shots = P.n, C.run_settings(s2)["shots"]
    print("=" * 72)
    print(f"STEP 3. Run on the CPUQVM simulator (pyqpanda3 {C.pyqpanda3_version()}), {shots} shots per circuit")
    print("=" * 72)
    try:
        from pyqpanda3.core import CPUQVM
    except ImportError as e:
        raise SystemExit(f"pyqpanda3 cannot be imported ({e}). Installation: see README, 'Local check'.")

    raws = {}
    for name, g in gates.items():
        qvm = CPUQVM()
        qvm.run(C.to_qprog(g, n), shots)
        raws[name] = {str(k): int(v) for k, v in qvm.result().get_counts().items()}
    res = C.analyse_raw(P, exact, raws)
    side = "RIGHTMOST" if res["order"] == "q0_right" else "LEFTMOST"
    print(f"Calibration X(q0): key {res['calib_top']!r} in {res['calib_share']:.0%} of shots "
          f"-> qubit 0 is the {side} character of the key")

    print(f"\n   {'circuit':<13}{'P(opt)':>8}{'theory':>8}{'P(feas)':>9}{'P(opt|feas)':>13}{'TVD':>7}   most frequent")
    for name, m in res["metrics"].items():
        th = C.metrics(P, exact[name])
        print(f"   {name:<13}{m['p_opt']:8.1%}{th['p_opt']:8.1%}{m['p_feasible']:9.1%}"
              f"{m['p_opt_given_feasible']:13.1%}{m['tvd']:7.3f}   {m['mode']}")

    C.save_json(C.STEP3_PATH, {"backend": "CPUQVM", "pyqpanda3": C.pyqpanda3_version(), "shots": shots,
                               "raw": raws})
    print(f"\nSaved: {C.rel(C.STEP3_PATH)}   ({time.time() - t0:.1f} s)")


if __name__ == "__main__":
    main()
