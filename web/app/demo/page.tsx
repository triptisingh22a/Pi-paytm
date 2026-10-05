"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Check,
  ChevronRight,
  FlaskConical,
  Home,
  Layers,
  Lock,
  Mic,
  Package,
  ReceiptText,
  RefreshCw,
  Repeat,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  Users,
  Volume2,
  Wallet,
  X,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LineChart,
  Line,
  Legend,
  BarChart,
  Bar,
} from "recharts";
import { ReceiptDialog } from "@/components/ui/dialog";
import PricePanel, { type PriceExternal } from "./price-panel";

type Proof = {
  inputs: Record<string, unknown>;
  formula_text: string;
  output: Record<string, any>;
  assumptions: string[];
  steps?: unknown[];
  data_tier: string;
  data_quality_flags: string[];
};
type Product = {
  id: string;
  name: string;
  family: string;
  price: number;
  cost: number;
  candidate: boolean;
  on_hand: number;
  units: number;
  revenue: number;
  revenue_share: number;
  health: string;
  days_cover: number | null;
  rate_change_pct: number | null;
  trend: string;
  recipe: Record<string, number>;
};
type Dashboard = {
  merchant: string;
  name: string;
  kind: string;
  period: string;
  start: string;
  end: string;
  revenue: number;
  contribution: number;
  bills: number;
  units: number;
  ticket: number;
  known_bills: number;
  returning_bills: number;
  anonymous_bills: number;
  inventory: Product[];
  chart: { label: string; revenue: number }[];
  customer_profiles: { profile: string; bills: number; share: number }[];
  top_units: Product[];
  top_revenue: Product[];
  rising: Product[];
  falling: Product[];
  dead: Product[];
  nudges: {
    product: string;
    name: string;
    reason: string;
    on_hand: number;
    days_cover: number | null;
  }[];
  receipt: Proof;
};
type Insight = {
  id: string;
  title: string;
  tone: "up" | "down" | "warn" | "info";
  headline: string;
  detail: string;
  question: string;
  receipt: Proof;
};
type InsightFeed = {
  generated_at: string;
  trigger: string;
  refresh_seconds: number;
  insights: Insight[];
};
type HabitGroup = {
  product: string;
  product_name: string;
  cadence: string;
  rhythm: string;
  gap_days: number;
  customers: number;
  due_back: number;
};
type Habit = {
  customer: string;
  member: string;
  product_name: string;
  cadence: string;
  visits: number;
  last_visit: string;
  days_since_last: number;
  status: string;
};
type Habits = {
  window: string[];
  groups: HabitGroup[];
  habits: Habit[];
  summary: { regular_customers: number; habits: number; due_back: number };
  receipt: Proof;
};
type Peer = {
  verdict: string;
  reason?: string;
  name: string;
  family: string;
  peer_count: number;
  eligible_count: number;
  effective_peers: number;
  mapping_confidence: number;
  peer_rate_per_100_bills: number;
  rate: number;
  rate_p10: number;
  rate_p90: number;
  local_units: number;
  local_exposure: number;
  weighted_exposure: number;
  window: string[];
  receipt: Proof;
};
type Trial = {
  verdict: string;
  reason?: string;
  remove: string;
  replace: string;
  remove_id: string;
  replace_id: string;
  horizon: number;
  quantity: number;
  purchase_cost: number;
  incremental_revenue: number;
  p10: number;
  p50: number;
  p90: number;
  incremental_contribution: number;
  probability_revenue_loss: number;
  candidate_units: number;
  unsold_candidate_value: number;
  incremental_cash_after_purchase: number;
  peer_count: number;
  effective_peers: number;
  opportunities: number;
  paths: number;
  baseline_revenue: number;
  scenario_revenue: number;
  chart: { day: number; baseline: number; scenario: number }[];
  products: {
    name: string;
    baseline_units: number;
    scenario_units: number;
    revenue_delta: number;
  }[];
  sensitivity: { outside_factor: number; incremental_revenue: number }[];
  ingredient_remaining: {
    ingredient: string;
    baseline_kg: number;
    scenario_kg: number;
  }[];
  peer_evidence: Peer;
  receipt: Proof;
};
type Answer = {
  tool: string;
  provider: string;
  answer: string;
  result: any;
  receipt: Proof | null;
  grounded: boolean;
  language_code?: string;
  canonical_answer?: string;
  translation_status?: string;
  tool_trace?: { tool?: string; status: string }[];
};
type Message = {
  role: "user" | "assistant";
  text: string;
  proof?: Proof | null;
  tool?: string;
  language?: string;
  canonical?: string;
  provider?: string;
  translation?: string;
  trace?: { tool?: string; status: string }[];
};
type Invoice = {
  invoice_id: string;
  lines: { product: string; quantity: number; unit_cost: number }[];
  source_text: string;
  note: string;
};
const money = (n: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n);
const short = (n: number) =>
  n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
