# -*- coding: utf-8 -*-
"""
Step 4. Run in the OriginQC cloud: the Wukong 180-2 quantum computer (and, if enabled in config.json,
the full_amplitude cloud simulator).

Works in two phases and never waits inside a run (notebook cell time limit):
  1st run      submits the jobs, immediately saves their ids (job_id) to results/step4_cloud.json and
               checks the status once;
  later runs   only check the status of the saved jobs and collect finished results.
               No new jobs are submitted unless the script is run with --new.

The API key is looked up in this order: environment variable ORIGINQC_API_KEY -> file key.txt next to the notebook
(or in src/) -> hidden input field. The file holds one line with the key only. The key itself is never printed.
key.txt is listed in .gitignore and never gets into the repository.
QCloudService.setup_logging() is not called: it prints the authorization header together with the key.

Input:  results/step2_circuits.json, data/config.json (section experiment)
Output: results/step4_cloud.json
Run:    %run src/step4_cloud_run.py         repeat until all jobs are finished
        %run src/step4_cloud_run.py --new   submit new jobs (spends QPU machine time)
        In the notebook (code in a cell): for a new submission delete results/step4_cloud.json and run the cell again.
"""
import getpass
import importlib
import os
import sys
import time
from datetime import datetime

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

_T0 = time.time()

# Job objects survive between %run calls in one kernel; after a kernel restart the jobs are found by job_id.
if not hasattr(sys, "_qcontrol_live_jobs"):
    sys._qcontrol_live_jobs = {}
_LIVE_JOBS = sys._qcontrol_live_jobs


def clean_key(text):
    """First non-empty line without spaces, quotes and the invisible BOM mark."""
    for line in text.replace("﻿", "").splitlines():
        line = line.strip().strip('"').strip("'").strip()
        if line:
            return line
    return ""


def read_api_key():
    key = clean_key(os.environ.get("ORIGINQC_API_KEY", ""))
    if key:
        return key, "environment variable ORIGINQC_API_KEY"
    for path in (os.path.join(C.ROOT, "key.txt"), os.path.join(C.ROOT, "src", "key.txt")):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                key = clean_key(f.read())
            if key:
                return key, f"file {C.rel(path)}"
    return clean_key(getpass.getpass("OriginQC API key (input hidden): ")), "input field"


def make_service():
    from pyqpanda3.qcloud import QCloudService
    key, source = read_api_key()
    if not key:
        raise RuntimeError("no API key: put it into key.txt next to the notebook")
    print(f"API key: {source}, length {len(key)} characters")
    return QCloudService(key)


def _remember(job):
    jid = job.job_id()
    _LIVE_JOBS[jid] = job
    return jid


def submit_simulator(service, backend_name, n, gates, shots):
    """Cloud simulator: one job per circuit, without QCloudOptions (only the QPU accepts them)."""
    backend = service.backend(backend_name)
    jobs = []
    for name, g in gates.items():
        jid = _remember(backend.run(C.to_qprog(g, n), shots))
        jobs.append({"job_id": jid, "circuits": [name], "status": "pending"})
        print(f"   submitted: {name:<13} job_id={jid}")
    return jobs, {}


def submit_qpu(service, backend_name, n, gates, shots, amend):
    """Quantum computer: all circuits in one batch job - one place in the queue."""
    from pyqpanda3.qcloud import QCloudOptions
    info = {}
    try:
        flags = service.backends()
        info["available"] = flags.get(backend_name) if isinstance(flags, dict) else None
        print(f"   available backends: {list(flags)}")
        print(f"   {backend_name}: availability flag = {info['available']}")
    except Exception as e:  # noqa: BLE001
        print(f"   backends() did not respond: {type(e).__name__}: {e}")
    opt = QCloudOptions()
    opt.set_mapping(True)            # the compiler chooses the physical qubits on the chip
    opt.set_optimization(True)       # and simplifies the circuit
    opt.set_amend(amend)             # readout error correction based on the platform calibration
    info["options"] = {"mapping": opt.is_mapping(), "optimization": opt.is_optimization(), "amend": opt.is_amend()}
    print(f"   options: {info['options']}")
    names = list(gates)
    progs = [C.to_qprog(gates[k], n) for k in names]
    print(f"   submitting {len(progs)} circuits with {shots} shots each: {names}")
    jid = _remember(service.backend(backend_name).run(progs, shots, opt))
    print(f"   submitted as one batch job: job_id={jid}")
    return [{"job_id": jid, "circuits": names, "status": "pending"}], info


