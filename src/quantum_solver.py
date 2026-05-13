#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import sys
import json
import os
import numpy as np

def run_qaoa_on_real_chip(Q, api_key, shots=256, chip_name="origin_wukong"):
    """
    1-й УРОВЕНЬ: Запуск QAOA на реальном квантовом чипе (QCloudService)
    """
    t_start = time.time()
    machine_type = f"REAL_CHIP ({chip_name})"
    print(f"[⏱️ {time.time()-t_start:.1f}s] Подключение к OriginQC Cloud (Поиск реального QPU)...")
    
    try:
        from pyqpanda3.qcloud import QCloudService, QCloudOptions
        from pyqpanda3.core import QProg, H, CNOT, RZ, RX, measure
        
        service = QCloudService(api_key)
        backend = service.backend(chip_name)
        
        chip_info = backend.chip_info()
        print(f"[💻] Целевой чип: {chip_name} (Готовность подтверждена)")
        
        n = len(Q)
        prog = QProg()
        gamma, beta = 0.5, 0.3
        
        for i in range(n): prog << H(i)
        
        h = np.zeros(n)
        J = np.zeros((n, n))
        for i in range(n):
            h[i] = -Q[i, i] / 2.0
            for j in range(n):
                if i != j: h[i] -= (Q[i, j] + Q[j, i]) / 4.0
        for i in range(n):
            for j in range(i + 1, n):
                J[i, j] = (Q[i, j] + Q[j, i]) / 4.0
                
        for i in range(n):
            if abs(h[i]) > 1e-5: prog << RZ(i, 2 * gamma * h[i])
        for i in range(n):
            for j in range(i + 1, n):
                if abs(J[i, j]) > 1e-5:
                    prog << CNOT(i, j)
                    prog << RZ(j, 2 * gamma * J[i, j])
                    prog << CNOT(i, j)
                    
        for i in range(n): prog << RX(i, 2 * beta)
        
        # Для реального чипа измерения ОБЯЗАТЕЛЬНЫ
        for i in range(n): prog << measure(i, i)
        
        print(f"[🚀 {time.time()-t_start:.1f}s] Отправка пакетной задачи на QPU...")
        options = QCloudOptions()
        
        # Batch-задача [prog] для реального чипа
        raw_result = backend.run([prog], shots, options)
        run_result = raw_result[0] if isinstance(raw_result, list) else raw_result
        
        if hasattr(run_result, 'get_counts'): histogram = run_result.get_counts()
        elif isinstance(run_result, dict): histogram = run_result
        else:
            try: histogram = dict(run_result)
            except Exception: histogram = run_result
                
        t_end = time.time()
        print(f"[✅ {t_end-t_start:.1f}s] Результаты с реального чипа получены!")
        return histogram, machine_type, shots, round(t_end - t_start, 2)
        
    except Exception as e:
        print(f"[❌ Ошибка чипа: {e}]")
        print("🔄 Переключаюсь на облачный Full-Amplitude симулятор...")
        return run_qaoa_cloud_simulator(Q, api_key, shots)


def run_qaoa_cloud_simulator(Q, api_key, shots=256):
    """
    2-й УРОВЕНЬ: Облачный суперкомпьютер Full Amplitude (Fallback 1)
    """
    t_start = time.time()
    machine_type = "CLOUD_SIMULATOR (full_amplitude)"
    print(f"\n[💻 {time.time()-t_start:.1f}s] Запуск на облачном суперкомпьютере...")
    
    try:
        from pyqpanda3.qcloud import QCloudService
        from pyqpanda3.core import QProg, H, CNOT, RZ, RX
        
        service = QCloudService(api_key)
        backend = service.backend("full_amplitude")
        
        n = len(Q)
        prog = QProg()
        gamma, beta = 0.5, 0.3
        
        for i in range(n): prog << H(i)
        
        h = np.zeros(n)
        J = np.zeros((n, n))
        for i in range(n):
            h[i] = -Q[i, i] / 2.0
            for j in range(n):
                if i != j: h[i] -= (Q[i, j] + Q[j, i]) / 4.0
        for i in range(n):
            for j in range(i + 1, n):
                J[i, j] = (Q[i, j] + Q[j, i]) / 4.0
                
        for i in range(n):
            if abs(h[i]) > 1e-5: prog << RZ(i, 2 * gamma * h[i])
        for i in range(n):
            for j in range(i + 1, n):
                if abs(J[i, j]) > 1e-5:
                    prog << CNOT(i, j)
                    prog << RZ(j, 2 * gamma * J[i, j])
                    prog << CNOT(i, j)
                    
        for i in range(n): prog << RX(i, 2 * beta)
        
        # ВНИМАНИЕ: Для Full Amplitude ЗАПРЕЩЕНО добавлять measure()!
        
        print(f"[🚀 {time.time()-t_start:.1f}s] Отправка математической задачи в облако...")
        
        # Исправление C++ Pybind11: передаем список кубитов, амплитуды которых хотим узнать
        qubits_to_calculate = list(range(n))
        raw_result = backend.run(prog, qubits_to_calculate)
        
        # Извлекаем результат (в разных версиях API может возвращаться по-разному)
        if hasattr(raw_result, 'get_counts'): prob_dict = raw_result.get_counts()
        elif hasattr(raw_result, 'get_probabilities'): prob_dict = raw_result.get_probabilities()
        elif isinstance(raw_result, dict): prob_dict = raw_result
        else: prob_dict = dict(raw_result)
            
        # Cloud simulator возвращает ВЕРОЯТНОСТИ (0.0 - 1.0) или сразу шоты
        histogram = {}
        for state, val in prob_dict.items():
            if isinstance(val, float) and val <= 1.0:
                count = int(round(val * shots))
                if count > 0: histogram[state] = count
            else:
                histogram[state] = int(val) # Если вдруг вернул шоты
                
        # Корректировка суммы из-за математического округления вероятностей
        total = sum(histogram.values())
        if total > 0 and total != shots:
            best_state = max(histogram, key=histogram.get)
            histogram[best_state] += (shots - total)
            
        t_end = time.time()
        print(f"[✅ {t_end-t_start:.1f}s] Результаты с облачного HPC получены!")
        return histogram, machine_type, shots, round(t_end - t_start, 2)
        
    except Exception as e:
        print(f"[❌ Ошибка облачного симулятора: {e}]")
        print("🔄 Переключаюсь на локальный симулятор...")
        
        return run_qaoa_local_simulator(Q, shots)


