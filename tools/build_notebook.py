# -*- coding: utf-8 -*-
"""
Builds notebook/qcontrol_originqc.ipynb from the project files: the code of every file goes 1:1 into its own cell,
preceded by an explanation. The notebook is self-contained: it is uploaded to the OriginQC JupyterLab as a single
file and creates config.json itself. Rebuild after any change in src/ or data/config.json:

    python3 tools/build_notebook.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "notebook", "qcontrol_originqc.ipynb")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read().rstrip("\n")


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": text.strip("\n").splitlines(keepends=True)}


def file_cell(rel):
    return code(f"# ===== {rel} (project file, 1:1) =====\n{read(rel)}\n")


CONFIG_CELL = '''# ===== data/config.json - problem and run parameters =====
# This cell writes data/config.json next to the notebook. Parameters can be changed right here.
import json, os
CONFIG = json.loads("""
{config}
""")
os.makedirs("data", exist_ok=True)
with open("data/config.json", "w", encoding="utf-8") as f:
    json.dump(CONFIG, f, indent=2, ensure_ascii=False)
print("Written data/config.json:", json.dumps(CONFIG["experiment"], ensure_ascii=False))
'''

KEY_CELL = '''# ===== API key =====
# The key is stored in the file key.txt next to the notebook (or in src/key.txt): one line, the key only.
# To create the file in JupyterLab: File -> New -> Text File, paste the key, save as key.txt.
# The cell puts the key into the kernel memory for step 4. The key itself is never printed.
import os
os.environ.pop("ORIGINQC_API_KEY", None)          # forget a key entered earlier through an input field
for path in ("key.txt", os.path.join("src", "key.txt")):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = [l.strip().strip('"').strip("'").strip() for l in f.read().replace("\\ufeff", "").splitlines()]
        key = next((l for l in lines if l), "")
        os.environ["ORIGINQC_API_KEY"] = key
        warn = " - WARNING: the key contains a space or '='" if any(c.isspace() or c == "=" for c in key) else ""
        print(f"Key taken from {path}: length {len(key)} characters{warn}")
        break
else:
    print("No key.txt next to the notebook - create it (see the comment above)")
'''

NEW_RUN_CELL = '''# ===== Only for a NEW run on the QPU (spends machine time) =====
# Uncomment the line, run this cell ONCE, then run the step 4 cell again.
# import os; os.remove("results/step4_cloud.json")
'''


def build():
    cfg = read("data/config.json")
    cells = [
        md("""
# Q-Control-Optimization: choosing backup lines of a substation on a quantum computer

The notebook is built from the project files: every code cell is a file from `src/`, copied 1:1.
**Run the cells from top to bottom** (Shift+Enter). The results appear in the `results/` folder next to the notebook.

| Cell | What it does | Time |
|---|---|---|
| API key | reads the key from `key.txt` into the kernel memory (needed only for step 4) | - |
| Settings | writes `data/config.json` | instant |
| Shared functions | defines the functions used by all steps, prints nothing | instant |
| Step 1 | problem, energies of all 16 states, optimum by brute force | < 1 s |
| Step 2 | quantum circuits, angle tuning, theory | a few seconds |
| Step 3 | CPUQVM simulator (no internet) - optional | < 1 s |
| Step 4 | submission to the Wukong 180-2 quantum computer and collection of the result | seconds per run |
| Step 5 | comparison of theory, simulator and QPU, plot | ~1 s |
"""),
        md("""
## API key
Create the file `key.txt` next to the notebook (File -> New -> Text File) and paste only the key from the
OriginQC console into it - one line, no quotes and no `api_key =`. The key does not get into the notebook and is not printed.
"""),
        code(KEY_CELL),
        md("""
## Settings
The problem (line losses, constraints, penalties) and the run parameters. The most important for a run:
`shots` - how many times each circuit is executed, `qpu_backend` - the quantum computer
(`WK_C180`, `WK_C180_2`, `WK_C180_3`), `qpu_circuits` - which circuits are sent to it,
`cloud_simulator` - cloud simulator (off: `null`).
"""),
        code(CONFIG_CELL.replace("{config}", cfg)),
        md("""
## Shared functions (src/common.py)
QUBO construction, gates and circuits, exact simulator, angle tuning, metrics, parsing of the backend's answers.
The cell only defines functions - there is no output. Run it before the steps.
"""),
        file_cell("src/common.py"),
        md("""
## Step 1. Problem statement
Prints the QUBO matrix, the energy of all 16 ways to switch the lines with an assessment (optimum / feasible /
which constraint is violated) and the classical optimum. Creates `results/step1_problem.json`.
"""),
        file_cell("src/step1_problem.py"),
        md("""
## Step 2. Quantum circuits and theory
Builds 4 circuits (`calib`, `penalty_qaoa`, `xy_qaoa`, `legacy_qaoa`), runs self-tests, tunes the angles on an exact
simulator and prints the theoretical probabilities: how often each circuit should return the optimum without noise.
Creates `results/step2_circuits.json`. Takes a few seconds.
"""),
        file_cell("src/step2_circuits.py"),
        md("""
## Step 3. CPUQVM simulator (optional)
Runs the circuits on a noiseless simulator inside the notebook and compares them with theory. Shows where qubit 0
is placed in the answer (calibration). No internet and no key needed. Creates `results/step3_local.json`.
"""),
        file_cell("src/step3_local_run.py"),
        md("""
## Step 4. Wukong 180-2 quantum computer
**The first run** submits one batch job (circuits `calib`, `penalty_qaoa`, `xy_qaoa`) and finishes immediately -
the job id is saved to `results/step4_cloud.json`.

**After that run this same cell every 1-2 minutes**: it only checks the status and submits no new jobs. When it
prints "All jobs finished", go to step 5. The status and the machine time spent are also visible in the OriginQC
console, page Jobs (column Usage (seconds)). If `results/step4_cloud.json` with a finished job already exists,
the cell only shows its result and does not contact the cloud.
"""),
        file_cell("src/step4_cloud_run.py"),
        md("""
### New run on the QPU (optional)
Needed only if you want to submit the job again.
"""),
        code(NEW_RUN_CELL),
        md("""
## Step 5. Analysis
Compares theory, CPUQVM and the quantum computer: metric tables, conclusions and a plot below the cell.
Creates `results/step5_report.md` and `results/step5_plot.png` - they can be downloaded (right click - Download).
"""),
        file_cell("src/step5_analysis.py"),
    ]
    nb = {"cells": cells,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 4}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print(f"Built {os.path.relpath(OUT, ROOT)}: {len(cells)} cells")


if __name__ == "__main__":
    build()
