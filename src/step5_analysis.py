# -*- coding: utf-8 -*-
"""
Step 5. Results analysis: theory vs simulators vs quantum computer.

What it does: collects everything that is available - theory (step 2), CPUQVM (step 3), cloud simulator and QPU
(step 4), converts the backends' answers into one bit order, computes the metrics and prints conclusions.
Steps 3 and 4 are optional: the analysis uses whichever sources are ready.

Metrics (for every circuit and every source):
  P(opt)       - share of shots with the optimal answer 0101;
  P(feas)      - share of feasible answers (exactly 2 lines and no short circuit);
  P(opt|feas)  - share of the optimum among feasible answers: can the circuit pick the best feasible state
                 (a random choice among the 5 feasible states gives 20%);
  <H>          - mean energy of the answer (lower is better);
  rank         - place of the optimum among feasible states by frequency (1 = most frequent);
  TVD          - distance to theory: 0 - identical, 1 - nothing in common.

Input:  results/step1..step4 (whatever exists)
Output: results/step5_report.md, results/step5_plot.png
Run:    python src/step5_analysis.py      (in Jupyter: %run src/step5_analysis.py)
"""
import importlib
import os
import sys
import time
from datetime import datetime

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

MAIN = ["penalty_qaoa", "xy_qaoa", "legacy_qaoa"]
COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]          # validated palette: blue, orange, teal
INK, INK2, SURFACE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e4e3df"


def collect_sources(P, exact):
    """[(label, analysis)] for every finished source with measurements."""
    out = []
    if os.path.exists(C.STEP3_PATH):
        s3 = C.load_json(C.STEP3_PATH, "step 3")
        out.append(("CPUQVM (noiseless simulator)", C.analyse_raw(P, exact, s3["raw"])))
    if os.path.exists(C.STEP4_PATH):
        s4 = C.load_json(C.STEP4_PATH, "step 4")
        for t in s4["tiers"]:
            if t["status"] == "done":
                label = f"{t['backend']} ({'QPU' if t.get('type') == 'qpu' else 'cloud simulator'})"
                out.append((label, C.analyse_raw(P, exact, t["raw"])))
            else:
                print(f"   {t['backend']}: {'still running' if t['status'] == 'pending' else 'error'} - "
                      f"not included in the analysis")
    return out


def rows_for(P, exact, sources, name):
    uni = np.full(2 ** P.n, 1 / 2 ** P.n)
    rows = [("random guess", C.metrics(P, uni, exact[name])),
            ("theory (noiseless)", C.metrics(P, exact[name], exact[name]))]
    rows += [(label, a["metrics"][name]) for label, a in sources if name in a["metrics"]]
    return rows


def fmt_row(label, m):
    pof = m["p_opt_given_feasible"]
    return (f"| {label} | {m['p_opt']:.1%} | {m['p_feasible']:.1%} | "
            f"{(f'{pof:.1%}' if pof is not None else '-')} | {m['exp_H']:.2f} | {m['mode']} | "
            f"{m['opt_rank_among_feasible']} | {m['tvd']:.3f} |")


def conclusions(P, exact, sources):
    opt = P.opt_strings()[0]
    k_opt = int(opt, 2)
    n_states = 2 ** P.n
    rnd_f = 1.0 / int(P.feasible.sum())          # random choice among the feasible states
    lines = []
    for label, a in sources:                      # headline for every quantum computer
        if "(QPU)" not in label or not a["metrics"]:
            continue
        best = max(a["metrics"], key=lambda c: a["metrics"][c]["p_opt"])
        m = a["metrics"][best]
        place = ("the most frequent outcome" if m["mode"] == opt
                 else f"rank {m['opt_rank_among_feasible']} among feasible states")
        lines.append(f"- **Summary, {label}:** the best circuit is {best}. The optimum {opt} is {place}: "
                     f"P(opt) = {m['p_opt']:.1%} ({m['p_opt'] * n_states:.1f}x a random guess), "
                     f"P(opt|feas) = {m['p_opt_given_feasible']:.0%} (random choice {rnd_f:.0%}).")
    for name in [c for c in MAIN if c in exact]:
        th_popt = float(exact[name][k_opt])
        series = [("theory", exact[name], False)] + [(lbl, a["probs"][name], "(QPU)" in lbl)
                                                      for lbl, a in sources if name in a["probs"]]
        for label, p, is_qpu in series:
            m = C.metrics(P, p)
            margin = m["p_opt"] - max(p[k] for k in range(n_states) if k != k_opt)
            if m["mode"] == opt:
                where = (f"the most frequent outcome, but only {100 * margin:.1f} pp ahead of the next one "
                         f"(effectively a tie)" if margin < 0.01
                         else f"the most frequent outcome ({100 * margin:.1f} pp ahead of the next one)")
            else:
                where = (f"not the most frequent outcome (most frequent: {m['mode']}; the optimum is "
                         f"rank {m['opt_rank_among_feasible']} among feasible states)")
            pof = m["p_opt_given_feasible"]
            if pof >= 1.5 * rnd_f:
                select = f"it is selected among feasible states: {pof:.0%} vs {rnd_f:.0%} for a random choice"
            elif pof >= 0.8 * rnd_f:
                select = f"it is not selected among feasible states: {pof:.0%}, close to a random choice ({rnd_f:.0%})"
            else:
                select = f"among feasible states it is below a random choice: {pof:.0%} vs {rnd_f:.0%}"
            keep = (f"; the chip keeps {m['p_opt'] / th_popt:.0%} of the noiseless P(opt)"
                    if is_qpu and th_popt > 0 else "")
            lines.append(f"- **{name}, {label}:** the optimum {opt} is {where}; P(opt) = {m['p_opt']:.1%} "
                         f"({m['p_opt'] * n_states:.1f}x a random guess){keep}; {select}.")
    for label, a in sources:
        side = "rightmost" if a["order"] == "q0_right" else "leftmost"
        lines.append(f"- Bit order, {label}: qubit 0 is the {side} character of the key "
                     f"(calibration {a['calib_top']!r}, {a['calib_share']:.0%}).")
    return lines