def run_qaoa_local_simulator(Q, shots=256):
    """
    3-й УРОВЕНЬ: Локальный симулятор (Fallback 2, если всё облако недоступно/нет интернета)
    """
    from pyqpanda3.core import CPUQVM, QProg, H, CNOT, RZ, RX, measure
    
    t_start = time.time()
    machine_type = "CPU_SIMULATOR (Local)"
    print(f"\n[💻 {time.time()-t_start:.1f}s] Запуск на локальном симуляторе...")
    
    n = len(Q)
    machine = CPUQVM()
    prog = QProg()
    gamma, beta = 0.5, 0.3
    
    for i in range(n): prog << H(i)
    
    h = np.zeros(n)
    J = np.zeros((n, n))
    for i in range(n):
        h[i] = -Q[i, i] / 2.0
        for j in range(n):
            if i != j: h[i] -= (Q[i, j] + Q[j, i]) / 4.0
    for i in range(n):
        for j in range(i + 1, n):
            J[i, j] = (Q[i, j] + Q[j, i]) / 4.0
            
    for i in range(n):
        if abs(h[i]) > 1e-5: prog << RZ(i, 2 * gamma * h[i])
    for i in range(n):
        for j in range(i + 1, n):
            if abs(J[i, j]) > 1e-5:
                prog << CNOT(i, j)
                prog << RZ(j, 2 * gamma * J[i, j])
                prog << CNOT(i, j)
                
    for i in range(n): prog << RX(i, 2 * beta)
    for i in range(n): prog << measure(i, i)
    
    machine.run(prog, shots)
    result = machine.result().get_counts()
    
    t_end = time.time()
    print(f"[✅ {t_end-t_start:.1f}s] Готово! Режим: {machine_type}")
    return result, machine_type, shots, round(t_end - t_start, 2)


if __name__ == "__main__":
    Q_PATH = "data/Q_matrix.npy"
    OUT_PATH = "results/quantum_histogram_cloud.json"
    LOG_PATH = "results/run_metadata.json"
    
    os.makedirs('results', exist_ok=True)
    
    if not os.path.exists(Q_PATH):
        print("❌ Не найдена Q_matrix.npy. Сначала запустите qubo_builder.py")
        sys.exit(1)
    
    # === API КЛЮЧ ===
    API_KEY = "YOUR_API_KEY"
    
    Q = np.load(Q_PATH)
    print(f"\n📊 Загружена QUBO матрица размером {len(Q)}x{len(Q)}")
    
    # Запуск логики 3-уровневого резервирования
    histogram, mode, shots_used, time_spent = run_qaoa_on_real_chip(
        Q, 
        api_key=API_KEY,
        shots=256,
        chip_name="origin_wukong" 
    )
    
    # Сохранение результатов
    with open(OUT_PATH, "w") as f:
        json.dump(histogram, f, indent=2)
    
    meta = {
        "machine_type": mode,
        "shots": shots_used,
        "time_sec": time_spent,
        "n_vars": len(Q),
        "status": "success"
    }
    with open(LOG_PATH, "w") as f:
        json.dump(meta, f, indent=2)
    
    print(f"\n📁 Результаты сохранены: {OUT_PATH}")
    print(f"📊 Метаданные: {LOG_PATH}")
    
    # Быстрый вывод топ-5
    sorted_hist = sorted(histogram.items(), key=lambda x: -x[1])
    print(f"\n🏆 Топ-5 состояний с квантовой среды:")
    for bits, count in sorted_hist[:5]:
        percentage = 100 * count / sum(histogram.values())
        print(f"   {bits}: {count} shots ({percentage:.1f}%)")