

# ⚡ Q-Control-Optimization

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Framework](https://img.shields.io/badge/Quantum-pyqpanda3-purple.svg)](https://originqc.com.cn)

**Quantum-Classical Optimizer for Discrete Real-Time Control Systems.**

A research project (program 27.03.04 "Control in Technical Systems", UrFU IRIT-RTF) exploring quantum computing for NP-hard dispatching problems in smart grid emergency reconfiguration.

> 🇷🇺 **Русская версия документации:** Доступна в папке [`docs/ru/`](docs/ru/).

---

## 🔬 Project Overview

### The Problem: Smart Grid Emergency Reconfiguration
A critical failure at a main substation leaves 4 backup power lines. The Automatic Reserve Switch (ARS) must choose a configuration that **minimizes power losses** while satisfying hard safety constraints (e.g., avoiding short circuits and power overloads).

### Solution: QAOA on QUBO
We translate discrete control constraints into a **QUBO (Quadratic Unconstrained Binary Optimization)** Hamiltonian $H(\mathbf{x})$, where binary variables $x_i \in \{0,1\}$ represent line states. The **QAOA (Quantum Approximate Optimization Algorithm)** searches for the ground state (minimum energy) via quantum interference.

### Hardware Architecture (High Availability)
The system implements a **Triple-Tier Fallback Architecture** to ensure uninterrupted control signals:
1. **Tier 1:** OriginQC Wukong chip (72 physical superconducting qubits).
2. **Tier 2:** OriginQC Full-Amplitude Cloud HPC (Mathematical Statevector Simulator).
3. **Tier 3:** Local CPU Quantum Simulator (CPUQVM).

---

## 🚀 Quick Start

**1. Setup Environment**
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Run the Pipeline**
```bash
python src/qubo_builder.py      # 1. Translate constraints into QUBO matrix
python src/classical_solver.py  # 2. Find ground truth via Brute-Force
python src/quantum_solver.py    # 3. Execute QAOA (QPU/HPC/Local fallback)
python src/analyze_results.py   # 4. Calculate ε-metric and visualize
```

---

## 📚 Documentation (English)

Detailed documentation covering the mathematical model, algorithm physics, and hardware integration:

* **[01. Problem Statement & Mathematical Model](docs/en/01-problem-statement.md)**
* **[02. Algorithm Explained (QAOA Physics)](docs/en/02-algorithm-explained.md)**
* **[03. Hardware Integration & Fallback Architecture](docs/en/03-hardware-integration.md)**
* **[04. Experimental Results & Analysis](docs/en/04-experimental-results.md)**
* **[05. Advanced QAOA Theory](docs/en/05-advanced-qaoa.md)**

---

## 📊 Key Results

| Metric | Value |
|--------|-------|
| Classical optimum | `0101` ($H = 1.700$) |
| Quantum best (valid) | `0101` ($H = 1.700$) |
| Deviation ($\epsilon$) | **0.0%** ✅ |
| Hypothesis ($\epsilon \le 10\%$) | **PASSED** |

> *See [Experimental Results](docs/en/04-experimental-results.md) for full histograms and physical noise analysis.*

---

## 📄 License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

