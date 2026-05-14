
# 🧬 Hardware Integration and High Availability Architecture

During the integration with the **OriginQC cloud platform (Wukong chip, 72 qubits)**, we identified critical nuances of operating real quantum "hardware" that distinctly separate it from ideal mathematical simulators.

---

## 1. Topological Mapping and SWAP Gates (Qubit Connectivity)

In our mathematical model (QUBO), we defined a penalty for the conflict between power lines 0 and 3. In the quantum circuit, this translates to the interaction gate `CNOT(0, 3)`. However, querying the Wukong chip's API returned the following physical topology (the connectivity graph of its microwave resonators):

```python
# Snippet of the physical qubit connectivity graph for Origin Wukong
[[1, 7], [2, 3], [2, 8], [3, 4], [4, 5], [4, 10], [5, 11], [7, 8], [7, 13], ...]
```

![Wukong chip topology and gate fidelities](../assets/Wukong_Qbits_info.png)

Analysis revealed that **there is no direct physical connection between arbitrary qubits (e.g., qubits 0 and 3)**.

**The Hardware Solution:** 
The OriginQC cloud compiler automatically performs *Topological Mapping*. It maps our logical qubits (0, 1, 2, 3) to adjacent physical qubits on the chip (e.g., 2, 3, 4, 5) and injects additional **SWAP gates** (quantum state exchange operations) to "move" the information of neighboring qubits next to each other to perform the CNOT. 

*Consequence:* Every SWAP gate increases the circuit depth and introduces physical noise (**Gate Infidelity**), which explains the discrepancy in results between a local simulator and a real QPU.

---

## 2. Industrial Realities of QaaS (Quantum-as-a-Service)

We established that access to real quantum processing power is strictly regulated and architecturally segmented:

1. **Environment Routing (API Separation):** 
   Sending a single program via `run(prog)` routes the task to a Mathematical Supercomputer (`Full_AMPLITUDE`). This HPC cluster calculates the exact state tensor $|\psi\rangle$ and **hardware-blocks** measurement operations (`measure()`) because they destroy the superposition. Accessing the measurement pathways of a real QPU requires a batch submission mode `run([prog], shots)`, which instructs the compiler to generate physical microwave readout pulses.

2. **Quotas and Access Control:** 
   The `Quantum computer under maintenance` error encountered during batch submission is the system's standard response (HTTP 403 Forbidden) for accounts lacking extended industrial clearance (HPC Application Review). Physical QPU time is a scarce resource allocated via a strict quota system.

![OriginQC Cloud platform — Wukong 180 chip](../assets/Origin_Quantum.png)

---

## 3. The Triple-Tier Fallback Pattern (High Availability)

Since this system is designed for real-time discrete control loops (Industrial Control Systems / SCADA), we implemented a pattern of extreme reliability. When external hardware fails or rejects the connection, the system does not crash; instead, it undergoes **graceful degradation**:

| Tier | Environment | Description | Status in our Run |
|------|-------------|-------------|-------------------|
| **Tier 1 (QPU)** | `origin_wukong` | Attempt to capture the real 72-qubit superconducting processor to get physical noise data. | ❌ *Rejected by Cloud (Maintenance/Quota)* |
| **Tier 2 (Cloud HPC)** | `full_amplitude` | Redirect to the cloud supercomputer simulator. Requires C++ interface (Pybind11) reconfiguration to drop `measure` gates. | ❌ *Rejected (Quota Limits)* |
| **Tier 3 (Local CPU)** | `CPUQVM` | Instant interception of the task by the local quantum simulator running on the controller's CPU. | ✅ **Successfully Executed** |

---

## 📊 Fallback Implementation Code

This architectural pattern guarantees that a control signal will be generated even if the connection to the quantum data centers is lost.

```python
def run_qaoa_with_fallback(Q, api_key, shots=256, chip_name="origin_wukong"):
    # ... [Tier 1: REAL_CHIP initiation attempt] ...
    try:
        raw_result = backend.run([prog], shots, options)
        # Process QPU results
    except Exception as e:
        print(f"[❌ QPU Error: {e}]")
        print("🔄 Switching to Cloud Full-Amplitude Simulator...")
        return run_qaoa_cloud_simulator(Q, api_key, shots)

def run_qaoa_cloud_simulator(Q, api_key, shots=256):
    # ... [Tier 2: HPC Cloud attempt without measure() gates] ...
    try:
        raw_result = backend.run(prog, qubits_to_calculate)
        # Map probabilities back to shots
    except Exception as e:
        print(f"[❌ Cloud Simulator Error: {e}]")
        print("🔄 Switching to Local Simulator...")
        return run_qaoa_local_simulator(Q, shots)
        
def run_qaoa_local_simulator(Q, shots=256):
    # ... [Tier 3: Local execution guaranteed to succeed] ...
    machine.run(prog, shots)
    return machine.result().get_counts()
```

---

## 🚀 Projection for a Physical NISQ Device (Theory)

If the task were successfully routed to the real Wukong chip, the probability distribution would become "flatter" compared to the simulator due to the open nature of the quantum system. We would observe:

1. **Decoherence (T1/T2 relaxation):** Qubits losing their energy states during the execution of RZ and CNOT gates.
2. **Gate Infidelity:** Noise in two-qubit operations (especially in the compiler's extra SWAP gates), distorting the penalty interactions $J_{ij}$.
3. **Readout Error:** Errors during measurement (e.g., a qubit in state $|1\rangle$ collapsing and being read as $|0\rangle$).

**Conclusion:**
The fallback architecture ensures that quantum algorithms can be safely integrated into mission-critical tech systems today, acting as a bridge until Fault-Tolerant Quantum Computers (FTQC) become widely available.