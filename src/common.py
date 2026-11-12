# -*- coding: utf-8 -*-
"""
common.py - shared functions used by all steps of the project.

Sections:
  1. Paths and JSON files
  2. Problem: QUBO, energies, feasibility (step 1)
  3. Gates and circuits - only H, X, RX, RZ, CNOT (step 2)
  4. Exact numpy simulator and angle tuning (step 2)
  5. Quality metrics (steps 3-5)
  6. Result keys and bit order (steps 3-5)
  7. Converting a circuit into a pyqpanda3 program (steps 3-4)

Index convention: state x = (x0, x1, x2, x3), x_i = 1 means line i is switched on.
In probability arrays the index is k = int("x0x1x2x3", 2), i.e. x0 is the most significant bit.
"""
import json
import math
import os
from itertools import product

import numpy as np

PI = math.pi

# ============================================================================ 1. Paths and JSON files
# As a file (python, %run): the project folder above src/; as code in a notebook cell: the notebook folder.
SRC_DIR = os.path.dirname(os.path.abspath(globals().get("__file__", os.path.join(os.getcwd(), "src", "common.py"))))
ROOT = os.path.dirname(SRC_DIR)
CONFIG_PATH = os.path.join(ROOT, "data", "config.json")
RESULTS_DIR = os.path.join(ROOT, "results")
STEP1_PATH = os.path.join(RESULTS_DIR, "step1_problem.json")
STEP2_PATH = os.path.join(RESULTS_DIR, "step2_circuits.json")
STEP3_PATH = os.path.join(RESULTS_DIR, "step3_local.json")
STEP4_PATH = os.path.join(RESULTS_DIR, "step4_cloud.json")
STEP5_REPORT = os.path.join(RESULTS_DIR, "step5_report.md")
STEP5_PLOT = os.path.join(RESULTS_DIR, "step5_plot.png")


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [to_jsonable(v) for v in obj.tolist()]
    if isinstance(obj, (np.floating, np.integer, np.bool_)):
        return obj.item()
    if isinstance(obj, (bool, int, float, str)) or obj is None:
        return obj
    return str(obj)


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(to_jsonable(obj), f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)          # the file is never left half-written


def load_json(path, hint):
    if not os.path.exists(path):
        raise SystemExit(f"Missing file {os.path.relpath(path, ROOT)} - run {hint} first.")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def pyqpanda3_version():
    try:
        from importlib.metadata import version
        return version("pyqpanda3")
    except Exception:  # noqa: BLE001
        return "not installed"


def rel(path):
    return os.path.relpath(path, ROOT)


# ============================================================================ 2. Problem
def build_qubo(cfg):
    """H(x) = x^T Q x + offset: line losses + penalties for violated constraints (as in the original qubo_builder.py)."""
    n = cfg["n_vars"]
    Q = np.zeros((n, n))
    offset = 0.0
    for i in range(n):
        Q[i, i] += cfg["objective_costs"][i]
    for ec in cfg.get("equality_constraints", []):           # P * (sum x_i - t)^2
        P, idx, t = ec["penalty"], ec["indices"], ec["target_sum"]
        for i in idx:
            Q[i, i] += P * (1 - 2 * t)                       # x_i^2 = x_i
            for j in idx:
                if j > i:
                    Q[i, j] += P
                    Q[j, i] += P
        offset += P * t ** 2
    for ic in cfg.get("inequality_constraints", []):         # P * x_i * x_j
        P = ic["penalty"]
        i, j = ic["indices"]
        Q[i, j] += P / 2
        Q[j, i] += P / 2
    return Q, offset


def violations(x, cfg):
    """List of violated constraints (empty - the state is feasible)."""
    out = []
    for ec in cfg.get("equality_constraints", []):
        s = sum(x[i] for i in ec["indices"])
        if s != ec["target_sum"]:
            out.append(f"lines on: {s} (need {ec['target_sum']})")
    for ic in cfg.get("inequality_constraints", []):
        i, j = ic["indices"]
        if x[i] and x[j]:
            out.append(f"short circuit: lines {i} and {j} together")
    return out


def qubo_to_ising(Q):
    """x_i = (1 - Z_i)/2  ->  H = const + sum h_i Z_i + sum_{i<j} J_ij Z_i Z_j."""
    n = len(Q)
    h = np.zeros(n)
    J = np.zeros((n, n))
    for i in range(n):
        h[i] = -Q[i, i] / 2.0
        for j in range(n):
            if i != j:
                h[i] -= (Q[i, j] + Q[j, i]) / 4.0
    for i in range(n):
        for j in range(i + 1, n):
            J[i, j] = (Q[i, j] + Q[j, i]) / 4.0
    return h, J