const ago = (iso: string) => {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)} min ago` : `${Math.floor(s / 3600)} h ago`;
};
const STOCK_FILTERS: { id: string; label: string; test: (p: Product) => boolean }[] = [
  { id: "all", label: "All products", test: () => true },
  { id: "replenish", label: "Replenish soon", test: (p) => p.health === "restock soon" },
  { id: "nosales", label: "No recorded sales", test: (p) => p.health === "no recorded sales" },
  { id: "slow", label: "Slow moving", test: (p) => p.health === "slow moving" },
  { id: "healthy", label: "Healthy", test: (p) => p.health === "healthy" },
  { id: "notstocked", label: "Not stocked", test: (p) => p.health === "not stocked" },
];
async function api(path: string, body?: unknown) {
  const res = await fetch(
    "/api" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!res.ok) {
    const e = await res.json().catch(() => ({ detail: "Service unavailable" }));
    throw new Error(
      typeof e.detail === "string" ? e.detail : "Please check the input.",
    );
  }
  return res.json();
}
function ProofButton({
  proof,
  show,
  label = "Show calculation",
}: {
  proof: Proof;
  show: (p: Proof) => void;
  label?: string;
}) {
  return (
    <button className="proof-button" onClick={() => show(proof)}>
      <ReceiptText size={14} />
      {label}
    </button>
  );
}
function Badge({ health }: { health: string }) {
  return (
    <span
      className={
        "badge " +
        (health === "healthy"
          ? "good"
          : health === "not stocked"
            ? "neutral"
            : health === "restock soon"
              ? "warn"
              : "bad")
      }
    >
      {health}
    </span>
  );
}
function RevenueChart({ data }: { data: Dashboard["chart"] }) {
  return (
    <div className="chart">
      <ResponsiveContainer>
        <AreaChart
          data={data}
          margin={{ top: 14, right: 16, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2463ed" stopOpacity={0.18} />
              <stop offset="100%" stopColor="#2463ed" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#e9edf3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "#788397" }}
            axisLine={false}
            tickLine={false}
            minTickGap={25}
          />
          <YAxis
            tickFormatter={short}
            tick={{ fontSize: 11, fill: "#788397" }}
            axisLine={false}
            tickLine={false}
            width={46}
          />
          <Tooltip formatter={(v) => money(Number(v))} />
          <Area
            type="monotone"
            dataKey="revenue"
            name="Recorded revenue"
            stroke="#2463ed"
            strokeWidth={2.5}
            fill="url(#revenueFill)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
const NAV = [
  { id: "overview", label: "Overview", icon: Home },
  { id: "inventory", label: "Inventory", icon: Package },
  { id: "twin", label: "Digital twin", icon: FlaskConical },
  { id: "peers", label: "Lookalike shops", icon: Users },
  { id: "decisions", label: "Decision lab", icon: Wallet },
  { id: "proof", label: "Data & integrations", icon: ShieldCheck },
];
export default function Demo() {
  const [mid, setMid] = useState("hypermarket");
  const [period, setPeriod] = useState("day");
  const [tab, setTab] = useState("overview");
  const [data, setData] = useState<Dashboard | null>(null);
  const [meta, setMeta] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [proof, setProof] = useState<Proof | null>(null);
  const [peer, setPeer] = useState<Peer | null>(null);
  const [trial, setTrial] = useState<Trial | null>(null);
  const [ranked, setRanked] = useState<Trial[]>([]);
  const [remove, setRemove] = useState("");
  const [replace, setReplace] = useState("");
  const [quantity, setQuantity] = useState(50);
  const [budget, setBudget] = useState(20000);
  const [horizon, setHorizon] = useState(7);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [language, setLanguage] = useState("unknown");
  const [recording, setRecording] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [imported, setImported] = useState(false);
  const [search, setSearch] = useState("");
  const [stockFilter, setStockFilter] = useState("all");
  const [twinMode, setTwinMode] = useState<"swap" | "price">("swap");
  const [priceDataset, setPriceDataset] = useState<"live" | "pilot">("live");
  const [priceSku, setPriceSku] = useState("");
  const [priceExternal, setPriceExternal] = useState<PriceExternal | null>(null);
  const [feed, setFeed] = useState<InsightFeed | null>(null);
  const [habits, setHabits] = useState<Habits | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [showAllHabits, setShowAllHabits] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const media = useRef<MediaStream | null>(null);
  const recordingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const conversation = useRef<HTMLDivElement>(null);
  const generation = useRef(0);
  const current = useRef({ mid, period });
  current.current = { mid, period };
  const audio = useRef<HTMLAudioElement | null>(null);
  const load = useCallback(async () => {
    const ticket = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const d = await api(`/v2/dashboard/${mid}?period=${period}`);
      if (ticket === generation.current) setData(d);
    } catch (e) {
      if (ticket === generation.current) setError((e as Error).message);
    } finally {
      if (ticket === generation.current) setLoading(false);
    }
  }, [mid, period]);
  useEffect(() => {
    load();
  }, [load]);
  const loadInsights = useCallback(
    async (manual = false) => {
      const asked = { mid, period };
      if (manual) setRefreshing(true);
      try {
        const f: InsightFeed = manual
          ? await api(`/v2/insights/${mid}/refresh?period=${period}`, {})
          : await api(`/v2/insights/${mid}?period=${period}`);
        if (current.current.mid === asked.mid && current.current.period === asked.period)
          setFeed(f);
      } catch {
        /* the cards keep their last result */
      } finally {
        if (manual) setRefreshing(false);
      }
    },
    [mid, period],
  );
  useEffect(() => {
    setFeed(null);
    loadInsights();
    // Picks up the server's scheduled refresh without a page reload.
    const timer = setInterval(() => loadInsights(), 60_000);
    return () => clearInterval(timer);
  }, [loadInsights]);
  useEffect(() => {
    setHabits(null);
    setShowAllHabits(false);
    api(`/v2/habits/${mid}`)
      .then(setHabits)
      .catch(() => {});
  }, [mid]);
  useEffect(() => {
    api("/v2/merchants")
      .then(setMeta)
      .catch(() => {});
  }, []);
  useEffect(() => {
    setTrial(null);
    setPeer(null);
    setRanked([]);
    setInvoice(null);
    setImported(false);
    setSearch("");
    setStockFilter("all");
    setPriceExternal(null);
    if (mid !== "hypermarket") setPriceDataset("live");
    setMessages([
      {
        role: "assistant",
        text: "Your POS data is ready. Ask what sold, what to replenish, who your regulars are, or try a product replacement on your digital twin.",
      },
    ]);
    setRemove("");
    setReplace("");
    setVoiceStatus("");
  }, [mid]);
  useEffect(() => {
    if (
      data &&
      data.merchant === mid &&
      (!remove || !data.inventory.some((p) => p.id === remove))
    ) {
      setRemove(
        data.inventory.find((p) => p.trend === "dead")?.id ||
          data.inventory[0].id,
      );
      setReplace(data.inventory.find((p) => p.candidate)?.id || "");
    }
  }, [data, remove, mid]);
  useEffect(() => {
    conversation.current?.scrollTo({
      top: conversation.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, busy]);
  useEffect(
    () => () => {
      if (recordingTimer.current) clearTimeout(recordingTimer.current);
      recorder.current?.stop();
      media.current?.getTracks().forEach((t) => t.stop());
      audio.current?.pause();
    },
    [],
  );
  const send = async (value = text) => {
    if (!value.trim() || busy) return;
    const askedMid = mid;
    setText("");
    setBusy(true);
    setError("");
    setMessages((m) => [...m, { role: "user", text: value }]);
    try {
      const dataset = mid === "hypermarket" ? priceDataset : "live";
      const r: Answer = await api(`/v2/ask/${mid}`, { text: value, period, language, dataset });
      if (current.current.mid !== askedMid) return;
      if (["reprice", "recommend_price"].includes(r.tool) && r.result) {
        setPriceExternal({ result: r.result, dataset, nonce: Date.now() });
        setPriceSku(r.result.product?.id || "");
        setTwinMode("price");
        setTab("twin");
      }
      setMessages((m) => [
        ...m,
        { role: "assistant", text: r.answer, proof: r.receipt, tool: r.tool, language: r.language_code || "en-IN", canonical: r.canonical_answer, provider: r.provider, translation: r.translation_status, trace: r.tool_trace },
      ]);
      if (r.tool === "replace" && r.result?.verdict === "SCENARIO") {
        setTrial(r.result);
        setRanked([]);
        setTab("twin");
        setRemove(r.result.remove_id);
        setReplace(r.result.replace_id);
      }
      if (r.tool === "recommend" && r.result?.candidates?.length) {
        setTrial(r.result.candidates[0]);
        setRemove(r.result.candidates[0].remove_id);
        setReplace(r.result.candidates[0].replace_id);
        setRanked(r.result.candidates);
        setTab("twin");
      }
      if (["replace", "recommend"].includes(r.tool) && r.result) {
        setQuantity(
          r.result.quantity || r.result.candidates?.[0]?.quantity || 50,
        );
        setHorizon(r.result.horizon || r.result.candidates?.[0]?.horizon || 7);
        setBudget(r.result.budget || r.result.candidates?.[0]?.budget || 10000);
      }
      if (r.tool === "peers" && r.result?.verdict === "SUPPORTED") {
        setPeer(r.result);
        setTab("peers");
      }
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: (e as Error).message },
      ]);
    } finally {
      setBusy(false);
    }
  };
  const run = async (recommend = false) => {
    setBusy(true);
    setError("");
    try {
      const result = await api(`/v2/twin/${mid}`, {
        remove,
        replace: recommend ? null : replace,
        quantity,
        budget,
        horizon,
      });
      if (recommend) {
        setRanked(result.candidates || []);
        setTrial(result.candidates?.[0] || null);
        if (result.candidates?.[0]) setReplace(result.candidates[0].replace_id);
        if (!result.candidates?.length)
          setError(result.reason || "Not enough evidence");
      } else {
        setRanked([]);
        if (result.verdict === "SCENARIO") setTrial(result);
        else setError(result.reason);
      }
      setTab("twin");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const fetchPeers = async (product = replace) => {
    setBusy(true);
    setError("");
    try {
      const p = await api(
        `/v2/peers/${mid}?product=${encodeURIComponent(product)}`,
      );
      if (p.verdict === "SUPPORTED") setPeer(p);
      else setError(p.reason);
      setTab("peers");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const startVoice = async () => {
    if (recording) {
      recorder.current?.stop();
      return;
    }
    if (!meta?.voice?.enabled) {
      setVoiceStatus(
        "Sarvam voice needs a server-side key. Text chat is available.",
      );
      return;
    }
    try {
      media.current = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      const mime = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4";
      const rec = new MediaRecorder(media.current, { mimeType: mime });
      recorder.current = rec;
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data);
      };
      rec.onstop = async () => {
        setRecording(false);
        if (recordingTimer.current) clearTimeout(recordingTimer.current);
        media.current?.getTracks().forEach((t) => t.stop());
        setVoiceStatus("Transcribing with Sarvam…");
        try {
          const form = new FormData();
          form.append(
            "file",
            new Blob(chunks, { type: mime }),
            "recording." + (mime === "audio/webm" ? "webm" : "m4a"),
          );
          form.append("language", language);
          const response = await fetch("/api/v2/voice/stt", {
            method: "POST",
            body: form,
          });
          if (!response.ok)
            throw new Error("Voice request failed. No retry was made.");
          const result = await response.json();
          setText(result.transcript);
          if (result.language_code) setLanguage(result.language_code);
          setVoiceStatus(`Transcript ready · ${result.language_code || "language uncertain"}. Review it, then send.`);
        } catch (e) {
          setVoiceStatus((e as Error).message);
        }
      };
      rec.start();
      setRecording(true);
      setVoiceStatus("Listening · stops after 20 seconds");
      recordingTimer.current = setTimeout(() => {
        if (rec.state === "recording") rec.stop();
      }, 20000);
    } catch {
      setVoiceStatus("Microphone unavailable. Use text chat.");
    }
  };
  const speak = async (value: string, answerLanguage = "en-IN") => {
    if (meta?.voice?.enabled) {
      setVoiceStatus("Generating speech with Sarvam…");
      try {
        const r = await fetch("/api/v2/voice/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: value.slice(0, 2500), language: answerLanguage }),
        });
        if (!r.ok) throw new Error("Speech request failed. No retry was made.");
        const url = URL.createObjectURL(await r.blob());
        audio.current?.pause();
        audio.current = new Audio(url);
        audio.current.onended = () => URL.revokeObjectURL(url);
        await audio.current.play();
        setVoiceStatus("Sarvam audio playing");
      } catch (e) {
        setVoiceStatus((e as Error).message);
      }
    } else if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const s = new SpeechSynthesisUtterance(value);
      s.lang = answerLanguage;
      window.speechSynthesis.speak(s);
      setVoiceStatus("Browser speech fallback · Sarvam is not configured");
    }
  };
  const openInvoice = async () => {
    setError("");
    try {
      setInvoice(await api(`/v2/invoices/${mid}/sample`));
      setImported(false);
      // The review panel renders below the ledger; bring it into view so the click visibly does something.
      setTimeout(
        () => document.querySelector(".invoice-card")?.scrollIntoView({ behavior: "smooth", block: "start" }),
        60,
      );
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const confirmInvoice = async () => {
    if (!invoice) return;
    setBusy(true);
    try {
      await api(`/v2/invoices/${mid}/confirm`, {
        invoice_id: invoice.invoice_id,
        lines: invoice.lines,
        confirmed: true,
      });
      setImported(true);
      await load();
      loadInsights(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const prepare = (product: Product) => {
    setRemove(product.id);
    setReplace(
      data?.inventory.find((p) => p.candidate && p.family === product.family)
        ?.id || "",
    );
    setTrial(null);
    setRanked([]);
    setTab("twin");
  };
  const topups = new Map<string, number>(
    ((feed?.insights.find((i) => i.id === "restock")?.receipt.output.items as { name: string; topup: number }[]) || []).map(
      (r) => [r.name, r.topup],
    ),
  );
  const stockCounts: Record<string, number> = Object.fromEntries(
    STOCK_FILTERS.map((f) => [f.id, data?.inventory.filter(f.test).length ?? 0]),
  );
  const activeFilter = STOCK_FILTERS.find((f) => f.id === stockFilter) || STOCK_FILTERS[0];
  const visibleStock = (data?.inventory || [])
    .filter(activeFilter.test)
    .filter((p) => p.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => (stockFilter === "replenish" ? (a.days_cover ?? 99) - (b.days_cover ?? 99) : 0));
  const candidate = data?.inventory.find((p) => p.id === replace);
  const removing = data?.inventory.find((p) => p.id === remove);
  const options =
    data?.inventory.filter(
      (p) => p.candidate && p.family === removing?.family,
    ) || [];
  const promptReplace = data
    ? `What should I replace ${data.inventory.find((p) => p.trend === "dead")?.name} with to increase revenue?`
    : "";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="brand">
          <span className="mark">π</span>pi
          <span className="brand-dot">.</span>
        </Link>
        <div className="workspace-label">MERCHANT WORKSPACE</div>
        <nav>
          {NAV.map((n) => (
            <button
              key={n.id}
              className={tab === n.id ? "nav-item active" : "nav-item"}
              onClick={() => setTab(n.id)}
            >
              <n.icon size={18} />
              {n.label}
              {tab === n.id && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <Layers size={20} />
          <strong>
            One shop.
            <br />
            Many possible futures.
          </strong>
          <p>
            Your data builds the twin.
            <br />
            Lookalikes add perspective.
          </p>
          <span>
            <i /> Simulated POS data
          </span>
        </div>
        <div className="sidebar-foot">
          <span className="avatar">AS</span>
          <div>
            Demo workspace<small>Item-level billing · Tier B</small>
          </div>
        </div>
      </aside>
      <div className="app-body">
        <header className="app-header">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />{" "}
            <strong>{NAV.find((n) => n.id === tab)?.label}</strong>
          </div>
          <div className="header-controls">
            <span className="simulation-label">SIMULATED DATA</span>
            <label className="shop-picker">
              <span className="sr-only">Choose merchant</span>
              <select
                aria-label="Choose merchant"
                value={mid}
                disabled={busy || recording}
                onChange={(e) => setMid(e.target.value)}
              >
                {(
                  meta?.merchants || [
                    { id: "hypermarket", name: "Asha Hypermarket" },
                    { id: "restaurant", name: "Annapurna Kitchen" },
                    { id: "apparel", name: "Thread & Co." },
                  ]
                ).map((s: any) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <span className="avatar">AS</span>
          </div>
        </header>
        <div className="workspace">
          <main className="main-content">
            <div className="page-heading">
              <div>
                <div className="eyebrow">
                  {data?.kind?.replace("_", " ").toUpperCase() || "YOUR SHOP"} /
                  POS CONNECTED
                </div>
                <h1>
                  {tab === "overview"
                    ? "A clearer view of your shop."
                    : tab === "inventory"
                      ? "Every shelf has a story."
                      : tab === "twin"
                        ? "Try the idea. Then decide."
                        : tab === "peers"
                          ? "Better perspective, together."
                          : tab === "decisions"
                            ? "What can Pi decide for you?"
                            : "Grounded from the first bill."}
                </h1>
                <p>
                  {tab === "overview"
                    ? "Your sales, shelves, and next opportunities — in one place."
                    : tab === "inventory"
                      ? "Availability and recorded demand, side by side."
                      : tab === "twin"
                        ? "Replace a product on your digital twin before committing cash."
                        : tab === "peers"
                          ? "Same-type shops. Canonical products. Aggregate evidence."
                          : tab === "decisions"
                            ? "The decisions your data supports today, and the ones it cannot yet."
                            : "Every calculation has a trail. Every integration has a clear status."}
                </p>
              </div>
              {["overview", "inventory"].includes(tab) && (
                <div className="period-switch" aria-label="Sales period">
                  {["day", "week", "month"].map((p) => (
                    <button
                      key={p}
                      className={period === p ? "selected" : ""}
                      onClick={() => setPeriod(p)}
                    >
                      {p[0].toUpperCase() + p.slice(1)}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {error && (
              <div className="error" role="alert">
                {error}
                <button aria-label="Dismiss error" onClick={() => setError("")}>
                  <X size={16} />
                </button>
              </div>
            )}
            {loading && (
              <div className="loading-line">Reading the POS ledger…</div>
            )}
            {!data && !loading && (
              <button className="primary" onClick={load}>
                Retry
              </button>
            )}
            {data && (
              <>
                <div className="data-date">
                  <span className="live-dot" /> Snapshot: 2 October 2026{" "}
                  <span>•</span> 12 months of synthetic billing history{" "}
                  {["overview", "inventory"].includes(tab) && (
                    <span className="window-label">
                      {data.start} → {data.end}
                    </span>
                  )}
                </div>
                {tab === "overview" && (
                  <>
                    <div className="metrics three">
                      <div className="metric">
                        <span>
                          Recorded revenue <BarChart3 size={15} />
                        </span>
                        <strong>{money(data.revenue)}</strong>
                        <small>
                          {data.bills} completed bills · {period}
                        </small>
                      </div>
                      <div className="metric">
                        <span>
                          Gross contribution <Wallet size={15} />
                        </span>
                        <strong>{money(data.contribution)}</strong>
                        <small>
                          After supplied item costs · before overhead
                        </small>
                      </div>
                      <div className="metric">
                        <span>
                          Regular customers <Repeat size={15} />
                        </span>
                        <strong>{habits ? habits.summary.regular_customers : "—"}</strong>
                        <small>
                          {habits
                            ? `Same product on a steady rhythm · ${habits.summary.due_back} due back`
                            : "Reading loyalty-linked bills…"}
                        </small>
                      </div>
                    </div>
                    <section className="card revenue-card">
                      <div className="section-head">
                        <div>
                          <h2>Revenue, as it happened</h2>
                          <p>Realized unit prices × recorded quantities</p>
                        </div>
                        <ProofButton proof={data.receipt} show={setProof} />
                      </div>
                      <RevenueChart data={data.chart} />
                    </section>
                    <section className="ai-overview">
                      <div className="ai-overview-head">
                        <span className="spark-icon">
                          <Sparkles size={19} />
                        </span>
                        <div>
                          <h2>Pi insights</h2>
                          <span>
                            {feed
                              ? `Updated ${ago(feed.generated_at)} · ${feed.trigger} · refreshes every ${Math.round(feed.refresh_seconds / 60)} min`
                              : "Calculating from the POS…"}
                          </span>
                        </div>
                        <button
                          className="refresh-button"
                          onClick={() => loadInsights(true)}
                          disabled={refreshing}
                        >
                          <RefreshCw size={13} className={refreshing ? "spin" : ""} />
                          {refreshing ? "Refreshing…" : "Refresh"}
                        </button>
                      </div>
                      <div className="insight-grid">
                        {(feed?.insights || [])
                          .filter((i) => i.id !== "regulars")
                          .map((i) => (
                            <article className={"insight-tile " + i.tone} key={i.id}>
                              <span className="insight-label">
                                {i.tone === "up" && <ArrowUpRight size={13} />}
                                {i.tone === "down" && <ArrowDownRight size={13} />}
                                {i.title.toUpperCase()}
                              </span>
                              <strong>{i.headline}</strong>
                              <p>{i.detail}</p>
                              <div className="insight-actions">
                                <code className="tool-chip" title="The chat agent can call this same tool">
                                  insight.{i.id}
                                </code>
                                <button onClick={() => send(i.question)}>Ask Pi</button>
                                <button onClick={() => setProof(i.receipt)}>Evidence</button>
                              </div>
                            </article>
                          ))}
                        {!feed && <p className="insight-wait">Running insight tools…</p>}
                      </div>
                    </section>
                    <div className="two-col">
                      <section className="card">
                        <div className="section-head">
                          <div>
                            <h2>Your regulars</h2>
                            <p>
                              How often customers come back for the same product
                              {habits ? ` · ${habits.window[0]} → ${habits.window[1]}` : ""}
                            </p>
                          </div>
                          {habits && <ProofButton proof={habits.receipt} show={setProof} />}
                        </div>
                        {!habits && <p className="fine-print">Reading loyalty-linked bills…</p>}
                        {habits && habits.groups.length === 0 && (
                          <p className="fine-print">
                            No customer buys the same product on a steady rhythm yet.
                          </p>
                        )}
                        {habits?.groups.slice(0, 6).map((g) => (
                          <div className="rhythm-row" key={g.product + g.cadence}>
                            <span className="rhythm-icon">
                              <Repeat size={15} />
                            </span>
                            <div>
                              <strong>
                                {g.customers} customer{g.customers === 1 ? "" : "s"} · {g.product_name}
                              </strong>
                              <small>
                                {g.cadence}
                                {g.due_back ? ` · ${g.due_back} due back` : ""}
                              </small>
                            </div>
                            <span className={"badge " + (g.due_back ? "warn" : "good")}>
                              {g.due_back ? "check in" : "on rhythm"}
                            </span>
                          </div>
                        ))}
                        {habits && habits.summary.habits > 0 && (
                          <button className="text-link" onClick={() => setShowAllHabits((v) => !v)}>
                            {showAllHabits ? "Hide" : "Show"} every customer rhythm ({habits.summary.habits}){" "}
                            <ArrowRight size={14} />
                          </button>
                        )}
                        {habits && showAllHabits && (
                          <div className="table-wrap">
                            <table>
                              <thead>
                                <tr>
                                  <th>Member</th>
                                  <th>Product</th>
                                  <th>Rhythm</th>
                                  <th>Last seen</th>
                                  <th>Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                {habits.habits.map((h) => (
                                  <tr key={h.customer + h.product_name}>
                                    <td>{h.member}</td>
                                    <td>{h.product_name}</td>
                                    <td>{h.cadence}</td>
                                    <td>{h.days_since_last === 0 ? "today" : `${h.days_since_last}d ago`}</td>
                                    <td>
                                      <span className={"badge " + (h.status === "due back" ? "warn" : "good")}>
                                        {h.status}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                        <p className="fine-print">
                          Only loyalty-linked bills can be followed. Members are pseudonymous IDs; nothing about who
                          they are is inferred.
                        </p>
                      </section>
                      <section className="card">
                        <div className="section-head">
                          <div>
                            <h2>A nudge for your next move</h2>
                            <p>Stock coverage and recorded demand</p>
                          </div>
                          <Sparkles size={19} />
                        </div>
                        {data.nudges.slice(0, 3).map((n) => (
                          <button
                            className="nudge-row"
                            key={n.product}
                            onClick={() => {
                              if (n.reason === "restock soon")
                                setTab("inventory");
                              else
                                prepare(
                                  data.inventory.find(
                                    (p) => p.id === n.product,
                                  )!,
                                );
                            }}
                          >
                            <span
                              className={
                                "nudge-icon " +
                                (n.reason === "restock soon" ? "blue" : "amber")
                              }
                            >
                              <Package size={17} />
                            </span>
                            <div>
                              <strong>{n.name}</strong>
                              <small>
                                {n.reason} · {n.on_hand} on hand
                                {n.days_cover !== null
                                  ? ` · ${n.days_cover} days cover`
                                  : ""}
                              </small>
                            </div>
                            <ArrowUpRight size={15} />
                          </button>
                        ))}
                        <button
                          className="text-link"
                          onClick={() => setTab("inventory")}
                        >
                          Review inventory <ArrowRight size={14} />
                        </button>
                      </section>
                    </div>
                  </>
                )}
                {tab === "inventory" && (
                  <>
                    <div className="inventory-summary">
                      <div>
                        <Package size={20} />
                        <span>
                          <strong>
                            {data.inventory.filter((p) => !p.candidate).length}
                          </strong>{" "}
                          stocked catalogue items
                        </span>
                      </div>
                      <div>
                        <Sparkles size={20} />
                        <span>
                          <strong>{data.nudges.length}</strong> checks to review
                        </span>
                      </div>
                      <button className="primary" onClick={openInvoice}>
                        Review sample supplier bill
                      </button>
                    </div>
                    <section className="card">
                      <div className="section-head">
                        <div>
                          <h2>Your inventory ledger</h2>
                          <p>
                            Prices and costs are merchant-supplied fixture
                            inputs
                          </p>
                        </div>
                        <input
                          className="search"
                          aria-label="Search inventory"
                          placeholder="Find a product…"
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                        />
                      </div>
                      <div className="filter-chips" role="group" aria-label="Filter inventory by status">
                        {STOCK_FILTERS.map((f) => (
                          <button
                            key={f.id}
                            className={stockFilter === f.id ? "chip selected" : "chip"}
                            aria-pressed={stockFilter === f.id}
                            onClick={() => setStockFilter(f.id)}
                          >
                            {f.label}
                            <em>{stockCounts[f.id]}</em>
                          </button>
                        ))}
                      </div>
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Product / canonical SKU</th>
                              <th>On hand</th>
                              <th>Sold · {period}</th>
                              <th>Revenue</th>
                              <th>Cover</th>
                              <th title="Units to order to hold 14 days of cover at the latest 7-day rate">
                                Top-up · 14d
                              </th>
                              <th>Status</th>
                              <th />
                            </tr>
                          </thead>
                          <tbody>
                            {visibleStock.length === 0 && (
                              <tr>
                                <td colSpan={8} className="empty-row">
                                  No products match this filter.
                                </td>
                              </tr>
                            )}
                            {visibleStock.map((p) => (
                                <tr key={p.id}>
                                  <td>
                                    <strong>{p.name}</strong>
                                    <small>
                                      {p.id} · {p.family}
                                    </small>
                                  </td>
                                  <td>{p.on_hand}</td>
                                  <td>{p.units}</td>
                                  <td>{money(p.revenue)}</td>
                                  <td>
                                    {p.days_cover === null
                                      ? "—"
                                      : `${p.days_cover}d`}
                                  </td>
                                  <td>
                                    {topups.has(p.name) ? <strong>+{topups.get(p.name)}</strong> : "—"}
                                  </td>
                                  <td>
                                    <Badge health={p.health} />
                                  </td>
                                  <td>
                                    {!p.candidate &&
                                      data.inventory.some(
                                        (x) =>
                                          x.candidate && x.family === p.family,
                                      ) && (
                                        <button
                                          className="proof-button"
                                          onClick={() => prepare(p)}
                                        >
                                          Try replacement{" "}
                                          <ArrowUpRight size={14} />
                                        </button>
                                      )}
                                    {!p.candidate && (
                                      <button
                                        className="proof-button"
                                        onClick={() => {
                                          setPriceDataset("live");
                                          setPriceSku(p.id);
                                          setPriceExternal(null);
                                          setTwinMode("price");
                                          setTab("twin");
                                        }}
                                      >
                                        Change price
                                      </button>
                                    )}
                                    {p.candidate && (
                                      <button
                                        className="proof-button"
                                        onClick={() => fetchPeers(p.id)}
                                      >
                                        Peer evidence
                                      </button>
                                    )}
                                  </td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                      <p className="fine-print">
                        Restock checks use less than 7 days of stock cover under
                        the latest recorded sales rate; a 7-day lead-time/buffer
                        threshold is a demo assumption. Zero sales do not
                        establish zero demand.
                      </p>
                      <ProofButton proof={data.receipt} show={setProof} />
                    </section>
                    {invoice && (
                      <section className="card invoice-card">
                        <div className="section-head">
                          <div>
                            <span className="eyebrow">
                              CACHED SAMPLE EXTRACTION · LIVE OCR NOT CONNECTED
                            </span>
                            <h2>Review supplier invoice</h2>
                            <p>{invoice.source_text}</p>
                          </div>
                          <button
                            aria-label="Close invoice"
                            onClick={() => setInvoice(null)}
                          >
                            <X size={18} />
                          </button>
                        </div>
                        <label>
                          Invoice reference
                          <input
                            aria-label="Invoice reference"
                            value={invoice.invoice_id}
                            onChange={(e) =>
                              setInvoice({
                                ...invoice,
                                invoice_id: e.target.value,
                              })
                            }
                          />
                        </label>
                        {invoice.lines.map((l, i) => (
                          <div className="invoice-line" key={i}>
                            <label>
                              Canonical product
                              <select
                                aria-label="Invoice product"
                                value={l.product}
                                onChange={(e) =>
                                  setInvoice({
                                    ...invoice,
                                    lines: invoice.lines.map((r, j) =>
                                      j === i
                                        ? { ...r, product: e.target.value }
                                        : r,
                                    ),
                                  })
                                }
                              >
                                {data.inventory.map((p) => (
                                  <option key={p.id} value={p.id}>
                                    {p.name}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label>
                              Quantity
                              <input
                                aria-label="Invoice quantity"
                                type="number"
                                min={1}
                                max={500}
                                value={l.quantity}
                                onChange={(e) =>
                                  setInvoice({
                                    ...invoice,
                                    lines: invoice.lines.map((r, j) =>
                                      j === i
                                        ? {
                                            ...r,
                                            quantity: Number(e.target.value),
                                          }
                                        : r,
                                    ),
                                  })
                                }
                              />
                            </label>
                            <label>
                              Unit cost
                              <input
                                aria-label="Invoice unit cost"
                                type="number"
                                min={0}
                                value={l.unit_cost}
                                onChange={(e) =>
                                  setInvoice({
                                    ...invoice,
                                    lines: invoice.lines.map((r, j) =>
                                      j === i
                                        ? {
                                            ...r,
                                            unit_cost: Number(e.target.value),
                                          }
                                        : r,
                                    ),
                                  })
                                }
                              />
                            </label>
                          </div>
                        ))}
                        <p className="fine-print">{invoice.note}</p>
                        <button
                          className="primary"
                          disabled={busy || imported}
                          onClick={confirmInvoice}
                        >
                          {imported ? (
                            <>
                              <Check size={16} /> Imported into simulated
                              inventory
                            </>
                          ) : (
                            "Confirm quantities & import"
                          )}
                        </button>
                      </section>
                    )}
                  </>
                )}
                {tab === "twin" && (
                  <>
                    <div className="mode-switch" role="group" aria-label="Digital twin mode">
                      <button
                        className={twinMode === "swap" ? "selected" : ""}
                        aria-pressed={twinMode === "swap"}
                        onClick={() => setTwinMode("swap")}
                      >
                        Swap a product
                      </button>
                      <button
                        className={twinMode === "price" ? "selected" : ""}
                        aria-pressed={twinMode === "price"}
                        onClick={() => setTwinMode("price")}
                      >
                        Change a price
                      </button>
                    </div>
                    {twinMode === "price" ? (
                      <PricePanel
                        mid={mid}
                        dataset={priceDataset}
                        setDataset={setPriceDataset}
                        focusSku={priceSku}
                        external={priceExternal}
                        show={setProof}
                      />
                    ) : (
                      <>
                    <section className="twin-banner">
                      <FlaskConical size={24} />
                      <div>
                        <strong>A small change. A measurable trade-off.</strong>
                        <p>
                          Same bill opportunities in both worlds. Choice, stock
                          and substitution change together.
                        </p>
                      </div>
                      <span>CONDITIONAL SCENARIO</span>
                    </section>
                    <section className="card trial-form">
                      <div className="section-head">
                        <div>
                          <h2>Build your assortment trial</h2>
                          <p>
                            Existing product → compatible new item, within your
                            inventory budget
                          </p>
                        </div>
                      </div>
                      <div className="trial-fields">
                        <label>
                          Remove from assortment
                          <select
                            aria-label="Remove product"
                            value={remove}
                            onChange={(e) => {
                              const p = data.inventory.find(
                                (p) => p.id === e.target.value,
                              )!;
                              prepare(p);
                            }}
                          >
                            {data.inventory
                              .filter(
                                (p) =>
                                  !p.candidate &&
                                  data.inventory.some(
                                    (x) => x.candidate && x.family === p.family,
                                  ),
                              )
                              .map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.name}
                                </option>
                              ))}
                          </select>
                        </label>
                        <span className="field-arrow">
                          <ArrowRight size={20} />
                        </span>
                        <label>
                          Introduce in its place
                          <select
                            aria-label="Replacement product"
                            value={replace}
                            onChange={(e) => {
                              setReplace(e.target.value);
                              setTrial(null);
                              setRanked([]);
                            }}
                          >
                            {options.map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.name}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                      <div className="trial-parameters">
                        <label>
                          Trial stock / portions
                          <input
                            aria-label="Trial quantity"
                            type="number"
                            min={1}
                            max={500}
                            value={quantity}
                            onChange={(e) => {
                              setQuantity(Number(e.target.value));
                              setTrial(null);
                              setRanked([]);
                            }}
                          />
                        </label>
                        <label>
                          Inventory budget (₹)
                          <input
                            aria-label="Trial budget"
                            type="number"
                            min={0}
                            value={budget}
                            onChange={(e) => {
                              setBudget(Number(e.target.value));
                              setTrial(null);
                              setRanked([]);
                            }}
                          />
                        </label>
                        <label>
                          Test horizon
                          <select
                            aria-label="Trial horizon"
                            value={horizon}
                            onChange={(e) => {
                              setHorizon(Number(e.target.value));
                              setTrial(null);
                              setRanked([]);
                            }}
                          >
                            <option value={7}>7 days</option>
                            <option value={14}>14 days</option>
                            <option value={30}>30 days</option>
                          </select>
                        </label>
                        <div className="quote">
                          <small>SUPPLIED MERCHANT QUOTE</small>
                          <strong>
                            {money((candidate?.cost || 0) * quantity)}
                          </strong>
                          <span>
                            {money(candidate?.price || 0)} price ·{" "}
                            {money(candidate?.cost || 0)} cost / unit
                          </span>
                        </div>
                      </div>
                      <div className="trial-actions">
                        <button
                          className="primary"
                          disabled={busy || !replace}
                          onClick={() => run()}
                        >
                          <FlaskConical size={17} />
                          {busy ? "Calculating…" : "Run on digital twin"}
                        </button>
                        <button
                          className="secondary"
                          disabled={busy || !remove}
                          onClick={() => run(true)}
                        >
                          Find the best replacement <Sparkles size={16} />
                        </button>
                        <button
                          className="text-link"
                          disabled={busy || !replace}
                          onClick={() => fetchPeers()}
                        >
                          Inspect lookalikes <ArrowUpRight size={15} />
                        </button>
                      </div>
                    </section>
                    {ranked.length > 0 && (
                      <section className="card">
                        <div className="section-head">
                          <div>
                            <h2>Eligible replacement trials</h2>
                            <p>
                              Ranked by P10 incremental revenue · current budget
                              and quantity
                            </p>
                          </div>
                        </div>
                        {ranked.map((r, i) => (
                          <button
                            key={r.replace_id}
                            className={
                              "ranking-row " +
                              (trial?.replace_id === r.replace_id
                                ? "chosen"
                                : "")
                            }
                            onClick={() => {
                              setTrial(r);
                              setReplace(r.replace_id);
                            }}
                          >
                            <span className="rank-number">{i + 1}</span>
                            <div>
                              <strong>{r.replace}</strong>
                              <small>
                                {r.p10 > 0
                                  ? "Positive modeled conservative change"
                                  : "No positive conservative uplift; consider holding assortment"}
                              </small>
                            </div>
                            <span>
                              {money(r.incremental_revenue)}
                              <small>P10 {money(r.p10)}</small>
                            </span>
                            <ArrowRight size={17} />
                          </button>
                        ))}
                      </section>
                    )}
                    {trial ? (
                      <TrialResult trial={trial} show={setProof} />
                    ) : (
                      <section className="empty-state">
                        <div className="empty-icon">
                          <FlaskConical size={30} />
                        </div>
                        <h2>Your next idea belongs here.</h2>
                        <p>
                          Choose an existing product and a replacement, or ask
                          Pi which candidate deserves a small trial.
                        </p>
                        <div>
                          <span>
                            <Check size={14} /> Substitution included
                          </span>
                          <span>
                            <Check size={14} /> Availability constrained
                          </span>
                          <span>
                            <Check size={14} /> Math attached
                          </span>
                        </div>
                      </section>
                    )}
                      </>
                    )}
                  </>
                )}
                {tab === "peers" && (
                  <>
                    <section className="card">
                      <div className="section-head">
                        <div>
                          <h2>Lookalikes for the decision at hand</h2>
                          <p>
                            Only billing-integrated shops with compatible
                            product identity and availability
                          </p>
                        </div>
                      </div>
                      <div className="peer-controls">
                        <select
                          aria-label="Peer product"
                          value={replace}
                          onChange={(e) => {
                            setReplace(e.target.value);
                            setPeer(null);
                          }}
                        >
                          {data.inventory.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                        <button
                          className="primary"
                          disabled={busy}
                          onClick={() => fetchPeers()}
                        >
                          Find eligible lookalikes
                        </button>
                      </div>
                      <div className="pipeline">
                        <span>Canonical SKU</span>
                        <ArrowRight size={15} />
                        <span>Same-type category peers</span>
                        <ArrowRight size={15} />
                        <span>Availability eligibility</span>
                        <ArrowRight size={15} />
                        <span>Weighted demand evidence</span>
                      </div>
                    </section>
                    {peer && (
                      <>
                        <div className="metrics peer-metrics">
                          <div className="metric">
                            <span>Aggregate donors</span>
                            <strong>{peer.peer_count}</strong>
                            <small>
                              {peer.eligible_count} eligible · same business
                              type
                            </small>
                          </div>
                          <div className="metric">
                            <span>Effective peers</span>
                            <strong>{peer.effective_peers}</strong>
                            <small>1 / sum of squared normalized weights</small>
                          </div>
                          <div className="metric">
                            <span>Peer recorded rate</span>
                            <strong>
                              {peer.peer_rate_per_100_bills.toFixed(1)}
                              <em> / 100</em>
                            </strong>
                            <small>
                              Units per available bill opportunities
                            </small>
                          </div>
                          <div className="metric">
                            <span>Mapping confidence</span>
                            <strong>
                              {Math.round(peer.mapping_confidence * 100)}%
                            </strong>
                            <small>
                              Curated synthetic identity · packs preserved
                            </small>
                          </div>
                        </div>
                        <section className="card">
                          <div className="section-head">
                            <div>
                              <h2>{peer.name}</h2>
                              <p>
                                {peer.family} · {peer.window.join(" → ")}
                              </p>
                            </div>
                            <ProofButton proof={peer.receipt} show={setProof} />
                          </div>
                          <div className="two-col">
                            <div>
                              <h3>Evidence that can transfer</h3>
                              <ul className="plain-list">
                                <li>
                                  Category-level assortment and demand patterns
                                </li>
                                <li>
                                  Recorded units adjusted for known offer
                                  exposure
                                </li>
                                <li>
                                  Shrunken new-item rate with posterior
                                  uncertainty
                                </li>
                              </ul>
                              <div className="evidence-stat">
                                Posterior rate:{" "}
                                <strong>{(peer.rate * 100).toFixed(2)}</strong>{" "}
                                units / 100 bills
                                <br />
                                <small>
                                  P10 {(peer.rate_p10 * 100).toFixed(2)} · P90{" "}
                                  {(peer.rate_p90 * 100).toFixed(2)} · local
                                  exposure {peer.local_exposure}
                                </small>
                              </div>
                            </div>
                            <div>
                              <h3>Inputs supplied by this merchant</h3>
                              <ul className="plain-list">
                                <li>
                                  Prices, landed costs, inventory cash and stock
                                </li>
                                <li>
                                  Recipe ingredient allocation for restaurant
                                  trials
                                </li>
                                <li>
                                  Outside-option sensitivity and fixed bill
                                  schedule
                                </li>
                              </ul>
                              <p className="fine-print">
                                No donor identity, individual bill, inferred
                                demographic, or assumed facility is exposed.
                                Cohorts smaller than 10 abstain.
                              </p>
                            </div>
                          </div>
                        </section>
                      </>
                    )}
                    <section className="card identity-note">
                      <Layers size={21} />
                      <div>
                        <h3>
                          Same product ≠ same family ≠ an interchangeable
                          substitute.
                        </h3>
                        <p>
                          Exact curated aliases identify the SKU. Pack size and
                          variant remain distinct. Family eligibility narrows
                          the scenario; preference transfer remains an explicit
                          modeling assumption.
                        </p>
                      </div>
                    </section>
                  </>
                )}
                {tab === "decisions" && (
                  <DecisionLab
                    mid={mid}
                    feed={feed}
                    show={setProof}
                    go={(t, f) => {
                      setTab(t);
                      if (f) setStockFilter(f);
                    }}
                    ask={(q) => send(q)}
                  />
                )}
                {tab === "proof" && (
                  <>
                    <section className="card">
                      <div className="section-head">
                        <div>
                          <h2>What this demo knows</h2>
                          <p>
                            2025-10-03 → 2026-10-02 · 365 days · seven business
                            types
                          </p>
                        </div>
                        <ShieldCheck size={22} />
                      </div>
                      <div className="two-col">
                        <div>
                          <h3>Recorded synthetic evidence</h3>
                          <ul className="plain-list">
                            <li>
                              POS bill, canonical SKU, units, price, cost and
                              timestamp
                            </li>
                            <li>
                              Stock arrivals and per-bill availability exposure
                            </li>
                            <li>
                              Basket categories and optional pseudonymous
                              loyalty IDs
                            </li>
                            <li>
                              Restaurant recipes and allocated ingredient
                              snapshot
                            </li>
                          </ul>
                        </div>
                        <div>
                          <h3>Clearly named assumptions</h3>
                          <ul className="plain-list">
                            <li>
                              Fixed completed-bill schedule and outside option
                            </li>
                            <li>
                              Peer exchangeability and proportional substitution
                            </li>
                            <li>
                              No replenishment or disposal in replacement trials
                            </li>
                            <li>
                              Gross contribution excludes overhead and taxes
                            </li>
                          </ul>
                        </div>
                      </div>
                      <p className="fine-print">
                        Hypermarket, restaurant, apparel, kirana, pharmacy,
                        bakery and electronics are selectable. Pharmacy data
                        supports a retail inventory demo; it does not recommend
                        medical substitutions.
                      </p>
                    </section>
                    <section className="card">
                      <h2>Integration status</h2>
                      {[
                        [
                          "POS / Paytm",
                          "SIMULATED",
                          "Generated bill-level data, not a real Paytm connection.",
                        ],
                        [
                          "Sarvam STT + TTS",
                          meta?.voice?.enabled
                            ? "CONFIGURED"
                            : "OFFLINE BY DEFAULT",
                          "Server-side speech adapters. Paid calls occur only after a voice button is used.",
                        ],
                        [
                          "Pi agent (tool calling)",
                          meta?.agent?.enabled ? "SARVAM LIVE" : "LOCAL ROUTER",
                          "The agent only picks a tool; the tool reads the POS and the app writes the numbers. Without a Sarvam key a labelled keyword router stands in.",
                        ],
                        [
                          "Insight tools",
                          "SCHEDULED",
                          `Overview cards and chat call the same tools. Refreshed every ${Math.round((meta?.insight_refresh_seconds || 900) / 60)} min and on demand.`,
                        ],
                        [
                          "Supplier-bill OCR",
                          "CACHED SAMPLE",
                          "Editable sample extraction + explicit, idempotent inventory import. Live OCR is not connected.",
                        ],
                        [
                          "Model results",
                          "CONDITIONAL",
                          "Assumption-based scenarios with receipts; no calibrated causal uplift claim.",
                        ],
                      ].map((row) => (
                        <div className="status-row" key={row[0]}>
                          <div>
                            <strong>{row[0]}</strong>
                            <p>{row[2]}</p>
                          </div>
                          <span className="badge neutral">{row[1]}</span>
                        </div>
                      ))}
                    </section>
                    <section className="card">
                      <h2>Why seven shop types?</h2>
                      <p>
                        Besides your hypermarket, apparel and restaurant
                        examples, kirana adds frequent essential baskets,
                        pharmacy adds pack-sensitive identity, bakery adds
                        short-life inventory, and electronics adds
                        low-frequency, high-ticket demand.
                      </p>
                      <p className="fine-print">
                        Expiry and medical suitability are not inferred from
                        bills. Those need additional stock-batch and
                        product-policy inputs before broader production
                        decisions.
                      </p>
                    </section>
                  </>
                )}
                <footer className="workspace-footer">
                  <ShieldCheck size={13} /> Synthetic data. Conditional
                  forecasts. A receipt for every decision.
                  <span>Calculate. Explain. Decide.</span>
                </footer>
              </>
            )}
          </main>
          <aside className="chat-panel">
            <div className="chat-header">
              <span className="spark-icon">
                <Sparkles size={18} />
              </span>
              <div>
                <h2>Ask Pi</h2>
                <p>Your shop’s thinking partner</p>
              </div>
              <span className="live-dot" />
            </div>
            <div className="chat-context">
              <span>
                <i /> Grounded in your POS
              </span>
              <small>
                {data?.name || "Loading…"} · {period}
              </small>
            </div>
            <div className="conversation" ref={conversation}>
              {messages.map((m, i) => (
                <div className={"message " + m.role} key={i}>
                  {m.role === "assistant" && (
                    <div className="assistant-label">
                      <Sparkles size={12} /> PI{" "}
                      {m.tool && <span>{m.tool}</span>}
                    </div>
                  )}
                  <p>{m.text}</p>
                  {m.provider && (
                    <details className="fine-print">
                      <summary>Answer evidence</summary>
                      <p>{m.provider}</p>
                      {m.trace?.map((t, j) => <p key={j}>{t.tool || "Planner"}: {t.status}</p>)}
                      {m.translation && <p>{m.translation}</p>}
                      {m.canonical !== m.text && <p>Canonical answer: {m.canonical}</p>}
                    </details>
                  )}
                  {m.role === "assistant" && m.proof && (
                    <div className="message-actions">
                      <ProofButton
                        proof={m.proof}
                        show={setProof}
                        label="Calculation receipt"
                      />
                      <button
                        aria-label="Read answer aloud"
                        onClick={() => speak(m.text, m.language)}
                      >
                        <Volume2 size={14} />
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {busy && (
                <div className="thinking">
                  <span />
                  <span />
                  <span /> Reading the evidence
                </div>
              )}
            </div>
            <div className="chat-bottom">
              <span className="suggestion-label">TRY ASKING</span>
              <div className="suggestions">
                <button
                  disabled={busy}
                  onClick={() =>
                    send("Give me a sales and customer overview for today")
                  }
                >
                  How did today go? <ArrowUpRight size={13} />
                </button>
                <button disabled={busy} onClick={() => send(promptReplace)}>
                  What should replace my dead stock? <ArrowUpRight size={13} />
                </button>
              </div>
              <form
                className="composer"
                onSubmit={(e) => {
                  e.preventDefault();
                  send();
                }}
              >
                <textarea
                  aria-label="Ask Pi"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Ask about sales, stock, or a what-if…"
                  rows={2}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <div>
                  <button
                    type="button"
                    className={recording ? "mic recording" : "mic"}
                    aria-label={
                      recording
                        ? "Stop voice recording"
                        : "Start voice recording"
                    }
                    onClick={startVoice}
                  >
                    {recording ? <Square size={16} /> : <Mic size={17} />}
                  </button>
                  <select
                    aria-label="Voice language"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                  >
                    <option value="unknown">Auto detect</option>
                    <option value="en-IN">English</option>
                    <option value="hi-IN">हिन्दी</option>
                    <option value="mr-IN">मराठी</option>
                    <option value="bn-IN">বাংলা</option>
                    <option value="gu-IN">ગુજરાતી</option>
                    <option value="kn-IN">ಕನ್ನಡ</option>
                    <option value="ml-IN">മലയാളം</option>
                    <option value="od-IN">ଓଡ଼ିଆ</option>
                    <option value="pa-IN">ਪੰਜਾਬੀ</option>
                    <option value="ta-IN">தமிழ்</option>
                    <option value="te-IN">తెలుగు</option>
                  </select>
                  <button
                    className="send"
                    aria-label="Send question"
                    disabled={busy || !text.trim()}
                  >
                    <Send size={15} />
                  </button>
                </div>
              </form>
              {voiceStatus && (
                <p className="voice-status" role="status">
                  {voiceStatus}
                </p>
              )}
              <p className="chat-foot">
                <ShieldCheck size={11} /> Models route. Tools calculate. You
                decide.
              </p>
            </div>
          </aside>
        </div>
      </div>
      <ReceiptDialog open={!!proof} onClose={() => setProof(null)}>
        {proof && (
          <>
            <div className="section-head">
              <div>
                <span className="eyebrow">
                  TIER {proof.data_tier} · SIMULATED DATA
                </span>
                <h2>Calculation receipt</h2>
              </div>
              <button
                aria-label="Close calculation"
                onClick={() => setProof(null)}
              >
                <X size={20} />
              </button>
            </div>
            <h3>The formula</h3>
            <p className="formula">{proof.formula_text}</p>
            <h3>What went in</h3>
            <pre>{JSON.stringify(proof.inputs, null, 2)}</pre>
            <h3>Assumptions & limits</h3>
            <ul>
              {proof.assumptions.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
            <details>
              <summary>Computed output and evidence</summary>
              <pre>{JSON.stringify(proof.output, null, 2)}</pre>
            </details>
            <div className="receipt-flags">
              {proof.data_quality_flags.join(" · ")}
            </div>
          </>
        )}
      </ReceiptDialog>
    </div>
  );
}
function TrialResult({
  trial: t,
  show,
}: {
  trial: Trial;
  show: (p: Proof) => void;
}) {
  return (
    <>
      <section className="trial-result">
        <div className="result-head">
          <div>
            <span className="eyebrow">{t.horizon}-DAY ASSORTMENT SCENARIO</span>
            <h2>
              {t.remove} <ArrowRight size={17} /> {t.replace}
            </h2>
          </div>
          <ProofButton proof={t.receipt} show={show} label="Show the math" />
        </div>
        <div className="result-stats">
          <div>
            <span>Modeled incremental revenue</span>
            <strong className={t.incremental_revenue < 0 ? "negative" : ""}>
              {t.incremental_revenue > 0 ? "+" : ""}
              {money(t.incremental_revenue)}
            </strong>
            <small>
              P10 {money(t.p10)} → P90 {money(t.p90)}
            </small>
          </div>
          <div>
            <span>Incremental contribution</span>
            <strong>{money(t.incremental_contribution)}</strong>
            <small>After supplied unit costs</small>
          </div>
          <div>
            <span>Upfront purchase cash</span>
            <strong>{money(t.purchase_cost)}</strong>
            <small>
              {t.quantity} units · {t.peer_count} peer donors
            </small>
          </div>
        </div>
        <p className="result-verdict">
          {t.sensitivity.some((s) => s.incremental_revenue < 0) &&
          t.sensitivity.some((s) => s.incremental_revenue > 0)
            ? "Sensitivity changes the sign. Review the assumptions and compare a small trial with holding the current assortment."
            : t.p10 > 0
              ? "Worth considering as a small, measured trial."
              : "The conservative estimate does not establish an uplift. Review cannibalization and consider holding the current assortment."}
        </p>
      </section>
      <section className="card">
        <div className="section-head">
          <div>
            <h2>Two possible weeks, one starting point</h2>
            <p>
              Cumulative family revenue · same {t.opportunities} completed-bill
              opportunities
            </p>
          </div>
          <span className="badge neutral">{t.paths} paired paths</span>
        </div>
        <div className="chart">
          <ResponsiveContainer>
            <LineChart data={t.chart}>
              <CartesianGrid vertical={false} stroke="#e9edf3" />
              <XAxis
                dataKey="day"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `Day ${v}`}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tickFormatter={short}
                width={50}
                tick={{ fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip formatter={(v) => money(Number(v))} />
              <Legend />
              <Line
                name="Current assortment"
                dataKey="baseline"
                stroke="#a0adbf"
                strokeDasharray="5 4"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                name="Replacement trial"
                dataKey="scenario"
                stroke="#2463ed"
                strokeWidth={3}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
      <div className="two-col">
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Substitution, made explicit</h2>
              <p>Replacing one item changes the whole family</p>
            </div>
          </div>
          {t.products.map((p) => (
            <div className="substitution-row" key={p.name}>
              <div>
                <strong>{p.name}</strong>
                <small>
                  {p.baseline_units} → {p.scenario_units} modeled units
                </small>
              </div>
              <span className={p.revenue_delta < 0 ? "negative" : "positive"}>
                {p.revenue_delta > 0 ? "+" : ""}
                {money(p.revenue_delta)}
              </span>
            </div>
          ))}
        </section>
        <section className="card">
          <h2>The downside deserves a look.</h2>
          <div className="risk-row">
            <span>Model probability of revenue loss</span>
            <strong>{(t.probability_revenue_loss * 100).toFixed(1)}%</strong>
          </div>
          <div className="risk-row">
            <span>Expected unsold candidate at cost</span>
            <strong>{money(t.unsold_candidate_value)}</strong>
          </div>
          <div className="risk-row">
            <span>Extra cash after candidate purchase</span>
            <strong>{money(t.incremental_cash_after_purchase)}</strong>
          </div>
          <h3>Outside-option sensitivity</h3>
          {t.sensitivity.map((s) => (
            <div className="risk-row" key={s.outside_factor}>
              <span>{s.outside_factor}× assumed no-purchase weight</span>
              <strong>{money(s.incremental_revenue)}</strong>
            </div>
          ))}
          <p className="fine-print">
            Outside-option demand is not identified from bills. These are
            alternative assumptions, not observed outcomes or causal forecasts.
          </p>
        </section>
      </div>
      {t.ingredient_remaining.length > 0 && (
        <section className="card">
          <h2>Recipe constraints are part of the restaurant twin.</h2>
          <p>
            Every sold dish consumes its supplied recipe. Shared ingredients can
            constrain or displace another dish.
          </p>
          <div className="ingredient-grid">
            {t.ingredient_remaining
              .filter((i) =>
                ["rice", "paneer", "vegetables", "batter"].includes(
                  i.ingredient,
                ),
              )
              .map((i) => (
                <div key={i.ingredient}>
                  <span>{i.ingredient}</span>
                  <strong>{i.scenario_kg} kg</strong>
                  <small>{i.baseline_kg} kg baseline remaining</small>
                </div>
              ))}
          </div>
          <p className="fine-print">
            The ingredient snapshot is allocated to this family trial; no future
            replenishment or other-category ingredient consumption is assumed.
          </p>
        </section>
      )}
      <div className="scenario-limit">
        <ShieldCheck size={16} />
        <p>
          This is a conditional model scenario, not guaranteed uplift. Peer
          exchangeability, the choice model and a fixed bill schedule are
          assumptions. Use a small trial to learn before scaling.
        </p>
      </div>
    </>
  );
}
type PaymentsOnly = {
  window: string[];
  chart: { label: string; revenue: number }[];
  last7: number;
  prior7: number;
  change_fraction: number;
  change_direction: "up" | "down";
  payments_7d: number;
  busiest_day: string;
  busiest_day_avg: number;
  quietest_day: string;
  quietest_day_avg: number;
  peak_hours: { hour: string; share_fraction: number }[];
  outlook: { expected: number; low: number; high: number };
  capabilities: { id: string; label: string; needs: string; available: boolean }[];
  receipt: Proof;
};
function DecisionLab({
  mid,
  feed,
  show,
  go,
  ask,
}: {
  mid: string;
  feed: InsightFeed | null;
  show: (p: Proof) => void;
  go: (tab: string, stockFilter?: string) => void;
  ask: (q: string) => void;
}) {
  const [tier, setTier] = useState<"A" | "B">("A");
  const [pay, setPay] = useState<PaymentsOnly | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setPay(null);
    setFailed(false);
    api(`/v2/payments-only/${mid}`)
      .then(setPay)
      .catch(() => setFailed(true));
  }, [mid]);
  const caps = pay?.capabilities || [];
  const open = caps.filter((c) => c.available).length;
  const insight = (id: string) => feed?.insights.find((i) => i.id === id);
  const queue = [
    { id: "restock", icon: Package, action: "Open replenish list", run: () => go("inventory", "replenish") },
    { id: "dead_shelf", icon: Package, action: "Try a replacement", run: () => go("twin") },
    { id: "falling", icon: ArrowDownRight, action: "Ask Pi why", run: () => ask("Which product is losing traction?") },
  ]
    .map((q) => ({ ...q, item: insight(q.id) }))
    .filter((q) => q.item && q.item.tone !== "info");
  return (
    <>
      <section className="card tier-card">
        <div className="section-head">
          <div>
            <h2>What can Pi decide with your data?</h2>
            <p>
              Many shops share only payments (QR, soundbox). Pick what Pi can see to preview what it can and cannot do.
            </p>
          </div>
        </div>
        <div className="tier-switch" role="group" aria-label="Data Pi can see">
          <button className={tier === "A" ? "selected" : ""} aria-pressed={tier === "A"} onClick={() => setTier("A")}>
            <strong>Payments only</strong>
            <small>Amount and time of each payment</small>
          </button>
          <button className={tier === "B" ? "selected" : ""} aria-pressed={tier === "B"} onClick={() => setTier("B")}>
            <strong>Item-level bills</strong>
            <small>Products, quantities, costs, stock, loyalty IDs</small>
          </button>
        </div>
      </section>
      {failed && <div className="error">Could not read payments for this shop. Please retry.</div>}
      {tier === "A" && (
        <>
          <div className="limited-banner" role="note">
            <Lock size={18} />
            <div>
              <strong>Limited view · payments only</strong>
              <p>
                Pi can read takings, timing and trend. It cannot tell which products sell, what is running low, or who
                comes back for what, so it will not guess. {open} of {caps.length || 8} insights are available.
              </p>
            </div>
          </div>
          {pay && (
            <>
              <div className="metrics three">
                <div className="metric">
                  <span>
                    Takings, last 7 days <BarChart3 size={15} />
                  </span>
                  <strong>{money(pay.last7)}</strong>
                  <small>
                    {pay.change_direction === "up" ? "Up" : "Down"} {(pay.change_fraction * 100).toFixed(1)}% on the
                    week before ({money(pay.prior7)})
                  </small>
                </div>
                <div className="metric">
                  <span>
                    Payments, last 7 days <Wallet size={15} />
                  </span>
                  <strong>{pay.payments_7d}</strong>
                  <small>Counts payments, not visitors</small>
                </div>
                <div className="metric">
                  <span>
                    Busiest weekday <Activity size={15} />
                  </span>
                  <strong>{pay.busiest_day}</strong>
                  <small>
                    {money(pay.busiest_day_avg)} a day · quietest is {pay.quietest_day} ({money(pay.quietest_day_avg)})
                  </small>
                </div>
              </div>
              <section className="card">
                <div className="section-head">
                  <div>
                    <h2>Daily takings, last 28 days</h2>
                    <p>Sum of payment amounts per day</p>
                  </div>
                  <ProofButton proof={pay.receipt} show={show} />
                </div>
                <RevenueChart data={pay.chart} />
              </section>
              <div className="two-col">
                <section className="card">
                  <div className="section-head">
                    <div>
                      <h2>When customers pay</h2>
                      <p>Busiest hours by share of takings, last 28 days</p>
                    </div>
                  </div>
                  {pay.peak_hours.map((h) => (
                    <div className="profile-row" key={h.hour}>
                      <div>
                        <span>{h.hour}</span>
                        <small>{(h.share_fraction * 100).toFixed(1)}% of takings</small>
                      </div>
                      <div className="profile-bar">
                        <i style={{ width: Math.min(100, h.share_fraction * 100 * 6) + "%" }} />
                      </div>
                    </div>
                  ))}
                  <p className="fine-print">Use it to schedule staff and cash handling, not to plan stock.</p>
                </section>
                <section className="card">
                  <div className="section-head">
                    <div>
                      <h2>Next 7 days: expected inflow</h2>
                      <p>Repeats the last 4 same weekdays</p>
                    </div>
                  </div>
                  <div className="outlook">
                    <strong>{money(pay.outlook.expected)}</strong>
                    <small>
                      Likely between {money(pay.outlook.low)} and {money(pay.outlook.high)} (one standard deviation)
                    </small>
                  </div>
                  <p className="fine-print">
                    Does not know about festivals, promotions or stock-outs. Useful for planning payouts, not
                    purchases.
                  </p>
                </section>
              </div>
            </>
          )}
          <section className="card">
            <div className="section-head">
              <div>
                <h2>What payments alone cannot answer</h2>
                <p>Each locked item names the data that would unlock it</p>
              </div>
            </div>
            <div className="capability-grid">
              {caps.map((c) => (
                <div className={c.available ? "capability open" : "capability locked"} key={c.id}>
                  {c.available ? <Check size={16} /> : <Lock size={16} />}
                  <div>
                    <strong>{c.label}</strong>
                    <small>{c.available ? "Available now" : `Needs ${c.needs.toLowerCase()}`}</small>
                  </div>
                </div>
              ))}
            </div>
            <button className="primary" onClick={() => setTier("B")}>
              See what item-level bills unlock <ArrowRight size={14} />
            </button>
          </section>
        </>
      )}
      {tier === "B" && (
        <>
          <section className="card">
            <div className="section-head">
              <div>
                <h2>Decisions waiting for you</h2>
                <p>Built from Pi insight tools · each one opens its evidence</p>
              </div>
            </div>
            {!feed && <p className="fine-print">Running insight tools…</p>}
            {feed && queue.length === 0 && <p className="fine-print">Nothing urgent. Every shelf is moving and stock is healthy.</p>}
            {queue.map(({ id, icon: Icon, item, action, run }) => (
              <div className="decision-row" key={id}>
                <span className="nudge-icon amber">
                  <Icon size={17} />
                </span>
                <div>
                  <strong>{item!.title}: {item!.headline}</strong>
                  <small>{item!.detail}</small>
                </div>
                <button className="secondary" onClick={() => show(item!.receipt)}>
                  Evidence
                </button>
                <button className="primary" onClick={run}>
                  {action}
                </button>
              </div>
            ))}
          </section>
          <section className="card">
            <div className="section-head">
              <div>
                <h2>Everything item-level bills unlock</h2>
                <p>With products, costs and stock on every bill, all of these run on your own data</p>
              </div>
            </div>
            <div className="capability-grid">
              {caps.map((c) => (
                <div className="capability open" key={c.id}>
                  <Check size={16} />
                  <div>
                    <strong>{c.label}</strong>
                    <small>{c.needs}</small>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </>
  );
}
