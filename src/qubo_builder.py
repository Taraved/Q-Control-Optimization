import numpy as np
import json
import os

def load_config(path='data/config.json'):
    with open(path, 'r') as f:
        return json.load(f)

def build_qubo_matrix(cfg):
    n = cfg['n_vars']
    Q = np.zeros((n, n))
    offset = 0.0  # Константа штрафа выносится отдельно!
    
    # 1. Целевая функция (минимизация затрат)
    for i in range(n):
        Q[i, i] += cfg['objective_costs'][i]
        
    # 2. Равенство: Σx_i = target_sum → P*(Σx_i - target)^2
    for ec in cfg['equality_constraints']:
        P = ec['penalty']
        idx = ec['indices']
        target = ec['target_sum']
        
        for i in idx:
            # Линейные члены: x_i^2 = x_i, поэтому P - 2*P*target
            Q[i, i] += P * (1 - 2 * target)
            for j in idx:
                if j > i:
                    # Кросс-члены x_i * x_j должны в сумме давать 2*P
                    Q[i, j] += P  # Было 2*P
                    Q[j, i] += P  # Было 2*P
        
        # Константа функции P * T^2
        offset += P * (target ** 2)
        
    # 3. Неравенства (взаимное исключение x_i * x_j = 0)
    for ic in cfg['inequality_constraints']:
        P = ic['penalty']
        i, j = ic['indices']
        Q[i, j] += P / 2  # Делим пополам, чтобы Q[i,j] + Q[j,i] = P
        Q[j, i] += P / 2
        
    return Q, offset

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    cfg = load_config()
    Q, offset = build_qubo_matrix(cfg)
    
    np.save('data/Q_matrix.npy', Q)
    
    # Сохраняем константу, чтобы аналитика могла выводить правильный H
    with open('data/qubo_offset.json', 'w') as f:
        json.dump({'offset': offset}, f)
        
    print("✅ QUBO-матрица сохранена в data/Q_matrix.npy")
    print(f"✅ Константа смещения H (offset={offset}) сохранена в data/qubo_offset.json")
    print("Матрица Q:\n", Q)