def energies(Q, offset, states):
    return np.array([float(np.array(x) @ Q @ np.array(x) + offset) for x in states])


def xstr(k, n):
    return format(k, f"0{n}b")      # string x0 x1 ... x_{n-1}


class Problem:
    """Everything about the problem: 16 states, their energies, feasibility, classical optimum (brute force)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.n = cfg["n_vars"]
        self.Q, self.offset = build_qubo(cfg)
        self.states = list(product((0, 1), repeat=self.n))
        self.E = energies(self.Q, self.offset, self.states)
        self.feasible = np.array([not violations(x, cfg) for x in self.states])
        self.E_opt = float(self.E[self.feasible].min())
        self.optimal = self.feasible & np.isclose(self.E, self.E_opt)

    def opt_strings(self):
        return [xstr(k, self.n) for k in np.where(self.optimal)[0]]


RUN_KEYS = ("shots", "cloud_simulator", "qpu_backend", "qpu_circuits", "qpu_amend", "time_budget_sec")


def run_settings(s2):
    """Run settings (shots, backends, time budget) come from the current config.json and may change after step 2.
    The problem and circuit parameters must match the ones step 2 used to build the circuits."""
    now = load_config()

    def core(cfg):
        c = {k: v for k, v in cfg.items() if k != "experiment"}
        c["circuit_params"] = {k: v for k, v in cfg.get("experiment", {}).items() if k not in RUN_KEYS}
        return c
    if core(now) != core(s2["config"]):
        raise SystemExit("data/config.json: the problem or the circuit parameters changed after step 2 - "
                         "rerun steps 1 and 2.")
    return now["experiment"]


def load_circuits():
    """Step 2 result: (step data, Problem, {circuit: gates}, {circuit: theoretical probabilities})."""
    s2 = load_json(STEP2_PATH, "steps 1-2 (src/step1_problem.py, src/step2_circuits.py)")
    P = Problem(s2["config"])
    gates = {k: v["gates"] for k, v in s2["circuits"].items()}
    exact = {k: np.array([v["exact"][xstr(i, P.n)] for i in range(2 ** P.n)]) for k, v in s2["circuits"].items()}
    return s2, P, gates, exact


# ============================================================================ 3. Gates and circuits
# A circuit is a list of tuples: ("H", q), ("X", q), ("RX", q, angle), ("RZ", q, angle), ("CNOT", control, target).
def g_ry(q, theta):                  # RY(theta) = RZ(pi/2) RX(theta) RZ(-pi/2)
    return [("RZ", q, -PI / 2), ("RX", q, theta), ("RZ", q, PI / 2)]


def g_cry(c, t, theta):              # controlled RY: 2 CNOT
    return g_ry(t, theta / 2) + [("CNOT", c, t)] + g_ry(t, -theta / 2) + [("CNOT", c, t)]


def g_xy(a, b, theta):               # exp(-i theta/2 (XX + YY)): exchange |01> <-> |10>, 2 CNOT
    return [("RX", a, PI / 2), ("RX", b, PI / 2), ("CNOT", a, b), ("RX", a, theta), ("RZ", b, theta),
            ("CNOT", a, b), ("RX", a, -PI / 2), ("RX", b, -PI / 2)]


def g_givens(i, j, theta):           # real rotation |1_i 0_j> -> cos|10> + sin|01>, 2 CNOT
    return [("RZ", i, PI / 2)] + g_xy(i, j, theta) + [("RZ", i, -PI / 2)]


def prep_plus(n):
    """|+>^n - equal superposition of all 16 states."""
    return [("H", q) for q in range(n)]


def prep_dicke_4_2():
    """Dicke state D(4,2) - equal superposition of the 6 states with exactly 2 lines on. 8 CNOT.
    1) the weight of pair A=(0,1) is encoded in unary: 0 -> 00 (1/6), 1 -> 10 (4/6), 2 -> 11 (1/6);
       pair B=(2,3) receives the complement to 2 (CNOT + X);
    2) inside each pair |10> becomes (|10> + |01>)/sqrt(2)."""
    t0 = 2 * math.acos(1 / math.sqrt(6))
    t1 = 2 * math.acos(2 / math.sqrt(5))
    return (g_ry(0, t0) + g_cry(0, 1, t1)
            + [("CNOT", 1, 2), ("X", 2), ("CNOT", 0, 3), ("X", 3)]
            + g_givens(0, 1, PI / 4) + g_givens(2, 3, PI / 4))


def cost_layer(h, J, gamma, scale):
    """exp(-i gamma H / scale): RZ on every qubit and CNOT-RZ-CNOT on every coupled pair."""
    n = len(h)
    gates = []
    for q in range(n):
        if abs(h[q]) > 1e-12:
            gates.append(("RZ", q, 2.0 * gamma * h[q] / scale))
    for i in range(n):
        for j in range(i + 1, n):
            if abs(J[i, j]) > 1e-12:
                gates += [("CNOT", i, j), ("RZ", j, 2.0 * gamma * J[i, j] / scale), ("CNOT", i, j)]
    return gates


def mixer_x(n, beta):
    """Standard mixer exp(-i beta sum X): may change the number of lines switched on."""
    return [("RX", q, 2.0 * beta) for q in range(n)]


def mixer_xy_ring(beta):
    """XY mixer on the ring 0-1-2-3-0: only moves the "on" state between neighbouring lines,
    the number of lines switched on never changes."""
    return g_xy(0, 1, beta) + g_xy(2, 3, beta) + g_xy(1, 2, beta) + g_xy(3, 0, beta)


def gate_counts(gates):
    two = sum(1 for g in gates if g[0] == "CNOT")
    return len(gates) - two, two


def xy_supported(cfg):
    """The XY circuit is written for 4 lines with the constraint "exactly 2 on"."""
    ecs = cfg.get("equality_constraints", [])
    return (cfg["n_vars"] == 4 and len(ecs) == 1 and sorted(ecs[0]["indices"]) == [0, 1, 2, 3]
            and ecs[0]["target_sum"] == 2)


# ============================================================================ 4. Exact simulator and angle tuning
_H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
_X = np.array([[0, 1], [1, 0]], dtype=complex)


def _rx(theta):                      # as in pyqpanda3: RX(theta) = exp(-i theta X / 2)
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array([[c, -1j * s], [-1j * s, c]])


def _rz(theta):                      # as in pyqpanda3: RZ(theta) = diag(e^{-i theta/2}, e^{i theta/2})
    return np.diag([np.exp(-0.5j * theta), np.exp(0.5j * theta)])


def simulate_state(gates, n, psi=None):
    """State vector after the circuit (exact: no noise, no sampling)."""
    if psi is None:
        psi = np.zeros(2 ** n, dtype=complex)
        psi[0] = 1.0
    psi = np.asarray(psi, dtype=complex).reshape((2,) * n).copy()
    for g in gates:
        if g[0] == "CNOT":
            c, t = g[1], g[2]
            idx = [slice(None)] * n
            idx[c] = 1
            idx = tuple(idx)
            psi[idx] = np.flip(psi[idx].copy(), axis=t if t < c else t - 1)
            continue
        U = {"H": _H, "X": _X}.get(g[0])
        if U is None:
            U = _rx(g[2]) if g[0] == "RX" else _rz(g[2])
        psi = np.moveaxis(np.tensordot(U, psi, axes=([1], [g[1]])), 0, g[1])
    return psi.reshape(-1)


def simulate_probs(gates, n):
    return np.abs(simulate_state(gates, n)) ** 2


def unitary_of(gates, n):
    eye = np.eye(2 ** n, dtype=complex)
    return np.array([simulate_state(gates, n, eye[k]) for k in range(2 ** n)]).T


def optimize_p1(psi0, E_cost, scale, mixer_fn, n, g_max, b_max, ng=801, nb=181):
    """Tune (gamma, beta) for p=1: minimum of the mean energy <E_cost>.
    State: |psi> = M(beta) exp(-i gamma E_cost/scale) |psi0>. Grid search, then refinement around the best point."""
    Es = E_cost / scale

    def search(gammas, betas):
        phase = np.exp(-1j * np.outer(Es, gammas)) * psi0[:, None]
        best = (math.inf, 0.0, 0.0)
        for beta in betas:
            expv = E_cost @ (np.abs(unitary_of(mixer_fn(beta), n) @ phase) ** 2)
            k = int(np.argmin(expv))
            if expv[k] < best[0]:
                best = (float(expv[k]), float(gammas[k]), float(beta))
        return best

    gg = np.linspace(-g_max, g_max, ng)
    bb = np.linspace(-b_max, b_max, nb)
    _, g0, b0 = search(gg, bb)
    dg, db = gg[1] - gg[0], bb[1] - bb[0]
    _, g1, b1 = search(np.linspace(g0 - 2 * dg, g0 + 2 * dg, 101), np.linspace(b0 - 2 * db, b0 + 2 * db, 101))
    return g1, b1


# ============================================================================ 5. Metrics
def metrics(problem, p, exact=None):
    """P(opt) - share of the optimum; P(feas) - share of feasible states; P(opt|feas) - share of the optimum among
    feasible states; <H> - mean energy; mode - most frequent state; TVD - distance to theory (0 - identical, 1 - disjoint)."""
    p = np.asarray(p, dtype=float)
    p = p / p.sum()
    feas_sorted = [k for k in np.argsort(-p, kind="stable") if problem.feasible[k]]
    ranks = [r + 1 for r, k in enumerate(feas_sorted) if problem.optimal[k]]
    p_feas = float(p[problem.feasible].sum())
    m = {
        "p_opt": float(p[problem.optimal].sum()),
        "p_feasible": p_feas,
        "p_opt_given_feasible": float(p[problem.optimal].sum() / p_feas) if p_feas > 0 else None,
        "exp_H": float(p @ problem.E),
        "mode": xstr(int(np.argmax(p)), problem.n),
        "opt_rank_among_feasible": ranks[0] if ranks else None,
    }
    if exact is not None:
        m["tvd"] = float(0.5 * np.abs(p - np.asarray(exact)).sum())
    return m


# ============================================================================ 6. Result keys and bit order
def key_to_bits(key, n):
    """'0101' or '0x5' -> a string of n characters in the order the backend returned it."""
    k = str(key).strip().replace(" ", "")
    if k.lower().startswith("0x"):
        v = int(k, 16)
        if v >= 2 ** n:
            raise ValueError(f"key {key!r} does not fit into {n} bits")
        return format(v, f"0{n}b")
    if k and set(k) <= {"0", "1"} and len(k) <= n:
        return k.zfill(n)
    raise ValueError(f"unexpected result key {key!r}")


def detect_order(raw_calib, n):
    """Calibration: the circuit X(q0) must give a single 1. Its position in the key is the position of qubit 0."""
    agg = {}
    for key, val in raw_calib.items():
        b = key_to_bits(key, n)
        agg[b] = agg.get(b, 0.0) + float(val)
    total = sum(agg.values())
    top = max(agg, key=agg.get)
    if top.count("1") != 1 or top.index("1") not in (0, n - 1):
        raise RuntimeError(f"calibration X(q0) returned an unexpected key {top!r}: {agg}")
    return ("q0_left" if top.index("1") == 0 else "q0_right"), top, agg[top] / total


def raw_to_probs(raw, n, order):
    """{key: count or probability} -> probability array in our order (x0 is the most significant bit)."""
    arr = np.zeros(2 ** n)
    for key, val in raw.items():
        b = key_to_bits(key, n)
        if order == "q0_right":
            b = b[::-1]
        arr[int(b, 2)] += max(float(val), 0.0)
    if arr.sum() <= 0:
        raise ValueError("empty distribution")
    return arr / arr.sum()


def analyse_raw(problem, exact, raws):
    """Raw results of one backend -> bit order + probabilities and metrics for every circuit."""
    order, top, share = detect_order(raws["calib"], problem.n)
    out = {"order": order, "calib_top": top, "calib_share": share, "probs": {}, "metrics": {}}
    for name, raw in raws.items():
        if name == "calib" or name not in exact:
            continue
        p = raw_to_probs(raw, problem.n, order)
        out["probs"][name] = p
        out["metrics"][name] = metrics(problem, p, exact[name])
    return out


# ============================================================================ 7. pyqpanda3
def to_qprog(gates, n):
    """Our circuit -> QProg. At the end every qubit q is measured into classical bit q."""
    from pyqpanda3.core import QProg, H, X, RX, RZ, CNOT, measure
    prog = QProg()
    for g in gates:
        op = g[0]
        if op == "H":
            prog << H(g[1])
        elif op == "X":
            prog << X(g[1])
        elif op == "RX":
            prog << RX(g[1], float(g[2]))
        elif op == "RZ":
            prog << RZ(g[1], float(g[2]))
        elif op == "CNOT":
            prog << CNOT(g[1], g[2])
        else:
            raise ValueError(f"unknown gate {op}")
    for q in range(n):
        prog << measure(q, q)
    return prog