def plot(P, exact, sources, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [c for c in ("penalty_qaoa", "xy_qaoa") if c in exact]
    order = sorted(range(2 ** P.n), key=lambda k: P.E[k])
    labels = [C.xstr(k, P.n) + ("*" if P.optimal[k] else "") for k in order]
    nfeas = int(P.feasible.sum())
    fig, axes = plt.subplots(len(names), 1, figsize=(11, 3.6 * len(names)), facecolor=SURFACE, squeeze=False)
    for ax, name in zip(axes[:, 0], names):
        ax.set_facecolor(SURFACE)
        ax.axvspan(-0.5, nfeas - 0.5, color=GRID, alpha=0.6, lw=0, zorder=0)
        ax.text(nfeas / 2 - 0.5, 0.97, "feasible", transform=ax.get_xaxis_transform(), ha="center",
                va="top", color=INK2, fontsize=9)
        m = len(sources)
        width = 0.8 / max(m, 1)
        xs = np.arange(len(order))
        for i, (label, a) in enumerate(sources[:3]):
            if name not in a["probs"]:
                continue
            ys = [100 * a["probs"][name][k] for k in order]
            ax.bar(xs - 0.4 + width * (i + 0.5), ys, width, color=COLORS[i], label=label,
                   edgecolor=SURFACE, linewidth=1.0, zorder=2)
        th = [100 * exact[name][k] for k in order]
        ax.hlines(th, xs - 0.42, xs + 0.42, colors=INK, linewidth=2, label="theory", zorder=3)
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, rotation=45, fontsize=9, color=INK2)
        ax.set_ylabel("share of shots, %", color=INK2)
        ax.set_title(f"{name}: distribution of the 16 outcomes (* optimum; energy grows from left to right)",
                     loc="left", fontsize=11, color=INK)
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=1)
        ax.tick_params(colors=INK2)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(INK2)
        ax.legend(loc="upper right", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main():
    t0 = time.time()
    s2, P, gates, exact = C.load_circuits()
    print("=" * 72)
    print("STEP 5. Analysis: theory, simulators, quantum computer")
    print("=" * 72)
    sources = collect_sources(P, exact)
    if not sources:
        print("   no measurements yet - comparing with theory only (run step 3 and/or step 4)")

    md = [f"# Step 5. Results analysis", "",
          f"Created: {datetime.now().isoformat(timespec='seconds')}. Optimum of the problem: {P.opt_strings()} "
          f"(H = {P.E_opt:.3f}). Sources: theory" + "".join(f", {lbl}" for lbl, _ in sources) + ".", ""]
    header = "| source | P(opt) | P(feas) | P(opt\\|feas) | ⟨H⟩ | most frequent | optimum rank | TVD |"
    for name in [c for c in MAIN if c in exact]:
        md += [f"## {name} - {s2['circuits'][name]['title']}", "", header, "|---|---|---|---|---|---|---|---|"]
        md += [fmt_row(label, m) for label, m in rows_for(P, exact, sources, name)]
        md.append("")
        print(f"\n{name} ({s2['circuits'][name]['title']}):")
        print(f"   {'source':<36}{'P(opt)':>8}{'P(feas)':>9}{'P(opt|f)':>10}{'<H>':>8}  {'mode':<7}{'rank':>5}{'TVD':>7}")
        for label, m in rows_for(P, exact, sources, name):
            pof = m["p_opt_given_feasible"]
            print(f"   {label[:35]:<36}{m['p_opt']:8.1%}{m['p_feasible']:9.1%}"
                  f"{(f'{pof:.1%}' if pof is not None else '-'):>10}{m['exp_H']:8.2f}  {m['mode']:<7}"
                  f"{str(m['opt_rank_among_feasible']):>5}{m['tvd']:7.3f}")

    order = sorted(range(2 ** P.n), key=lambda k: P.E[k])
    for name in [c for c in ("penalty_qaoa", "xy_qaoa") if c in exact]:
        md += [f"### {name}: probabilities of all 16 outcomes, %", "",
               "| x | H | feasible | theory | " + " | ".join(lbl for lbl, _ in sources) + " |",
               "|---|---|---|---|" + "---|" * len(sources)]
        for k in order:
            cells = [f"{100 * a['probs'][name][k]:.1f}" if name in a["probs"] else "-" for _, a in sources]
            md.append(f"| {C.xstr(k, P.n)}{' *' if P.optimal[k] else ''} | {P.E[k]:.1f} | "
                      f"{'yes' if P.feasible[k] else '-'} | {100 * exact[name][k]:.1f} | " + " | ".join(cells) + " |")
        md.append("")

    concl = conclusions(P, exact, sources)
    md += ["## Conclusions", ""] + concl + ["", f"![Plot](step5_plot.png)", ""]
    print("\nConclusions:")
    for line in concl:
        print("   " + line.replace("**", ""))

    plot(P, exact, sources, C.STEP5_PLOT)
    os.makedirs(C.RESULTS_DIR, exist_ok=True)
    with open(C.STEP5_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"\nSaved: {C.rel(C.STEP5_REPORT)}, {C.rel(C.STEP5_PLOT)}   ({time.time() - t0:.1f} s)")
    try:                                     # in Jupyter show the plot right below the cell
        from IPython import get_ipython
        if get_ipython() is not None:
            from IPython.display import Image, display
            display(Image(filename=C.STEP5_PLOT))
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    main()
