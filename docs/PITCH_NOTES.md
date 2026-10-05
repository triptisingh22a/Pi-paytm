# Pitch notes

**Pi: test a shelf decision before spending the next rupee.**

Paytm POS can provide a merchant's bill-level purchases and inventory inputs. Pi is a decision layer: a digital twin with grounded calculations, peer evidence and explicit assumptions. Voice makes asking easy; simulation is the proposition.

Two demos establish the flow. The overview reconciles sales and stock to timestamped bills. The assortment twin answers “what if I replace this unpopular product?” and “which replacement should I trial?” It normalizes item identity, finds same-type category peers, rejects insufficient exposure, shrinks their demand evidence, and recomputes substitution under shared customer-flow assumptions. Restaurant trials consume shared recipe ingredients.

Show a number and its receipt together. Show a negative candidate and sensitivity that changes the answer. Do not claim all customer visitors or causal uplift from purchase-only POS. A controlled small trial closes that evidence gap. State supplied costs and recipe data explicitly; peers do not supply arbitrary merchant characteristics.

For scale: canonical catalogue and incremental mapping → daily merchant/product facts → merchant-category ANN retrieval → missingness-aware eligibility and exact rerank → weighted hierarchical demand → narrow assortment trial. The demo implements curated identity, exact cohort rerank, conjugate transfer and a conditional choice twin. A production ANN index, calibrated matching, controlled trials, tenant auth, medical/product rules and live POS/OCR remain subsequent work.

The seven synthetic verticals are hypermarket, restaurant, apparel, kirana, pharmacy, bakery and electronics. No market-size statistic, real Paytm integration, realized merchant uplift or lending offer is claimed.
