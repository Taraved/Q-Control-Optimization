# -*- coding: utf-8 -*-
"""
Step 2. Quantum circuits and the theoretical result.

What it does:
  1. Builds 4 circuits:
     calib         - X on qubit 0 and measurement. Shows where qubit 0 is placed in the backend's result key.
     penalty_qaoa  - QAOA with penalties (the model of the original version), but with tuned angles.
     xy_qaoa       - QAOA with the constraint "exactly 2 lines" built into the circuit: start from a Dicke state
                     and an XY mixer that never changes the number of lines switched on.
     legacy_qaoa   - the original circuit with gamma=0.5, beta=0.3 - for comparison.
  2. Tunes the angles (gamma, beta) on an exact simulator: minimum of the mean energy.
  3. Self-tests: QUBO -> Ising mapping, Dicke state fidelity, the XY mixer preserves the number of lines,
     the gate circuit matches the formula.
  4. Computes the theoretical probabilities of all 16 outcomes for every circuit (noiseless).

Input:  results/step1_problem.json
Output: results/step2_circuits.json
Run:    python src/step2_circuits.py      (in Jupyter: %run src/step2_circuits.py)
"""
import importlib
import os
import sys
import time

import numpy as np

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

TITLES = {
    "calib": "calibration: X on qubit 0",
    "penalty_qaoa": "QAOA with penalties, tuned angles",
    "xy_qaoa": "QAOA with the constraint in the circuit (Dicke + XY)",
    "legacy_qaoa": "original circuit (gamma=0.5, beta=0.3)",
}


def self_tests(P):
    n, cfg = P.n, P.cfg
    h, J = C.qubo_to_ising(P.Q)
    zs = [1 - 2 * np.array(x) for x in P.states]
    ising = np.array([h @ z + sum(J[i, j] * z[i] * z[j] for i in range(n) for j in range(i + 1, n)) for z in zs])
    assert np.ptp(P.E - ising) < 1e-9, "QUBO -> Ising: energies do not match"
    print("   [ok] QUBO -> Ising: energies match up to a constant")
    if C.xy_supported(cfg):
        D = np.array([1.0 if sum(x) == 2 else 0.0 for x in P.states])
        D /= np.linalg.norm(D)
        fid = abs(np.vdot(D, C.simulate_state(C.prep_dicke_4_2(), n))) ** 2
        assert fid > 1 - 1e-12, f"Dicke state: fidelity {fid}"
        print(f"   [ok] Dicke state D(4,2) is prepared exactly (fidelity = {fid:.12f})")
        w = np.array([sum(x) for x in P.states])
        leak = np.abs(C.unitary_of(C.mixer_xy_ring(0.7), n))[w[:, None] != w[None, :]].max()
        assert leak < 1e-12, "the XY mixer changes the number of lines"
        print("   [ok] the XY mixer preserves the number of lines switched on")


