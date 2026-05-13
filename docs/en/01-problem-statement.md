# 📘 Problem Statement and Scientific Hypothesis

> **A classic problem in control theory and power engineering.** The sum constraint perfectly models "bus bandwidth/power balance," while mutual exclusion models "short-circuit protection."

---

## 1. Formal Problem Statement

**Case Title:** Emergency Reconfiguration of a Micro-grid (Smart Grid) using Quantum Optimization.

**Context:**
A critical failure has occurred at a main substation of an industrial facility. There are 4 backup power lines (generators/UPS) available. The Automatic Transfer Switch (ATS) system must urgently select a connection configuration.

**Objective:** Select the active power lines to minimize total power losses (objective function).

**Hard Automation Constraints:**
1. 🔹 **Power Balance (Equality):** Exactly 2 lines must be active simultaneously (`Σx_i = 2`). Fewer active lines will result in a power shortage for the facility; more active lines will overload and burn out the backup distribution bus.
2. 🔸 **Topological Conflict (Inequality):** Lines `0` and `3` are powered by the same damaged transformer. Activating them simultaneously will cause a short circuit (`x₀·x₃ = 0`).

**Relevance to "Control in Technical Systems" Engineering:**
This task models a critical dispatch control problem—finding a safe and optimal control action under strict constraints. As the number of nodes in a Smart Grid grows, the complexity of classical brute-force search increases exponentially. This project explores the potential of Quantum Processing Units (QPUs) as a future alternative to PLCs (Programmable Logic Controllers) for instantly solving NP-hard dispatching problems.

---

## 2. Mathematical Model (QUBO)

### Variables
$$x_i \in \{0,1\}, \quad i = 0,1,2,3$$
where $x_i=1$ means the line is active, and $x_i=0$ means it is deactivated.

### Objective Function (Power Loss Minimization)
$$\min \; f(\mathbf{x}) = \sum_{i=0}^{3} c_i x_i, \quad \mathbf{c} =[1.2,\; 0.8,\; 1.5,\; 0.9]$$
*(Coefficients represent the electrical resistance/operational cost of a specific line).*

### Constraints → Penalty Terms
To run this on a quantum computer, constraints must be embedded into the energy landscape using penalties:
1. **Preventing bus overload/underload** $\sum x_i = 2$:
   $$P_1 \left( \sum_{i=0}^3 x_i - 2 \right)^2$$
2. **Preventing transformer short circuit** $x_0 x_3 = 0$:
   $$P_2 \cdot x_0 x_3$$

### Final Energy Hamiltonian
$$H(\mathbf{x}) = \sum_{i} c_i x_i + P_1 \left( \sum_{i} x_i - 2 \right)^2 + P_2 x_0 x_3$$
This function is translated into the quantum gates of the QAOA algorithm, where the search for minimum power loss is replaced by finding the ground quantum state of the system.

---

## 3. Scientific Hypothesis and Methodology

### ✅ Hypothesis
> *"In discrete control problems with hard constraints (e.g., micro-grids), a hybrid quantum algorithm QAOA (even at a depth of $p=1$ on NISQ-class devices) is capable of isolating the optimal control action. The paradigm shift—from step-by-step brute forcing to quantum interference—proves the fundamental feasibility of using QPUs in real-time systems in the future, once hardware qubit errors are mitigated."*

### 📊 Validation Criteria
- [x] The theoretical QUBO matrix is correctly mapped into the physics of the quantum simulator (penalties work).
- [x] The quantum algorithm finds the global optimum (deviation $\epsilon \le 10\%$).
- [x] Safety constraints (sum=2, no conflicts) are met in a significant portion of the measurements (considering unoptimized $\gamma, \beta$ parameters).
- [x] The script's automation completes within the 60-second execution limit on the OriginQC Cloud.

---

## 4. Controller Configuration (`config.json`)

```json
{
  "n_vars": 4,
  "objective_costs": [1.2, 0.8, 1.5, 0.9],
  "equality_constraints": [
    {
      "indices": [0, 1, 2, 3],
      "target_sum": 2,
      "penalty": 50.0
    }
  ],
  "inequality_constraints": [
    {
      "indices": [0, 3],
      "penalty": 100.0,
      "type": "mutual_exclusion"
    }
  ],
  "qaoa_params": {
    "p": 1,
    "gamma": 0.5,
    "beta": 0.3
  }
}
```

🔍 **Physical meaning of the penalties:**
- $P_1=50.0$: The risk of a total facility blackout due to incorrect power output is evaluated by the automation system as much "more expensive" than power wire losses (1.2 - 1.5).
- $P_2=100.0$: A short circuit is a critical emergency. The probability of this state must be suppressed as strictly as possible by the quantum algorithm.

---

## 5. Energy Landscape and Expected Results

Analyzing the energy landscape reveals the following states (out of 16 possible):

| State $x$ (Lines) | System Energy (H) | ATS Status | Reason for Rejection |
|-------------------|-------------------|------------|----------------------|
| `0 1 0 1`         | **1.700**         | 🏆 **Optimum** | Perfect balance, lines 1 and 3 active. |
| `1 1 0 0`         | 2.000             | ✅ Valid | Power loss is higher than optimum (2.0 > 1.7). |
| `0 1 1 0`         | 2.300             | ✅ Valid | Power loss is higher than optimum (2.3 > 1.7). |
| `1 0 0 1`         | 102.100           | ❌ Emergency (Short Circuit) | Violated 0↔3 constraint (Penalty 100). |
| `0 0 0 1`         | 50.900            | ❌ Emergency (Power) | Only 1 active line (Penalty 50). |

📌 **Quantum Expectations:**
Due to the shallow depth $p=1$ and fixed unoptimized angles $\gamma, \beta$, we expect a "blurred" distribution. The quantum system will produce errors (emergency states), but among the valid solutions, the probability peak will confidently aggregate around the global optimum `0101`. This proves the viability of quantum physics for solving logical control engineering tasks.
