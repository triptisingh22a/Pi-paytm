"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { FlaskConical, Lock, ReceiptText } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Money = number; // paise
type Item = {
  id: string;
  name: string;
  price_paise: Money;
  cost_paise: Money;
  on_hand: number;
  evidence_state: string;
  evidence_label: string;
  price_levels: number;
  story?: string | null;
};
type Result = any;
export type PriceExternal = { result: Result; dataset: string; nonce: number };

const inr = (paise: number, digits = 0) =>
  `${paise < 0 ? "-" : ""}₹${(Math.abs(paise) / 100).toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
const n0 = (x: number) => Math.round(x).toLocaleString("en-IN");
const pct = (f: number, d = 1) => `${f >= 0 ? "+" : ""}${(f * 100).toFixed(d)}%`;
async function call(path: string, body?: unknown) {
  const res = await fetch("/api" + path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = json.detail;
    throw new Error(typeof d === "string" ? d : Array.isArray(d) ? "Please check the numbers you entered." : "Service unavailable");
  }
  return json;
}
const STATE_TONE: Record<string, string> = {
  synthetic_experiment: "good",
  real_experiment: "good",
  observational: "warn",
  peer_prior: "warn",
  insufficient: "neutral",
};
const DECISION_TONE: Record<string, string> = {
  likely_improves: "good",
  likely_reduces: "bad",
  trial_recommended: "warn",
  insufficient_evidence: "neutral",
  current_price: "neutral",
};

export default function PricePanel({
  mid,
  dataset,
  setDataset,
  focusSku,
  external,
  show,
}: {
  mid: string;
  dataset: "live" | "pilot";
  setDataset: (d: "live" | "pilot") => void;
  focusSku: string;
  external: PriceExternal | null;
  show: (p: any) => void;
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [sku, setSku] = useState("");
  const [price, setPrice] = useState("");
  const [horizon, setHorizon] = useState(7);
  const [extraCost, setExtraCost] = useState("");
  const [arrivalQty, setArrivalQty] = useState("");
  const [arrivalDay, setArrivalDay] = useState("1");
  const [baseline, setBaseline] = useState("");
  const [assume, setAssume] = useState(false);
  const [eta, setEta] = useState(2);
  const [candidates, setCandidates] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const item = items.find((i) => i.id === sku);
  const externalRef = useRef(external);
  externalRef.current = external;
  // An assumed sensitivity belongs to one product; never carry it silently to the next.
  useEffect(() => {
    setAssume(false);
  }, [sku, dataset]);

  const suggest = (it: Item) => String(Math.round((it.price_paise * 0.95) / 100));
  useEffect(() => {
    let live = true;
    setItems([]);
    setResult(null);
    call(`/v2/pricing/${mid}/products?dataset=${dataset}`)
      .then((r) => {
        if (!live) return;
        setItems(r.products);
        const pick = r.products.find((p: Item) => p.id === focusSku) || r.products[0];
        if (pick) {
          setSku(pick.id);
          const shown = externalRef.current?.result;
          // keep the price from an answer that came in through chat; otherwise suggest a 5% cut
          setPrice(shown?.product?.id === pick.id && shown.proposed_price_paise ? String(shown.proposed_price_paise / 100) : suggest(pick));
        }
      })
      .catch((e) => live && setError((e as Error).message));
    return () => {
      live = false;
    };
  }, [mid, dataset, focusSku]);
  useEffect(() => {
    if (!external) return;
    setResult(external.result);
    setError("");
    setSaved("");
    if (external.result?.product?.id) setSku(external.result.product.id);
    if (external.result?.proposed_price_paise) setPrice(String(external.result.proposed_price_paise / 100));
  }, [external]);

  const body = () => {
    const proposed = Number(price);
    if (!sku || !Number.isFinite(proposed) || proposed <= 0) throw new Error("Enter a proposed price in rupees.");
    const out: Record<string, unknown> = { product: sku, dataset, horizon, proposed_price: proposed };
    if (extraCost) out.extra_cost = Number(extraCost);
    if (baseline) out.baseline_units = Number(baseline);
    if (arrivalQty) out.receipts = [{ day: Number(arrivalDay), qty: Number(arrivalQty) }];
    if (assume && item?.evidence_state === "insufficient") out.assumed_eta = eta;
    return out;
  };
  const run = async (kind: "reprice" | "recommend") => {
    setBusy(true);
    setError("");
    setSaved("");
    try {
      const b: Record<string, unknown> = body();
      if (kind === "recommend") {
        delete b.proposed_price;
        delete b.baseline_units;
        if (candidates.trim()) {
          const list = candidates.split(/[,\s]+/).filter(Boolean).map(Number);
          if (list.some((x) => !Number.isFinite(x) || x <= 0)) throw new Error("Candidate prices must be numbers in rupees, like 110, 115, 120.");
          b.candidates = list;
        }
      }
      setResult(await call(`/v2/pricing/${mid}/${kind}`, b));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = useCallback(
    async (kind: "scenario" | "experiment_plan") => {
      try {
        const b = { ...body(), kind };
        const r = await call(`/v2/pricing/${mid}/scenarios`, b);
        setSaved(`Saved locally (#${r.id}). No price was changed anywhere.`);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [mid, sku, dataset, horizon, price, extraCost, baseline, arrivalQty, arrivalDay, assume, eta, item],
  );
  const insufficient = item?.evidence_state === "insufficient";

  return (
    <>
      <section className="card price-form">
        <div className="section-head">
          <div>
            <h2>Change a price</h2>
            <p>Break-even first, then what the price history can support. Nothing is changed in your POS.</p>
          </div>
          {mid === "hypermarket" && (
            <div className="dataset-toggle" role="group" aria-label="Price history to use">
              <button className={dataset === "live" ? "selected" : ""} aria-pressed={dataset === "live"} onClick={() => setDataset("live")}>
                Live history
              </button>
              <button className={dataset === "pilot" ? "selected" : ""} aria-pressed={dataset === "pilot"} onClick={() => setDataset("pilot")}>
                Price-test pilot
              </button>
            </div>
          )}
        </div>
        {dataset === "pilot" && (
          <p className="pilot-note">
            <FlaskConical size={14} /> Synthetic price-test data for Asha Hypermarket, built to show what a controlled price history allows. Live history
            has only ever had one price per item.
          </p>
        )}
        <div className="price-grid">
          <label>
            Product
            <select aria-label="Product to reprice" value={sku} onChange={(e) => { setSku(e.target.value); const it = items.find((i) => i.id === e.target.value); if (it) setPrice(suggest(it)); setResult(null); }}>
              {items.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Proposed price (₹)
            <input aria-label="Proposed price" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
          </label>
          <label>
            Look ahead
            <select aria-label="Horizon in days" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
              {[7, 14, 21, 30].map((d) => (
                <option key={d} value={d}>
                  {d} days
                </option>
              ))}
            </select>
          </label>
        </div>
        {item && (
          <div className="fact-row">
            <span>
              Price now <strong>{inr(item.price_paise)}</strong>
            </span>
            <span>
              Unit cost <strong>{inr(item.cost_paise)}</strong>
            </span>
            <span>
              Margin <strong>{inr(item.price_paise - item.cost_paise)}</strong>
            </span>
            <span>
              Stock <strong>{item.on_hand} units</strong>
            </span>
            <span className={"badge " + (STATE_TONE[item.evidence_state] || "neutral")} title="How much price history Pi has for this item">
              {item.evidence_label}
            </span>
          </div>
        )}
        {item?.story && <p className="fine-print">{item.story}</p>}
        <div className="chip-row" aria-label="Quick prices">
          {item &&
            [-0.1, -0.05, -0.02, 0.02, 0.05].map((f) => (
              <button key={f} className="chip" onClick={() => setPrice(String(Math.round((item.price_paise * (1 + f)) / 100)))}>
                {f > 0 ? "+" : ""}
                {Math.round(f * 100)}%
              </button>
            ))}
        </div>
        <details className="price-advanced">
          <summary>Stock, costs and your own numbers (optional)</summary>
          <div className="price-grid">
            <label>
              Other cost per unit (₹)
              <input aria-label="Other cost per unit" inputMode="decimal" value={extraCost} onChange={(e) => setExtraCost(e.target.value)} placeholder="0" />
            </label>
            <label>
              Delivery arriving: units
              <input aria-label="Delivery units" inputMode="numeric" value={arrivalQty} onChange={(e) => setArrivalQty(e.target.value)} placeholder="none" />
            </label>
            <label>
              Delivery arrives on day
              <input aria-label="Delivery day" inputMode="numeric" value={arrivalDay} onChange={(e) => setArrivalDay(e.target.value)} />
            </label>
            <label>
              Units you expect at today's price
              <input aria-label="Expected units" inputMode="numeric" value={baseline} onChange={(e) => setBaseline(e.target.value)} placeholder="from history" />
            </label>
          </div>
          {insufficient && (
            <div className="assume-box">
              <label className="check">
                <input type="checkbox" checked={assume} onChange={(e) => setAssume(e.target.checked)} />
                What if customers react this strongly? <small>(an assumption, not learned from your sales)</small>
              </label>
              {assume && (
                <label>
                  A 1% price rise cuts units by about {eta.toFixed(1)}%
                  <input type="range" aria-label="Assumed price sensitivity" min={0.5} max={5} step={0.1} value={eta} onChange={(e) => setEta(Number(e.target.value))} />
                </label>
              )}
            </div>
          )}
          <label>
            Prices to compare (₹, optional)
            <input aria-label="Prices to compare" value={candidates} onChange={(e) => setCandidates(e.target.value)} placeholder="e.g. 110, 115, 120, 125 — blank uses a sensible range" />
          </label>
        </details>
        <div className="trial-actions">
          <button className="primary" disabled={busy || !item} onClick={() => run("reprice")}>
            Check this price
          </button>
          <button className="secondary" disabled={busy || !item} onClick={() => run("recommend")}>
            Compare prices
          </button>
        </div>
        {error && (
          <p className="inline-error" role="alert">
            {error}
          </p>
        )}
      </section>
      {result?.kind === "reprice" && <RepriceResult r={result} show={show} save={save} saved={saved} />}
      {result?.kind === "recommend_price" && <CompareResult r={result} show={show} save={save} saved={saved} />}
    </>
  );
}

