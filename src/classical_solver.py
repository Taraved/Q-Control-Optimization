import numpy as np
import json
import os
from itertools import product

def solve_bruteforce(Q, offset, config=None):
    n = len(Q)
    
    if config is None:
        target_sum = 2
        conflict_indices = (0, 3)
    else:
        # Пытаемся достать target_sum из конфига
        target_sum = 2
        if config.get('equality_constraints'):
            target_sum = config['equality_constraints'][0].get('target_sum', 2)
            
        conflict_indices = None
        for ic in config.get('inequality_constraints',[]):
            if ic.get('type') == 'mutual_exclusion':
                conflict_indices = tuple(ic['indices'])
                break
        if conflict_indices is None:
            conflict_indices = (0, 3)
    
    best_val = np.inf
    best_sol = None
    
    for bits in product([0, 1], repeat=n):
        x = np.array(bits)
        
        if sum(bits) != target_sum:
            continue
        
        i, j = conflict_indices
        if bits[i] == 1 and bits[j] == 1:
            continue
        
        val = (x @ Q @ x) + offset  # Учитываем математический offset
        if val < best_val:
            best_val, best_sol = val, list(bits)
    
    return np.array(best_sol) if best_sol is not None else None, best_val

def load_config_and_solve():
    with open('data/config.json', 'r') as f:
        config = json.load(f)
        
    with open('data/qubo_offset.json', 'r') as f:
        offset = json.load(f)['offset']
    
    Q = np.load('data/Q_matrix.npy')
    sol, val = solve_bruteforce(Q, offset, config)
    
    print(f"🏆 Классический оптимум (валидные): {sol} (H={val:.3f})")
    
    # Без фильтрации для сравнения ландшафта
    best_val_all = np.inf
    best_sol_all = None
    for bits in product([0, 1], repeat=len(Q)):
        x = np.array(bits)
        val = (x @ Q @ x) + offset
        if val < best_val_all:
            best_val_all = val
            best_sol_all = bits
    
    print(f"   Без фильтрации: {best_sol_all} (H={best_val_all:.3f})")
    
    os.makedirs('results', exist_ok=True)
    np.save('results/classical_solution.npy', sol)
    
    return sol, val

if __name__ == '__main__':
    load_config_and_solve()