def result_distributions(res, m):
    """Cloud response -> m dicts {key: value}. By default the QPU returns probabilities, not counts."""
    for getter, kind in (("get_counts_list", "counts"), ("get_probs_list", "probs")):
        try:
            lst = list(getattr(res, getter)())
        except Exception:  # noqa: BLE001
            continue
        if len(lst) == m and all(len(d) > 0 for d in lst):
            return [dict(d) for d in lst], kind
    if m == 1:
        for getter, kind in (("get_counts", "counts"), ("get_probs", "probs")):
            try:
                d = dict(getattr(res, getter)())
            except Exception:  # noqa: BLE001
                continue
            if d:
                return [d], kind
    raise RuntimeError(f"the response contains no results for {m} circuits: {str(res.origin_data())[:300]}")


def poll(job_rec):
    """One status check without waiting: ('pending' | 'done' | 'failed', data)."""
    job = _LIVE_JOBS.get(job_rec["job_id"])
    if job is None:
        from pyqpanda3.qcloud import QCloudJob
        job = QCloudJob(job_rec["job_id"])
        _LIVE_JOBS[job_rec["job_id"]] = job
    st = str(job.status()).upper()
    if "FINISHED" in st:
        lst, kind = result_distributions(job.result(), len(job_rec["circuits"]))
        return "done", {"kind": kind, "raw": {c: {str(k): float(v) for k, v in d.items()}
                                              for c, d in zip(job_rec["circuits"], lst)}}
    if "FAILED" in st:
        return "failed", str(job.result().origin_data())[:400]
    return "pending", st.split(".")[-1]


def refresh(state, service, budget):
    for t in state["tiers"]:
        if t["status"] != "pending":
            continue
        for j in t["jobs"]:
            if j["status"] != "pending":
                continue
            if budget - (time.time() - _T0) < 5:
                print(f"   time budget of this run ({budget} s) is used up - the next run will check the rest")
                return
            try:
                st, data = poll(j)
            except Exception as e:  # noqa: BLE001
                print(f"   [{t['backend']}] {j['job_id']}: status check error: {type(e).__name__}: {e}")
                continue
            if st == "done":
                j.update(status="done", kind=data["kind"], raw=data["raw"])
                print(f"   [{t['backend']}] {j['job_id']} {j['circuits']}: done")
            elif st == "failed":
                j.update(status="failed", error=data)
                print(f"   [{t['backend']}] {j['job_id']} {j['circuits']}: ERROR {data}")
            else:
                print(f"   [{t['backend']}] {j['job_id']} {j['circuits']}: {data}")
        statuses = [j["status"] for j in t["jobs"]]
        if "failed" in statuses:
            t["status"] = "failed"
            t["error"] = "; ".join(f"{j['job_id']}: {j.get('error')}" for j in t["jobs"] if j["status"] == "failed")
        elif statuses and all(s == "done" for s in statuses):
            t.update(status="done", result_kind=t["jobs"][0]["kind"],
                     raw={c: r for j in t["jobs"] for c, r in j["raw"].items()})


