import numpy as np
from engine.receipts import Receipt, insufficient


def peers(shop, population, k=10):
    if k < 10:
        raise ValueError("Privacy minimum group size is 10")
    group = [r for r in population if r["kind"] == shop["kind"]]
    if len(group) < k:
        return insufficient(shop["data_tier"], "PEER_GROUP_TOO_SMALL")
    features = np.array([r["features"] for r in group])
    target = np.array([100, 60, shop["repeat_rate"], 0.2])
    scale = np.maximum(features.std(axis=0), 0.01)
    idx = np.argsort(np.linalg.norm((features - target) / scale, axis=1))[:k]
    mean = float(np.mean([group[i]["daily_units"] for i in idx]))
    return Receipt(
        inputs={"shop_type": shop["kind"], "minimum_group_size": k},
        formula_text="k nearest within-type normalized feature vectors; aggregate mean",
        assumptions=["No individual rows returned; k-anonymity threshold is not differential privacy"],
        output={
            "group_size": k,
            "cold_start_daily_units": round(mean, 2),
            "insight": "Use a peer prior only until this shop has enough uncensored history",
        },
        data_tier=shop["data_tier"],
    )
