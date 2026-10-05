# Mathematical specification

All outputs are model-based simulated decisions; currency INR, horizons days. Receipts contain inputs, assumptions, formula, calculation steps, outputs, quantiles, tier and quality flags. No LLM participates in calculation.

## Demand
Exclude observations with available stock exhausted: observed sales Y=min(D,stock) do not identify D. For uncensored data fit log(Y+0.5)=Xb with ridge penalty λ=1 (intercept unpenalized); X includes weekday dummies, payday and configured festival. Set μ=max(0.1,exp(Xb)-0.5). Predict Poisson quantiles. Hold out the last 28 days, train on earlier uncensored rows and report mean pinball loss Lτ(y,q)=(τ-1[y<q])(y-q) across τ=.1,.5,.9. This is an approximate count regression, not an exact censored likelihood. Too little history returns a flagged peer prior.

## Allocation
For SKU i, candidate integer quantity q, paired demand scenarios D, existing usable stock s and selling window w=max(0,min(H-lead,shelf)): incremental gross contribution
V_i(q)=p E[min(D,s+q)-min(D,s)] - c q + c E[(s+q-D)+-(s-D)+] 1[shelf>H-lead].
The last term values unexpired terminal inventory at cost; perishable expired inventory has zero salvage. No extra stock-out penalty is added: missed sales already enter contribution. Lead-time approximation uses demand over the post-arrival window and existing stock remaining at arrival.
Choose one q per SKU maximizing ΣV_i(q), subject to Σc_i q_i ≤ B. MILP binary selection gives exact optimization over enumerated candidates, subject to solver tolerance. Candidate caps are documented; this is not an unrestricted optimality claim. Shadow value is the finite difference V(B+1000)-V(B), not a differentiable dual multiplier.

## Promotion
Matched counterfactual baseline b_t from nonpromo same-weekday/event/payday controls. Uplift u=mean(Ypromo/bpromo)-1; pull-forward f=max(0,1-mean(Ypost/bpost)). Bootstrap blocks of complete promotion episodes, preserving event dependence. For baseline units Q, price p, cost c, discount d, horizon-compatible lost future units F: Δπ=Q[(1+u)((1-d)p-c)-(p-c)]-F(p-c). Discount applies to baseline sales too. DO if p10>0; DON'T if p90<0; otherwise INSUFFICIENT_DATA. Missing costs or A always insufficient. At p=100,u=.8,d=.1,F=.1Q: margin 35% gives Δπ/Q=1.8×25−35−3.5=6.5; margin 7% gives 1.8×(−3)−7−.7=−13.1. Results use estimated values, not these constants.

## Cash
C_t=C_0+Σ_{j≤t}settlements_j-Σ_{j≤t}dues_j. Probability of any gap is empirical mean 1[min_t C_t<0]. Quantiles are pointwise, not simultaneous path coverage. Safe commitment=max(0,quantile_r(min_{t=0..H}C_t)); include C0 so pending receipts cannot finance today's spend. With continuous cash distributions, spending this quantile leaves estimated breach probability r; finite-path uncertainty remains. Earliest likely gap is first day marginal gap probability≥configured threshold, otherwise null.

## Twin simulation
Clone state; use common random numbers for action and baseline. Daily demand Poisson; FIFO expiry; lead-time arrivals; revenue settles after lag. Profit is revenue minus cost of sold inventory, expiry write-offs and assumed borrowing cost. Purchases change cash and stock, not expense immediately. Δprofit=profit_action-profit_baseline. Terminal inventory remains an asset. Approve creates a pending plan; advance executes it once and saves outcome/memory transactionally. Repeated advances after execution do not execute the order twice. Counter counts simulated Δprofit only. Predictions and simulated realized outcomes are separately labeled.

## Ranker and peers
Compare Δprofit over H=7 days and divide by cash committed for positive-cost actions. Show P(Δprofit<0). Holding cash is a safeguard. Peer features are normalized within shop type, nearest k≥10 neighbours; only aggregate means and count returned. This is a minimum-group-size rule, not differential privacy or a reidentification guarantee.

## Loan illustration
Eligible only if B and gap-risk>threshold and restock Δprofit>amount×assumed cost fraction. Amount=min(cash gap, identified order shortfall). No real eligibility, loan decision or sanction estimate.

