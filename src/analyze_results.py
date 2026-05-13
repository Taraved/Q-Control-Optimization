import json
import numpy as np
import matplotlib.pyplot as plt
import os
from itertools import product

def decode_bitstring(bitstr, n_vars=4):
    return[int(b) for b in bitstr.zfill(n_vars)]

def check_constraints(solution, target_sum=2, conflict_indices=None):
    if sum(solution) != target_sum:
        return False, f"Сумма {sum(solution)} != {target_sum}"
    
    if conflict_indices:
        i, j = conflict_indices
        if solution[i] and solution[j]:
            return False, f"Конфликт: элементы {i} и {j} оба активны"
    
    return True, "OK"

def compute_H(solution, Q, offset):
    x = np.array(solution)
    return (x @ Q @ x) + offset

def analyze_results():
    # Читаем именно файл, который отдает облачный скрипт
    with open('results/quantum_histogram_cloud.json') as f:
        hist = json.load(f)
    
    Q = np.load('data/Q_matrix.npy')
    n_vars = Q.shape[0]
    
    with open('data/qubo_offset.json', 'r') as f:
        offset = json.load(f)['offset']
    
    # Сортируем все состояния
    sorted_hist = sorted(hist.items(), key=lambda x: -x[1])
    top_plot = sorted_hist[:16] # Для 4 переменных состояний максимум 16
    
    print("=" * 60)
    print("📊 АНАЛИЗ КВАНТОВЫХ РЕЗУЛЬТАТОВ")
    print("=" * 60)
    print(f"\nВсего уникальных состояний: {len(hist)}")
    total_shots = sum(hist.values())
    print(f"Всего измерений: {total_shots}")
    
    print("\nРаспределение (отсортировано по частоте):")
    print("-" * 65)
    print(f"{'Состояние':<10} {'x':<12} {'H':<8} {'Шоты':<6} {'Допустимо?':<12}")
    print("-" * 65)
    
    valid_shots = 0
    valid_quantum_states =[]
    
    for bits, count in sorted_hist:
        x = decode_bitstring(bits, n_vars)
        H = compute_H(x, Q, offset)
        is_valid, msg = check_constraints(x, target_sum=2, conflict_indices=(0, 3))
        
        valid_str = "✅ Да" if is_valid else "❌ Нет"
        if is_valid:
            valid_shots += count
            valid_quantum_states.append((H, bits, count)) # Сохраняем для оценки ε
            
        print(f"{bits:<10} {str(x):<12} {H:<8.3f} {count:<6} {valid_str:<12}")
        if not is_valid and count >= (total_shots * 0.05): # Объяснение для частых ошибок
            print(f"           → {msg}")
    
    print("\n" + "=" * 60)
    print("📈 Статистика по допустимым состояниям")
    print("=" * 60)
    print(f"Допустимых шотов: {valid_shots} / {total_shots} ({100*valid_shots/total_shots:.1f}%)")
    
    # --- Классический оптимум ---
    best_H = np.inf
    best_states = []
    for bits in product([0, 1], repeat=n_vars):
        x = list(bits)
        is_valid, _ = check_constraints(x, target_sum=2, conflict_indices=(0, 3))
        if is_valid:
            H_val = compute_H(x, Q, offset)
            if H_val < best_H:
                best_H = H_val
                best_states = [bits]
            elif H_val == best_H:
                best_states.append(bits)
                
    print("\n" + "=" * 60)
    print("⚖️ СРАВНЕНИЕ С КЛАССИЧЕСКИМ ОПТИМУМОМ")
    print("=" * 60)
    print(f"Классический оптимум: H = {best_H:.3f}")
    optimal_strings =[''.join(map(str, s)) for s in best_states]
    print(f"Оптимальные состояния: {optimal_strings}")
    
    best_quantum_H = None
    epsilon = None
    
    if valid_quantum_states:
        # Ищем ЛУЧШЕЕ среди ВАЛИДНЫХ
        valid_quantum_states.sort(key=lambda x: x[0])
        best_quantum_H = valid_quantum_states[0][0]
        
        # Модуль отклонения, чтобы избежать -5000%
        epsilon = abs((best_quantum_H - best_H) / best_H) * 100 if best_H != 0 else 0
        
        print(f"\nЛучшее ВАЛИДНОЕ квантовое решение: H = {best_quantum_H:.3f} (Состояние: {valid_quantum_states[0][1]})")
        print(f"Отклонение от оптимума (ε): {epsilon:.1f}%")
        
        if epsilon <= 10:
            print("✅ Критерий гипотезы ВЫПОЛНЕН (ε ≤ 10%)")
        else:
            print("⚠️ Критерий гипотезы НЕ ВЫПОЛНЕН (ε > 10%)")
    else:
        print("\n❌ Квантовый алгоритм не нашел НИ ОДНОГО допустимого (валидного) решения!")
    
    # --- График ---
    print("\n" + "=" * 60)
    print("📊 Создание визуализации")
    print("=" * 60)
    
    plt.figure(figsize=(10, 5))
    states = [bits for bits, _ in top_plot]
    counts =[count for _, count in top_plot]
    colors =['green' if check_constraints(decode_bitstring(s, n_vars), 2, (0, 3))[0] 
              else 'red' for s in states]
    
    bars = plt.bar(range(len(states)), counts, color=colors)
    plt.xticks(range(len(states)), states, rotation=45, fontsize=10)
    plt.ylabel('Частота (shots)', fontsize=11)
    plt.xlabel('Состояние', fontsize=11)
    plt.title('Распределение квантовых состояний\n(зелёный = допустимо, красный = нарушает ограничения)', fontsize=11)
    plt.tight_layout()
    
    os.makedirs('results', exist_ok=True)
    plt.savefig('results/comparison_plot.png', dpi=150)
    print("✅ График сохранён в results/comparison_plot.png")
    
    # Метаданные
    stats = {
        "total_shots": int(total_shots),
        "valid_shots": int(valid_shots),
        "valid_percentage": round(100 * valid_shots / total_shots, 2),
        "classical_optimum_H": round(best_H, 3),
        "quantum_best_H": round(best_quantum_H, 3) if best_quantum_H is not None else None,
        "epsilon_percent": round(epsilon, 2) if epsilon is not None else None,
        "hypothesis_met": bool(epsilon <= 10) if epsilon is not None else False,
        "optimal_states": optimal_strings
    }
    
    with open('results/run_metadata.json', 'w') as f:
        json.dump(stats, f, indent=2)
    print("✅ Метаданные сохранены в results/run_metadata.json")
    
    return stats

if __name__ == '__main__':
    analyze_results()