def build(P):
    """Circuits, angles and theoretical probabilities."""
    n, cfg, ex = P.n, P.cfg, P.cfg["experiment"]
    h, J = C.qubo_to_ising(P.Q)
    out = {"calib": {"gates": [("X", 0)], "gamma": None, "beta": None, "scale": None}}

    # QAOA with penalties: start |+>^4, cost = full H with penalties (normalised), X mixer
    scale = float(np.max(np.abs(P.E)))
    psi0 = C.simulate_state(C.prep_plus(n), n)
    g, b = C.optimize_p1(psi0, P.E, scale, lambda bt: C.mixer_x(n, bt), n, 2 * C.PI, C.PI / 2)
    out["penalty_qaoa"] = {"gates": C.prep_plus(n) + C.cost_layer(h, J, g, scale) + C.mixer_x(n, b),
                           "gamma": g, "beta": b, "scale": scale, "psi0": psi0, "E_cost": P.E,
                           "mixer": lambda bt: C.mixer_x(n, bt)}

    # QAOA with the constraint in the circuit: start D(4,2), cost = losses + small short-circuit penalty, XY mixer
    if C.xy_supported(cfg):
        Qc = np.diag(np.array(cfg["objective_costs"], dtype=float))
        for ic in cfg.get("inequality_constraints", []):
            i, j = ic["indices"]
            Qc[i, j] += ex["xy_conflict_penalty"] / 2
            Qc[j, i] += ex["xy_conflict_penalty"] / 2
        Ec = C.energies(Qc, 0.0, P.states)
        hc, Jc = C.qubo_to_ising(Qc)
        sc = float(np.max(np.abs(Ec)))
        psi0 = C.simulate_state(C.prep_dicke_4_2(), n)
        g, b = C.optimize_p1(psi0, Ec, sc, C.mixer_xy_ring, n, 4 * C.PI, C.PI, ng=801, nb=241)
        out["xy_qaoa"] = {"gates": C.prep_dicke_4_2() + C.cost_layer(hc, Jc, g, sc) + C.mixer_xy_ring(b),
                          "gamma": g, "beta": b, "scale": sc, "psi0": psi0, "E_cost": Ec,
                          "mixer": C.mixer_xy_ring}
    else:
        print("   xy_qaoa skipped: it is written for 4 lines with the constraint 'exactly 2'")

    # the original circuit without angle tuning
    la = ex["legacy_angles"]
    out["legacy_qaoa"] = {"gates": C.prep_plus(n) + C.cost_layer(h, J, la["gamma"], 1.0) + C.mixer_x(n, la["beta"]),
                          "gamma": la["gamma"], "beta": la["beta"], "scale": 1.0}

    for name, v in out.items():
        v["exact"] = C.simulate_probs(v["gates"], n)
        if "psi0" in v:   # gate circuit == the formula used to tune the angles
            phase = np.exp(-1j * v["gamma"] * v["E_cost"] / v["scale"]) * v["psi0"]
            formula = np.abs(C.unitary_of(v["mixer"](v["beta"]), n) @ phase) ** 2
            assert np.max(np.abs(formula - v["exact"])) < 1e-9, f"{name}: gates do not match the formula"
    print("   [ok] the gate circuits match the formulas used to tune the angles")
    return out


def main():
    t0 = time.time()
    s1 = C.load_json(C.STEP1_PATH, "step 1 (src/step1_problem.py)")
    P = C.Problem(s1["config"])
    n = P.n
    print("=" * 72)
    print("STEP 2. Quantum circuits, angle tuning and the theoretical result")
    print("=" * 72)
    print("Self-tests:")
    self_tests(P)
    print("Tuning the angles on the exact simulator (a few seconds)...")
    circuits = build(P)

    print("\nCircuits:")
    for name, v in circuits.items():
        one_q, two_q = C.gate_counts(v["gates"])
        angles = "" if v["gamma"] is None else f"gamma={v['gamma']:+.4f}, beta={v['beta']:+.4f}; "
        print(f"   {name:<13} {TITLES[name]:<52} {angles}gates: {one_q} single-qubit + {two_q} CNOT")

    uni = np.full(2 ** n, 1 / 2 ** n)
    print("\nTheory (noiseless). Random guess: P(opt)=6.2%, P(feas)=31.2%, P(opt|feas)=20.0%")
    print(f"   {'circuit':<13}{'P(opt)':>8}{'P(feas)':>9}{'P(opt|feas)':>13}{'<H>':>9}   most frequent outcome")
    for name, v in circuits.items():
        if name == "calib":
            continue
        m = C.metrics(P, v["exact"])
        print(f"   {name:<13}{m['p_opt']:8.1%}{m['p_feasible']:9.1%}{m['p_opt_given_feasible']:13.1%}"
              f"{m['exp_H']:9.2f}   {m['mode']}")
    mu = C.metrics(P, uni)
    print(f"   {'(random)':<13}{mu['p_opt']:8.1%}{mu['p_feasible']:9.1%}{mu['p_opt_given_feasible']:13.1%}"
          f"{mu['exp_H']:9.2f}")

    C.save_json(C.STEP2_PATH, {
        "config": s1["config"],
        "circuits": {name: {"title": TITLES[name], "gates": v["gates"], "gamma": v["gamma"], "beta": v["beta"],
                            "energy_scale": v["scale"],
                            "exact": {C.xstr(k, n): float(v["exact"][k]) for k in range(2 ** n)}}
                     for name, v in circuits.items()},
    })
    print(f"\nSaved: {C.rel(C.STEP2_PATH)}   ({time.time() - t0:.1f} s)")


if __name__ == "__main__":
    main()