## Number guard
Normalize Unicode digits, grouping separators, currency, percentages and K/lakh multipliers; compare all numerical tokens to authorized numeric fields including receipt inputs/steps/outputs. Preserve negative signs. Dates compared as dates. Unmatched tokens reject; failed explanation falls back to engine template. Numeric membership alone does not establish correct semantics; templates bind labels to receipt fields. Default replies use templates; an optional schema-verified Sarvam explanation adapter applies this guard, retries once, then falls back. Spelled-out English numeric claims are conservatively rejected. Arbitrary prose semantics and all spelled-out multilingual numbers are not formally verified; cached templates are the reliable demo path.

## Customer cohorts
Synthetic cohorts evolve independently of sales: new→repeat Binomial(n,.15); repeat→at-risk Binomial(n,.015); at-risk→inactive Binomial(n,.04), remaining at-risk→repeat Binomial(n,.02); inactive→repeat Binomial(n,.005); new acquisition Poisson(2) daily. Rates are planted assumptions. Transitions conserve existing customers and acquisitions increase total. No identities are stored, and this cohort model does not feed demand or assert causal response. Tier A does not expose customer history.

## Billing overview, peer transfer and replacement twin

Implemented in `api/billing/services.py`; evidence comes from `billing.sqlite3`, not the legacy payment fixture.

For window W, realized revenue is `R_W = Σ_(bill lines in W) q_l p_l`; gross contribution is `C_W = Σ q_l(p_l − c_l)`. Chart and product totals reconcile to the same line-level revenue. Inventory coverage is `on_hand / (latest_7_day_units / 7)`; absent velocity returns no coverage, not infinity. Trend is `(recent_units/recent_exposure)/(prior_units/prior_exposure) − 1`; missing denominator returns no comparable trend. Trends always compare the latest two weeks while main totals obey the selected 1/7/30-day window.

For same-type donor d, feature `z_d` is its normalized non-candidate category-unit mix; the requested SKU and Y are omitted. Distance is `||z_d − z_target||₂ + |z_d,f − z_target,f|`. Among eligible donors choose the closest 30 and normalize `w_d ∝ exp(−8 distance_d)`. ESS is `1/Σ w_d²`; it is descriptive evidence concentration, not a privacy guarantee. Cohort count below 10 suppresses inference.

Peer rate `r_peer = Σ w_d units_d / Σ w_d availability_exposure_d`. Let `E0 = min(500, Σ w_d exposure_d)` and target latest-28-day `(n,E)`. Posterior `r ~ Gamma(shape=0.5 + E0*r_peer+n, rate=1+E0+E)`. Report quantiles of this rate; for a future known exposure H, the predictive count is Negative Binomial with shape α and probability β/(β+H). Unit counts may exceed one per bill; this is a Poisson rate model, not Bernoulli penetration.

For each simulation path draw one rate per compatible option. With baseline family sum `s = clip(Σ existing rates, 0.01,0.8)`, use `u_i = r_i/max(1-s,0.2)`. This calibration is assumed, not estimated preference identification. For available set A and outside weight o, `P_i = u_i/(o+Σ_(j in A) u_j)`, and `P_outside = o/(o+Σ_A u_j)`. One uniform draw shared by both branches chooses an item or outside. Baseline offers Y and existing family items; action removes Y and offers X. Stocks and ingredient availability dynamically change A. Thus X sales are never added independently to unchanged incumbent sales.

Fixed opportunities `H = round(latest_30_day_completed_bills / 30 * horizon)` apply in both branches. Shared uniforms and rates reduce paired-delta variance. Seed 92341 draws posteriors; seed 8421 draws choices. Default 1024 paths. Current and action stock/ingredient caps are recorded in the receipt. Restaurant `ingredient_k(t+1) = ingredient_k(t) − recipe_ik` for each sold dish; sale is feasible only if every requirement is available.

Per path `ΔR = Σ_i (q_i,action−q_i,base)*price_i`. `ΔC = Σ_i Δq_i*(price_i−cost_i)`. Purchase cash is `Q_X*cost_X`; incremental cash after that purchase is `ΔR − purchase_cash`. Unsold X at supplied cost is `(Q_X−q_X,action)*cost_X`. Existing stock is a sunk starting asset; removing Y does not generate an assumed salvage receipt. Future replenishment, overhead, taxation and terminal sale are excluded. Display mean ΔR/ΔC, paired P10/P50/P90 and `Pr(ΔR<0)`. Outside factors 0.5/1/2 share draws but represent different unidentifiable assumptions.

Candidates must be supplied catalogue products in the same family, with known prices/costs and affordable purchase quantity; recipes need known ingredient allocations. Ranking maximizes P10 incremental revenue under the default model. Negative conservative values favor holding rather than promising a winner; sensitivity can change the sign even for a positive default trial.

