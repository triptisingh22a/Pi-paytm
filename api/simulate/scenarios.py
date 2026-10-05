from twin.simulator import simulate


def advance(shop, action, seed=42):
    return simulate(shop, action, horizon_days=7, n_paths=256, seed=seed)