def new_submission(s2, P, gates, ex):
    shots, n = ex["shots"], P.n
    state = {"created": datetime.now().isoformat(timespec="seconds"), "pyqpanda3": C.pyqpanda3_version(),
             "shots": shots, "tiers": []}
    plan = []                        # QPU first: its queue is the longest
    if ex.get("qpu_backend"):
        qpu_gates = {k: gates[k] for k in ex["qpu_circuits"] if k in gates}
        plan.append((ex["qpu_backend"], "qpu", qpu_gates))
    if ex.get("cloud_simulator"):
        plan.append((ex["cloud_simulator"], "simulator", gates))
    service = make_service()
    for backend, kind, g in plan:
        print(f"\n--- {backend}: submitting ---")
        try:
            if kind == "qpu":
                jobs, info = submit_qpu(service, backend, n, g, shots, ex.get("qpu_amend", True))
            else:
                jobs, info = submit_simulator(service, backend, n, g, shots)
            state["tiers"].append({"backend": backend, "type": kind, "status": "pending", "jobs": jobs, "info": info})
        except Exception as e:  # noqa: BLE001
            state["tiers"].append({"backend": backend, "type": kind, "status": "failed", "jobs": [],
                                   "error": f"{type(e).__name__}: {e}"})
            print(f"   NOT SUBMITTED: {type(e).__name__}: {e}")
            if "unauthorized" in str(e).lower():
                print("   -> the server rejected the key. Check that key.txt contains only the key from the OriginQC console")
                print("      (no 'api_key =', quotes or extra lines); if the key was reissued, the new one is needed.")
        C.save_json(C.STEP4_PATH, state)       # job ids are on disk right after submission
    return state, service


def main():
    global _T0
    _T0 = time.time()
    s2, P, gates, exact = C.load_circuits()
    ex = C.run_settings(s2)
    budget = ex.get("time_budget_sec", 35)
    print("=" * 72)
    print(f"STEP 4. OriginQC cloud: QPU {ex.get('qpu_backend')}, simulator {ex.get('cloud_simulator') or 'off'} "
          f"(pyqpanda3 {C.pyqpanda3_version()})")
    print("=" * 72)
    service, state = None, None
    if os.path.exists(C.STEP4_PATH) and "--new" not in sys.argv:
        state = C.load_json(C.STEP4_PATH, "step 4")
        if not any(t["jobs"] for t in state["tiers"]):
            print("The previous submission created no jobs - submitting again.")
            state = None
        else:
            print(f"Resuming: jobs submitted {state['created']} (--new submits new ones)")
    if state is None:
        state, service = new_submission(s2, P, gates, ex)

    if any(t["status"] == "pending" for t in state["tiers"]):
        print("\n--- checking jobs ---")
        if service is None:
            service = make_service()
        refresh(state, service, budget)
        C.save_json(C.STEP4_PATH, state)

    print("\nSummary by backend:")
    for t in state["tiers"]:
        if t["status"] == "done":
            res = C.analyse_raw(P, exact, t["raw"])
            side = "rightmost" if res["order"] == "q0_right" else "leftmost"
            print(f"   {t['backend']:<16} done ({t['result_kind']}); qubit 0 is the {side} character of the key")
            for name, m in res["metrics"].items():
                print(f"      {name:<13} P(opt)={m['p_opt']:6.1%}  P(feas)={m['p_feasible']:6.1%}  "
                      f"P(opt|feas)={m['p_opt_given_feasible']:6.1%}  TVD={m['tvd']:.3f}")
        elif t["status"] == "pending":
            waiting = [j["job_id"] for j in t["jobs"] if j["status"] == "pending"]
            print(f"   {t['backend']:<16} still running: {waiting}")
        else:
            print(f"   {t['backend']:<16} ERROR: {t.get('error')}")
    if any(t["status"] == "pending" for t in state["tiers"]):
        print("\nNot all jobs are finished. Run this cell again in 1-2 minutes - no new jobs will be submitted.")
    elif any(t["status"] == "done" for t in state["tiers"]):
        print(f"\nAll jobs finished. Next: step 5 (src/step5_analysis.py). File: {C.rel(C.STEP4_PATH)}")
    else:
        print("\nNo job has finished - see the errors above. Fix the cause and run the cell again:"
              "\nif no jobs were created, the submission is repeated automatically.")
    print(f"(this run took {time.time() - _T0:.1f} s)")


if __name__ == "__main__":
    main()