See `eval/peer_transfer.json`: merchant-held-out, candidate-hidden, future-week evaluation compares the weighted method with a type-item mean. These scores apply only to the simulated generator; they do not validate the causal counterfactual.

### Primary method references

- GS1 declared net content identity: https://www.gs1.org/1/gtinrules/en/rule/266/declared-net-content
- Exposure offsets: https://www.statsmodels.org/stable/generated/statsmodels.genmod.generalized_linear_model.GLM.html
- Hierarchical and multi-logit foundations: https://mc-stan.org/docs/stan-users-guide/regression.html
- Unobserved stockouts/arrival-identification problem: https://arxiv.org/abs/2003.02313

The code uses its stated conjugate transfer and conditional choice approximation, not these sources' full estimation algorithms.


## Repricing (own item, regular price)

Implemented in `api/pricing/`. Money is integer paise. Gross contribution = units x (price - landed unit cost - other variable cost); it is not net profit.

**Break-even** (exact, no demand assumption). With current margin `m0`, new margin `m1 = p1 - c - v`, baseline expected units `Q0`: baseline contribution `Q0*m0`; tie volume `Q0*m0/m1`; required integer units `floor(tie)+1` (strictly beat). Required uplift is `tie/Q0 - 1` (expected) and `required/Q0 - 1` (integer). Example: cost 100, price 120, 130 units, new price 115 -> 2,600 baseline; 173.33 units tie (+33.33%); 174 needed (+33.85%). `m1 <= 0` returns "no break-even", never a divided-by-zero quantity. The new price applies to every unit sold, so revenue can rise while contribution falls.

**Evidence before estimation** (`evidence.py`). Distinct price levels, price-change episodes, randomized blocks, stockout share and whether the proposed price lies inside the observed range. States: randomized price test (real or synthetic), observational scenario, insufficient evidence. One price level, or fewer than 3 changes, is insufficient. Randomized needs >= 8 blocks and >= 3 levels. Many days at one price are one assignment. Peers never supply price sensitivity for the item being priced.

**Demand model** (`model.py`). `D_t ~ NegBin(mean mu_t, alpha)`, `log mu_t = b0 + b_p log(p_t/p_ref) + b_promo promo_t + weekday_t`, so `E[D(p)] = baseline (p/p_ref)^(-eta)`, `eta = -b_p`. Stockout days enter as censored observations, `P(D >= units)`, not as ordinary sales. Ridge on promo and weekday terms; the price coefficient has a normal prior, centred on the pooled estimate of comparable items that have randomized tests (partial pooling) or nearly flat when none exist. Parameter uncertainty is a Laplace approximation with a week-clustered robust (sandwich) covariance, because unrecorded demand shocks last about a week. For observational history the price-coefficient standard deviation is multiplied by 4 (a product choice) and the result is capped at "trial recommended" or "likely reduces". No trend or seasonality beyond weekday in v1.

**Simulation** (`simulate.py`). 400 parameter draws x 8 demand draws x horizon days. Each candidate price shares the same draws, so differences are paired. Stock is walked forward day by day with opening stock, listed deliveries and an optional order-up-to rule, identical under every price; fulfilled = min(demand, stock), so `E[min(D, S)]` is taken over paths. Reported: expected units, contribution change, outcome intervals (P10-P90 over all paths: where one future could land) and mean intervals (P10-P90 over parameter draws of the path-average: uncertainty about the average), probability lower, stockout probability, units lost to stock. Seeds are fixed (92341).

**Decision labels** (`recommend.py`). Thresholds are product choices, printed in every receipt: "likely improves" needs a randomized test, a price inside the tested range, P(higher) >= 0.80 and P10 loss within 5% of baseline contribution; "likely reduces" needs P(lower) >= 0.80 (0.90 for observational); otherwise "trial recommended"; no price evidence gives "insufficient evidence" and no forecast. Candidate grids always include the current price, drop prices under 5% margin or above a supplied maximum, and cap at 15 prices.

**Assumption-based scenarios.** With no price variation, a merchant may supply a sensitivity. Every dependent output is labelled an assumption; it is never stored as learned and the decision stays "insufficient evidence". The `assumed_eta` range is 0.1 to 8.

**Not modelled:** category spillovers and cross-price effects, price-induced store traffic, clearance and expiry, batch-cost layers (latest landed cost is used; variation is flagged), and any effect of price on future periods (pull-forward is covered by the experiment plan's follow-up period).

References: Oracle Retail Offer Optimization (offer-opt implementation guide); Bray, Sanders and Stamatopoulos, observational versus experimental price elasticities (MSI); Conlon and Mortimer, demand under incomplete product availability (NBER w14315).