function Evidence({ r }: { r: Result }) {
  const e = r.evidence;
  const s = e.support;
  return (
    <div className="evidence-card">
      <div className="evidence-head">
        <span className={"badge " + (STATE_TONE[e.state] || "neutral")}>{e.label}</span>
        {s && <span className="badge neutral">{s.kind === "interpolation" ? "Inside the tested price range" : `Outside the tested range by ${(s.outside_by_fraction * 100).toFixed(0)}%`}</span>}
      </div>
      <p>{e.explanation}</p>
      <dl>
        <div><dt>Price levels seen</dt><dd>{e.distinct_price_levels}</dd></div>
        <div><dt>Price changes</dt><dd>{e.price_change_episodes}</dd></div>
        <div><dt>Range</dt><dd>{e.price_range_paise[0] != null ? `${inr(e.price_range_paise[0])} to ${inr(e.price_range_paise[1])}` : "—"}</dd></div>
        <div><dt>Days with stock</dt><dd>{e.available_days}</dd></div>
        <div><dt>Stock-out days</dt><dd>{e.stockout_days}</dd></div>
        {e.randomized_blocks > 0 && <div><dt>Randomized weeks</dt><dd>{e.randomized_blocks}</dd></div>}
      </dl>
      <ul className="limits">
        {e.limitations.map((l: string) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
    </div>
  );
}

function Plan({ plan, save, saved }: { plan: any; save: (k: "scenario" | "experiment_plan") => void; saved: string }) {
  if (!plan) return null;
  return (
    <section className="card plan-card">
      <div className="section-head">
        <div>
          <h2>A small price trial would settle this</h2>
          <p>A plan only. Nothing runs by itself.</p>
        </div>
      </div>
      <ul className="plan-list">
        <li><strong>Prices to test:</strong> {plan.candidate_prices_paise.map((p: number) => inr(p)).join(", ")}</li>
        <li><strong>How:</strong> {plan.randomization_unit}. {plan.assignment}</li>
        <li><strong>How long:</strong> {plan.weeks_per_price} weeks per price ({plan.total_weeks} weeks in total). {plan.sample_size_reasoning}</li>
        <li><strong>Stock:</strong> {plan.inventory_requirement}</li>
        <li><strong>Keep steady:</strong> {plan.keep_constant.join("; ")}</li>
        <li><strong>Judge it by:</strong> {plan.primary_metric}</li>
        <li><strong>Afterwards:</strong> {plan.after_the_test}</li>
      </ul>
      <button className="secondary" onClick={() => save("experiment_plan")}>
        Save this plan locally
      </button>
      {saved && <p className="fine-print" role="status">{saved}</p>}
    </section>
  );
}

function RepriceResult({ r, show, save, saved }: { r: Result; show: (p: any) => void; save: (k: "scenario" | "experiment_plan") => void; saved: string }) {
  const b = r.breakeven;
  const f = r.forecast;
  return (
    <>
      <section className="card price-result" aria-live="polite">
        <div className="result-top">
          <span className={"badge big " + (DECISION_TONE[r.decision.id] || "neutral")}>{r.decision.label}</span>
          <button className="proof-button" onClick={() => show(r.receipt)}>
            <ReceiptText size={14} />
            Show calculation
          </button>
        </div>
        <h2 className="price-headline">{r.headline}</h2>
        <p className="fine-print">{r.decision.reason}</p>
        {b.status === "ok" && (
          <div className="breakeven-strip">
            <div><span>Units needed</span><strong>{b.required_units}</strong><small>{pct(b.required_uplift)} on {Number(b.baseline_units).toFixed(Number.isInteger(b.baseline_units) ? 0 : 1)} ({r.baseline.source.replace(/_/g, " ")})</small></div>
            <div><span>Contribution to beat</span><strong>{inr(b.baseline_contribution_paise)}</strong><small>at {inr(r.product.price_paise)} today</small></div>
            <div><span>New margin per unit</span><strong>{inr(b.new_margin_paise, 2)}</strong><small>was {inr(b.current_margin_paise, 2)}</small></div>
          </div>
        )}
        {b.status !== "ok" && b.reason && <p className="fine-print">{b.reason}</p>}
        {r.mode === "withheld" ? (
          <div className="withheld" role="note">
            <Lock size={16} />
            <div>
              <strong>Demand forecast withheld</strong>
              <p>Pi will not guess how many units you would sell at a new price without price history to learn from. Break-even above is exact; the trial plan below shows how to learn the answer.</p>
            </div>
          </div>
        ) : (
          f && (
            <>
              {r.assumption && <p className="assumption-tag">{r.assumption.label}</p>}
              <div className="forecast-grid">
                <div>
                  <span>Expected units, {r.horizon} days</span>
                  <strong>{n0(f.expected_units)}</strong>
                  <small>
                    Where one future could land: {n0(f.units_outcome_interval[0])} to {n0(f.units_outcome_interval[1])}. Uncertainty in the average: {n0(f.units_mean_interval[0])} to {n0(f.units_mean_interval[1])}.
                  </small>
                  <small>Without a price change: {n0(f.baseline_units)}</small>
                </div>
                <div>
                  <span>Contribution change</span>
                  <strong className={f.delta_contribution_paise >= 0 ? "up" : "down"}>{inr(f.delta_contribution_paise)}</strong>
                  <small>
                    Where one future could land: {inr(f.delta_outcome_interval[0])} to {inr(f.delta_outcome_interval[1])}. Chance it is lower: {(f.probability_lower * 100).toFixed(0)}%.
                  </small>
                  <small>Revenue changes by {inr(f.delta_revenue_paise)}: more revenue is not more contribution.</small>
                </div>
                <div>
                  <span>Stock</span>
                  <strong>{n0(f.expected_remaining_stock)} left</strong>
                  <small>
                    Chance of running out: {(f.stockout_probability * 100).toFixed(0)}%. Sales lost to stock: {n0(f.expected_units_lost_to_stock)} units.
                  </small>
                  <small>{r.stock.description}</small>
                </div>
              </div>
            </>
          )
        )}
        {r.model && (
          <p className="fine-print">
            Price sensitivity estimated at {r.model.price_sensitivity} (±{r.model.price_sensitivity_se}): a 1% price rise cuts units by about that many percent.
            {r.model.uncertainty_widened_for_confounding && " Uncertainty is widened because the price history was not a controlled test."}
          </p>
        )}
        <p className="fine-print">{r.scope}</p>
        <div className="trial-actions">
          <button className="secondary" onClick={() => save("scenario")}>
            Save this scenario locally
          </button>
          {saved && <span className="fine-print" role="status">{saved}</span>}
        </div>
      </section>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>What the price history says</h2>
            <p>Evidence status for {r.product.name}</p>
          </div>
        </div>
        <Evidence r={r} />
      </section>
      <Plan plan={r.experiment_plan} save={save} saved={saved} />
    </>
  );
}

function CompareResult({ r, show, save, saved }: { r: Result; show: (p: any) => void; save: (k: "scenario" | "experiment_plan") => void; saved: string }) {
  const rows = r.candidates as any[];
  const forecasts = rows.filter((c) => c.forecast);
  const chart = forecasts.map((c) => ({ name: inr(c.price_paise), delta: Math.round(c.forecast.delta_contribution_paise / 100), best: c.price_paise === r.best_price_paise }));
  return (
    <>
      <section className="card price-result" aria-live="polite">
        <div className="result-top">
          <span className={"badge big " + (DECISION_TONE[r.decision.id] || "neutral")}>{r.decision.label}</span>
          <button className="proof-button" onClick={() => show(r.receipt)}>
            <ReceiptText size={14} />
            Show calculation
          </button>
        </div>
        <h2 className="price-headline">{r.headline}</h2>
        <p className="fine-print">{r.decision.reason}</p>
        {r.assumption && <p className="assumption-tag">{r.assumption.label}</p>}
        {r.mode === "withheld" && (
          <div className="withheld" role="note">
            <Lock size={16} />
            <div>
              <strong>Demand forecasts withheld</strong>
              <p>This item has no price variation to learn from. The table shows the exact number of sales each price would need.</p>
            </div>
          </div>
        )}
        {chart.length > 0 && (
          <div className="chart price-chart" aria-label="Expected contribution change by price">
            <ResponsiveContainer>
              <BarChart data={chart} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="#e9edf3" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#788397" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#788397" }} axisLine={false} tickLine={false} width={52} tickFormatter={(v) => `${v < 0 ? "-" : ""}₹${Math.abs(v).toLocaleString("en-IN")}`} />
                <ReferenceLine y={0} stroke="#9aa7b9" />
                <Tooltip formatter={(v) => [`₹${Number(v).toLocaleString("en-IN")}`, "Expected change"]} />
                <Bar dataKey="delta" isAnimationActive={false} radius={[3, 3, 0, 0]}>
                  {chart.map((c) => (
                    <Cell key={c.name} fill={c.delta >= 0 ? (c.best ? "#147d68" : "#7fc4b4") : "#d98a90"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className="table-wrap">
          <table className="price-table">
            <thead>
              <tr>
                <th>Price</th>
                <th>Units needed</th>
                <th>Expected units</th>
                <th>Contribution change</th>
                <th>Chance lower</th>
                <th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.price_paise} className={c.is_current ? "current" : c.price_paise === r.best_price_paise ? "best" : ""}>
                  <td>
                    <strong>{inr(c.price_paise)}</strong>
                    {c.is_current && <small>current</small>}
                    {c.support?.kind === "extrapolation" && <small>outside tested range</small>}
                  </td>
                  <td>{c.breakeven.required_units ?? "none"}</td>
                  <td>{c.forecast ? n0(c.forecast.expected_units) : "withheld"}</td>
                  <td>{c.forecast ? inr(c.forecast.delta_contribution_paise) : "withheld"}</td>
                  <td>{c.forecast ? `${(c.forecast.probability_lower * 100).toFixed(0)}%` : "—"}</td>
                  <td>
                    <span className={"badge " + (DECISION_TONE[c.decision.id] || "neutral")}>{c.decision.label}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {r.dropped.length > 0 && (
          <p className="fine-print">
            Left out: {r.dropped.map((d: any) => `${inr(d.price_paise)} (${d.reason})`).join("; ")}.
          </p>
        )}
        <p className="fine-print">{r.scope} Labels are product thresholds, not statistical guarantees.</p>
      </section>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>What the price history says</h2>
            <p>Evidence status for {r.product.name}</p>
          </div>
        </div>
        <Evidence r={r} />
      </section>
      <Plan plan={r.experiment_plan} save={save} saved={saved} />
    </>
  );
}
