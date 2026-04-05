import { useCallback, useEffect, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";

type CategoryRow = {
  id: string;
  direction: number;
  confidence: number | null;
  raw_score: number | null;
  title: string;
  subtitle: string;
  detail: string;
};

type SignalLeg = {
  id: string;
  category: string;
  label: string;
  raw_score: number | null;
  direction: number;
};

type StrategyMeta = {
  source: string;
  tuning_run_dir: string | null;
  tuning_run_name: string | null;
  use_latest_tuning: boolean;
};

type Latest = {
  date: string;
  consensus: { direction: number; confidence: number | null };
  categories: CategoryRow[];
  signal_legs?: SignalLeg[];
  warnings: string[];
  strategy?: StrategyMeta;
};

type SharpeMethodology = {
  oos_trading_days_per_window: number;
  is_trading_days_per_window: number;
  step_trading_days: number;
  mean_oos_sharpe: string;
  full_sample_sharpe: string;
  why_they_differ: string;
};

type WfStep = {
  oos_sharpe: number;
  oos_start: string;
  oos_end?: string;
  is_sharpe?: number;
  oos_sharpe_long_only?: number | null;
  is_sharpe_long_only?: number | null;
  oos_sharpe_buy_hold?: number | null;
  is_sharpe_buy_hold?: number | null;
};

type BacktestLane = {
  walk_forward: {
    n_steps: number;
    mean_oos_sharpe: number | null;
    steps: WfStep[];
  };
  sharpe_full_sample: number | null;
  total_return_pct: number;
  direction_mix_pct: { long: number; short: number; neutral: number };
  equity_tail_rebased: { d: string; e: number }[];
};

type CategoryBacktest = BacktestLane & { long_only?: BacktestLane };

/** XAUUSD buy & hold vs same calendar; `equity_tail_rebased_sub` matches per-signal chart density. */
type BuyHoldComparison = BacktestLane & {
  equity_tail_rebased_sub?: { d: string; e: number }[];
};

type EquityMeta = {
  chart_first_date: string | null;
  chart_last_date: string | null;
  panel_start: string | null;
  panel_end: string | null;
  n_points: number;
  n_bars_full: number;
  wf_first_oos: string | null;
  hint: string;
};

type SubsignalBacktest = {
  id: string;
  label: string;
  category: string;
} & BacktestLane & { long_only?: BacktestLane };

type ReturnStatsLane = {
  annualized_sharpe: number | null;
  total_return_pct: number | null;
  max_drawdown_pct: number | null;
  volatility_annualized: number | null;
  hit_ratio_all_days_pct: number | null;
  hit_ratio_active_days_pct?: number | null;
  trading_days: number;
  active_trading_days?: number;
};

type VersusBhDaily = {
  pct_days_strategy_return_gt_benchmark: number | null;
  correlation: number | null;
  days_compared: number;
};

type OosVsBuyHold = {
  oos_steps_compared: number;
  oos_sharpe_beat_buy_hold_count: number;
  oos_sharpe_beat_buy_hold_pct: number | null;
  oos_long_only_steps_compared: number;
  oos_long_only_sharpe_beat_buy_hold_count: number;
  oos_long_only_sharpe_beat_buy_hold_pct: number | null;
};

type FullSampleStatsBundle = {
  consensus_long_short: ReturnStatsLane;
  consensus_long_only: ReturnStatsLane;
  buy_hold_xauusd: ReturnStatsLane;
  versus_buy_hold_daily: VersusBhDaily;
};

type Wf = {
  walk_forward: {
    n_steps: number;
    mean_oos_sharpe: number | null;
    mean_oos_sharpe_long_only?: number | null;
    mean_oos_sharpe_buy_hold?: number | null;
    steps: WfStep[];
    truncated?: boolean;
    steps_in_payload?: number;
    oos_vs_buy_hold?: OosVsBuyHold;
    wf_is_days?: number;
    wf_oos_days?: number;
    wf_step_days?: number;
    sharpe_methodology?: SharpeMethodology;
  };
  full_sample_stats?: FullSampleStatsBundle;
  equity_curve_tail: { d: string; s: number; b: number; l: number }[];
  strategy_equity_end_long_only?: number | null;
  buy_hold_backtest?: BuyHoldComparison;
  equity_meta?: EquityMeta;
  category_backtests?: Record<string, CategoryBacktest>;
  subsignal_backtests?: Record<string, SubsignalBacktest>;
};

const dirLabel = (d: number) =>
  d === 1 ? "Long" : d === -1 ? "Short" : "Neutral";

const dirClass = (d: number) =>
  d === 1 ? "tag long" : d === -1 ? "tag short" : "tag neutral";

/** UI release (align with API when you ship both). */
const SITE_VERSION = "0.2.0";

/** Hosted static sites must set `VITE_API_BASE` to the FastAPI origin; dev leaves this empty (Vite proxy). */
const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

/** Must match `vite.config.ts` proxy target (see `frontend/.env.example`). */
const DEV_API_PORT = import.meta.env.VITE_API_PORT ?? "8000";

function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${p}`;
}

async function apiFetch(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<Response> {
  const { timeoutMs, signal: userSignal, ...rest } = init ?? {};
  const ctrl = new AbortController();
  const tid =
    timeoutMs != null && timeoutMs > 0
      ? window.setTimeout(() => ctrl.abort(), timeoutMs)
      : undefined;
  if (userSignal) {
    if (userSignal.aborted) ctrl.abort();
    else userSignal.addEventListener("abort", () => ctrl.abort(), { once: true });
  }
  try {
    return await fetch(apiUrl(path), {
      cache: "no-store",
      signal: ctrl.signal,
      ...rest,
    });
  } finally {
    if (tid !== undefined) window.clearTimeout(tid);
  }
}

function explainNetworkFailure(raw: string): string {
  const m = raw.toLowerCase();
  const isNetFail =
    m.includes("failed to fetch") ||
    m.includes("networkerror") ||
    m.includes("load failed") ||
    m.includes("network request failed");
  if (!isNetFail) return raw;
  if (API_BASE) {
    return `${raw} — This UI is built with VITE_API_BASE=${API_BASE}. Open that URL in the browser; if it fails, the API host is down, blocking mixed content, or CORS is misconfigured (set GOLD_CORS_ORIGINS on the API).`;
  }
  return `${raw} — In dev, Vite proxies /api and /health to http://127.0.0.1:${DEV_API_PORT} (set VITE_API_PORT in frontend/.env.local if uvicorn uses another port). From the repo folder run: ./scripts/start_api.sh then keep npm run dev running. Quick check: open http://127.0.0.1:${DEV_API_PORT}/health in the browser (should return JSON).`;
}

async function readApiErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: string | string[] | Record<string, unknown> };
    const d = body?.detail;
    if (typeof d === "string") return `${fallback}: ${d}`;
    if (Array.isArray(d)) return `${fallback}: ${JSON.stringify(d)}`;
    if (d != null) return `${fallback}: ${JSON.stringify(d)}`;
  } catch {
    /* ignore */
  }
  return fallback;
}

export default function App() {
  const [tab, setTab] = useState<"dash" | "method">("dash");
  const [latest, setLatest] = useState<Latest | null>(null);
  const [wf, setWf] = useState<Wf | null>(null);
  const [wfErr, setWfErr] = useState<string | null>(null);
  const [wfLoading, setWfLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(async (opts?: { invalidateServer?: boolean }) => {
    setErr(null);
    setWfErr(null);
    if (opts?.invalidateServer) {
      try {
        await apiFetch("/api/v1/cache/invalidate", { method: "POST", timeoutMs: 30_000 });
      } catch {
        /* still try reads */
      }
    }
    try {
      const h = await apiFetch("/health", { timeoutMs: 12_000 });
      if (!h.ok) {
        throw new Error(
          `/health returned HTTP ${h.status}. Uvicorn may be running but not ready — check its terminal.`,
        );
      }
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      setLatest(null);
      setWf(null);
      setErr(
        explainNetworkFailure(
          raw.startsWith("/health") ? raw : `Health check failed: ${raw}`,
        ),
      );
      return;
    }
    try {
      const rl = await apiFetch("/api/v1/signals/latest", { timeoutMs: 180_000 });
      if (!rl.ok) {
        throw new Error(await readApiErrorMessage(rl, `signals ${rl.status}`));
      }
      const l = (await rl.json()) as Latest;
      flushSync(() => {
        setLatest(l);
      });
    } catch (e) {
      const aborted =
        (e instanceof Error && e.name === "AbortError") ||
        (typeof DOMException !== "undefined" && e instanceof DOMException && e.name === "AbortError");
      const raw = aborted
        ? `Timed out waiting for /api/v1/signals/latest (180s). ${
            API_BASE
              ? `Host: ${API_BASE}`
              : `Dev proxy → http://127.0.0.1:${DEV_API_PORT} — keep ./scripts/start_api.sh running.`
          }`
        : e instanceof Error
          ? e.message
          : "API unreachable";
      setLatest(null);
      setWf(null);
      setErr(aborted ? raw : explainNetworkFailure(raw));
      return;
    }

    setWfLoading(true);
    const tryUrls = ["/api/v1/walk-forward", "/api/v1/backtest/walk-forward"];
    let lastStatus = 0;
    let w: Wf | null = null;
    let lastWfErr: string | null = null;
    try {
      for (const url of tryUrls) {
        const rw = await apiFetch(url, { timeoutMs: 300_000 });
        lastStatus = rw.status;
        if (rw.ok) {
          w = (await rw.json()) as Wf;
          break;
        }
        lastWfErr = await readApiErrorMessage(rw, `walk-forward ${lastStatus}`);
      }
    } catch (e) {
      const aborted =
        (e instanceof Error && e.name === "AbortError") ||
        (typeof DOMException !== "undefined" && e instanceof DOMException && e.name === "AbortError");
      lastWfErr = aborted
        ? "Walk-forward request timed out (300s). Try again or open GET /api/v1/walk-forward in the API docs."
        : e instanceof Error
          ? e.message
          : String(e);
    } finally {
      setWfLoading(false);
    }
    if (!w) {
      setWf(null);
      setWfErr(
        lastWfErr ??
          `Walk-forward HTTP ${lastStatus}. The first load can take 30–60s (large JSON). If this was instant, the dev proxy may have timed out—restart Vite after pulling the latest vite.config. Or open http://127.0.0.1:8000/docs and try GET /api/v1/walk-forward.`
      );
    } else {
      setWf(w);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === "visible") void load();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [load]);

  return (
    <>
      <header className="hero">
        <p className="eyebrow">XAU · walk-forward baseline</p>
        <h1>Gold signal desk</h1>
        <p className="lede">
          Consensus from categories A–F (technical, rates, USD, risk, flow). Execution spine:{" "}
          <strong>XAUUSD</strong> mid; features: <strong>GC1</strong> / curve.
        </p>
        {latest?.strategy ? (
          <p className="hero-strategy" role="status">
            <span className={`strategy-pill ${latest.strategy.source === "tuned" ? "tuned" : "prod"}`}>
              {latest.strategy.source === "tuned" ? "Tuned strategy" : "Production strategy"}
            </span>
            {latest.strategy.source === "tuned" ? (
              <span className="muted small">
                {latest.strategy.tuning_run_name ? (
                  <>
                    run <code>{latest.strategy.tuning_run_name}</code>
                    <span className="muted"> · </span>
                  </>
                ) : null}
                WF overlays on legs &amp; categories; equity &amp; walk-forward below match this API build.
              </span>
            ) : (
              <span className="muted small">Sign(z) discrete rules only (set tuning CSV + restart API for tuned).</span>
            )}
          </p>
        ) : null}
        <nav className="tabs">
          <button type="button" className={tab === "dash" ? "active" : ""} onClick={() => setTab("dash")}>
            Dashboard
          </button>
          <button
            type="button"
            className={tab === "method" ? "active" : ""}
            onClick={() => setTab("method")}
          >
            Methodology
          </button>
          <button
            type="button"
            className="ghost"
            title="Reload from API. Shift+click also clears the server signal cache (use after updating CSVs)."
            onClick={(ev) => void load({ invalidateServer: ev.shiftKey })}
          >
            Refresh
          </button>
        </nav>
      </header>

      {tab === "method" ? (
        <Methodology />
      ) : err ? (
        <div className="card error">
          <h2>Offline</h2>
          <p>{err}</p>
          <p className="muted small">
            The UI talks to the API through the Vite proxy (<code>/api</code> → port <code>8000</code>) in dev. On a
            hosted static site, set <code>VITE_API_BASE</code> to your API URL and rebuild (
            <code>frontend/.env.example</code>).
            <strong> You must open a terminal in your project folder first</strong> — if you are in{" "}
            <code>~</code> (home), <code>./scripts/start_api.sh</code> will not exist.{" "}
            <code>cd</code> into the folder that contains <code>backend/</code> and <code>frontend/</code>, then run:
          </p>
          <pre className="cmd">
            {`cd "/path/to/Gold Dashboard V2"   # example — use your real clone path
./scripts/start_api.sh`}
          </pre>
          <p className="muted small">
            One-liner without <code>cd</code> (replace the path):{" "}
            <code>/path/to/Gold Dashboard V2/scripts/start_api.sh</code>
          </p>
          <p className="muted small">
            Or from the <strong>same</strong> project root after <code>cd</code>:{" "}
            <code>PYTHONPATH=backend python3 -m uvicorn gold_signal.api.main:app --reload --host 127.0.0.1 --port 8000</code>
          </p>
          <p className="muted small">
            Frontend: <code>cd</code> into <code>frontend/</code>, then <code>npm run dev</code> (not static{" "}
            <code>file://</code>).
          </p>
          <p className="muted small">
            If the API script says <strong>Address already in use</strong>, port 8000 is taken (often a leftover
            uvicorn). Stop it:{" "}
            <code>kill $(lsof -t -iTCP:8000 -sTCP:LISTEN)</code> then run <code>start_api.sh</code> again. See{" "}
            <code>frontend/.env.example</code> if you use another port.
          </p>
        </div>
      ) : latest ? (
        <Dashboard latest={latest} wf={wf} wfErr={wfErr} wfLoading={wfLoading} />
      ) : (
        <div className="card load-card">
          <p className="load-title">Loading…</p>
          <p className="muted small load-detail">
            Waiting for <code>/api/v1/signals/latest</code>. The first cold build (load panel + full signal table, often
            with tuning overlays) can take <strong>1–2 minutes</strong>. Start the API from the repo:{" "}
            <code>./scripts/start_api.sh</code> (port <code>8000</code>). Vite proxies <code>/api</code> → that port. If
            this passes 3 minutes you should see a timeout error instead of this screen.
          </p>
        </div>
      )}

      <style>{css}</style>
    </>
  );
}

function tickIndices(n: number): number[] {
  if (n <= 1) return [0];
  const k = 5;
  const out: number[] = [];
  for (let i = 0; i < k; i++) {
    out.push(Math.round((i * (n - 1)) / (k - 1)));
  }
  return [...new Set(out)].sort((a, b) => a - b);
}

function shortDate(iso: string): string {
  if (iso.length >= 10) return iso.slice(2, 10);
  return iso;
}

function fmtPct(x: number | null | undefined, d = 1): string {
  if (x == null || !Number.isFinite(x)) return "—";
  return `${x.toFixed(d)}%`;
}

function fmtNum(x: number | null | undefined, d = 3): string {
  if (x == null || !Number.isFinite(x)) return "—";
  return x.toFixed(d);
}

/** OOS Sharpe (strategy vs buy & hold) + excess Sharpe bars per WF step. */
function WfOosComparisonCharts({ steps }: { steps: WfStep[] }) {
  if (steps.length < 2) return null;
  const W = 900;
  const padL = 52;
  const padR = 16;
  const plotW = W - padL - padR;
  const n = steps.length;
  const xAt = (i: number) => padL + (i / (n - 1)) * plotW;

  const stratVals = steps.map((s) => (Number.isFinite(s.oos_sharpe) ? s.oos_sharpe : null));
  const bhVals = steps.map((s) =>
    s.oos_sharpe_buy_hold != null && Number.isFinite(s.oos_sharpe_buy_hold) ? s.oos_sharpe_buy_hold : null,
  );
  const allY: number[] = [];
  for (let i = 0; i < n; i++) {
    if (stratVals[i] != null) allY.push(stratVals[i]!);
    if (bhVals[i] != null) allY.push(bhVals[i]!);
  }
  let yMin = Math.min(...allY, 0);
  let yMax = Math.max(...allY, 0);
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
  }
  const padY = (yMax - yMin) * 0.1;
  yMin -= padY;
  yMax += padY;
  const lineTop = 22;
  const lineBot = 118;
  const yLine = (v: number) => lineBot - ((v - yMin) / (yMax - yMin)) * (lineBot - lineTop);
  let dStrat = "";
  let dBh = "";
  for (let i = 0; i < n; i++) {
    const sv = stratVals[i];
    const bv = bhVals[i];
    if (sv != null) {
      dStrat += `${dStrat === "" ? "M" : "L"} ${xAt(i).toFixed(1)} ${yLine(sv).toFixed(1)}`;
    }
    if (bv != null) {
      dBh += `${dBh === "" ? "M" : "L"} ${xAt(i).toFixed(1)} ${yLine(bv).toFixed(1)}`;
    }
  }

  const excess: (number | null)[] = steps.map((_, i) => {
    const sv = stratVals[i];
    const bv = bhVals[i];
    if (sv == null || bv == null) return null;
    return sv - bv;
  });
  const exFin = excess.filter((v): v is number => v != null);
  let eMin = Math.min(...exFin, 0);
  let eMax = Math.max(...exFin, 0);
  if (eMin === eMax) {
    eMin -= 0.5;
    eMax += 0.5;
  }
  const ep = (eMax - eMin) * 0.12;
  eMin -= ep;
  eMax += ep;
  const barTop = 138;
  const barBot = 248;
  const yEx = (e: number) => barBot - ((e - eMin) / (eMax - eMin)) * (barBot - barTop);
  const yZero = yEx(0);
  const barW = Math.max(0.8, (plotW / n) * 0.5);
  const ticks = tickIndices(n);

  const bars = excess.map((e, i) => {
    if (e == null) return null;
    const xb = xAt(i) - barW / 2;
    const y1 = yEx(e);
    const top = Math.min(y1, yZero);
    const h = Math.max(1, Math.abs(yZero - y1));
    const fill = e >= 0 ? "rgba(61, 154, 106, 0.55)" : "rgba(196, 92, 92, 0.48)";
    return <rect key={`b-${i}`} x={xb} y={top} width={barW} height={h} fill={fill} rx={1} />;
  });

  return (
    <div className="wf-oos-charts">
      <p className="muted small wf-oos-caption">
        <strong>Top:</strong> OOS Sharpe each window — gold = long/short consensus, gray = buy &amp; hold XAUUSD.
        <strong> Bottom:</strong> excess OOS Sharpe (strategy − B&amp;H); green bars beat benchmark, red underperform.
      </p>
      <svg viewBox={`0 0 ${W} 268`} className="chart wf-oos-svg" aria-hidden>
        <line
          x1={padL}
          y1={lineBot}
          x2={padL + plotW}
          y2={lineBot}
          stroke="var(--border)"
          strokeWidth="1"
          opacity={0.5}
        />
        <line
          x1={padL}
          y1={yLine(0)}
          x2={padL + plotW}
          y2={yLine(0)}
          stroke="var(--muted)"
          strokeWidth="1"
          strokeDasharray="4 3"
          opacity={0.45}
        />
        {dBh ? <path d={dBh} fill="none" stroke="var(--muted)" strokeWidth="1.75" opacity={0.85} /> : null}
        {dStrat ? <path d={dStrat} fill="none" stroke="var(--gold)" strokeWidth="2" /> : null}
        <line x1={padL} y1={barBot} x2={padL + plotW} y2={barBot} stroke="var(--border)" strokeWidth="1" opacity={0.45} />
        <line
          x1={padL}
          y1={yZero}
          x2={padL + plotW}
          y2={yZero}
          stroke="var(--muted)"
          strokeWidth="1"
          opacity={0.55}
        />
        {bars}
        {ticks.map((ti) => (
          <text
            key={`wx-${ti}`}
            x={xAt(ti)}
            y={262}
            fill="#8a8278"
            fontSize="10"
            fontFamily="system-ui, sans-serif"
            textAnchor="middle"
          >
            {shortDate(steps[ti].oos_start)}
          </text>
        ))}
      </svg>
      <div className="wf-oos-legend">
        <span>
          <i className="dot gold" /> Strategy OOS Sharpe
        </span>
        <span>
          <i className="dot muted" /> B&amp;H OOS Sharpe
        </span>
        <span className="muted small">({n} steps)</span>
      </div>
    </div>
  );
}

function LaneStatsCol({ title, lane }: { title: string; lane: ReturnStatsLane }) {
  return (
    <div className="stat-col">
      <h4 className="stat-col-title">{title}</h4>
      <dl className="stat-dl">
        <dt>Ann. Sharpe</dt>
        <dd>{fmtNum(lane.annualized_sharpe)}</dd>
        <dt>CAGR</dt>
        <dd>{fmtPct(lane.total_return_pct)}</dd>
        <dt>Max drawdown</dt>
        <dd>{fmtPct(lane.max_drawdown_pct)}</dd>
        <dt>Ann. volatility</dt>
        <dd>{fmtPct(lane.volatility_annualized)}</dd>
        <dt>Hit ratio (all days)</dt>
        <dd>{fmtPct(lane.hit_ratio_all_days_pct)}</dd>
        {lane.hit_ratio_active_days_pct != null ? (
          <>
            <dt>Hit ratio (active)</dt>
            <dd>{fmtPct(lane.hit_ratio_active_days_pct)}</dd>
          </>
        ) : null}
        <dt>Days</dt>
        <dd>
          {lane.trading_days}
          {lane.active_trading_days != null ? ` (${lane.active_trading_days} active)` : ""}
        </dd>
      </dl>
    </div>
  );
}

function EquityFullSampleBlock({ wf }: { wf: Wf }) {
  const fs = wf.full_sample_stats;
  const oos = wf.walk_forward?.oos_vs_buy_hold;
  if (!fs) return null;
  return (
    <div className="equity-stats-block">
      <h3 className="equity-stats-heading">Full-sample statistics (daily)</h3>
      <p className="muted small">
        Sharpe = √252 × mean/σ on daily returns. CAGR = geometric annualized return from the equity curve (252 trading
        days/year). Ann. volatility = √252 × stdev of daily returns (shown as %). Drawdown from the equity curve. Hit
        ratio = % of days with positive daily return; <em>active</em> = days with a non-flat position (long or short
        for L/S; long gold only for long-only).
      </p>
      <div className="stat-cols">
        <LaneStatsCol title="Long / short consensus" lane={fs.consensus_long_short} />
        <LaneStatsCol title="Long-only consensus" lane={fs.consensus_long_only} />
        <LaneStatsCol title="Buy &amp; hold XAUUSD" lane={fs.buy_hold_xauusd} />
      </div>
      <div className="stat-extra">
        <h4 className="stat-col-title">Versus buy &amp; hold (daily)</h4>
        <dl className="stat-dl stat-dl-inline">
          <dt>% days strategy return &gt; B&amp;H</dt>
          <dd>{fmtPct(fs.versus_buy_hold_daily.pct_days_strategy_return_gt_benchmark)}</dd>
          <dt>Correlation (strategy, B&amp;H)</dt>
          <dd>{fmtNum(fs.versus_buy_hold_daily.correlation)}</dd>
          <dt>Days compared</dt>
          <dd>{fs.versus_buy_hold_daily.days_compared}</dd>
        </dl>
      </div>
      {oos ? (
        <div className="stat-extra">
          <h4 className="stat-col-title">Walk-forward OOS vs B&amp;H</h4>
          <dl className="stat-dl stat-dl-inline">
            <dt>L/S: steps beating B&amp;H Sharpe</dt>
            <dd>
              {oos.oos_sharpe_beat_buy_hold_count} / {oos.oos_steps_compared} (
              {fmtPct(oos.oos_sharpe_beat_buy_hold_pct, 1)})
            </dd>
            <dt>Long-only: steps beating B&amp;H</dt>
            <dd>
              {oos.oos_long_only_sharpe_beat_buy_hold_count} / {oos.oos_long_only_steps_compared} (
              {fmtPct(oos.oos_long_only_sharpe_beat_buy_hold_pct, 1)})
            </dd>
          </dl>
        </div>
      ) : null}
    </div>
  );
}

/** Single-series equity with vertical grid + date ticks (matches main chart pattern). */
function SparkEquityTimeline({
  pts,
  stroke = "var(--gold)",
}: {
  pts: { d: string; e: number }[];
  stroke?: string;
}) {
  if (pts.length < 2) return null;
  const W = 300;
  const plotTop = 8;
  const plotBottom = 54;
  const plotLeft = 6;
  const plotRight = 292;
  const axisY = 66;
  const svgH = 78;
  const plotW = plotRight - plotLeft;
  const plotH = plotBottom - plotTop;
  const ev = pts.map((p) => p.e);
  const smin = Math.min(...ev) * 0.998;
  const smax = Math.max(...ev) * 1.002;
  const n = pts.length;
  const xAt = (i: number) => plotLeft + (i / (n - 1)) * plotW;
  const yAt = (v: number) => plotBottom - ((v - smin) / (smax - smin || 1)) * plotH;
  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(p.e).toFixed(1)}`).join(" ");
  const ticks = tickIndices(n);
  return (
    <svg viewBox={`0 0 ${W} ${svgH}`} className="spark spark-timeline" aria-hidden>
      {ticks.map((ti) => (
        <line
          key={ti}
          x1={xAt(ti)}
          y1={plotTop}
          x2={xAt(ti)}
          y2={plotBottom}
          stroke="var(--border)"
          strokeWidth="1"
          opacity={0.35}
        />
      ))}
      <line
        x1={plotLeft}
        y1={plotBottom}
        x2={plotRight}
        y2={plotBottom}
        stroke="var(--muted)"
        strokeWidth="1"
        opacity={0.45}
      />
      <path d={path} fill="none" stroke={stroke} strokeWidth="1.5" />
      {ticks.map((ti) => (
        <text
          key={`t-${ti}`}
          x={xAt(ti)}
          y={axisY}
          fill="#8a8278"
          fontSize="9"
          fontFamily="system-ui, sans-serif"
          textAnchor="middle"
        >
          {shortDate(pts[ti].d)}
        </text>
      ))}
    </svg>
  );
}

function CategoryDetailCard({
  c,
  bt,
  bh,
  legs,
  subBt,
}: {
  c: CategoryRow;
  bt?: CategoryBacktest;
  bh?: BuyHoldComparison;
  legs: SignalLeg[];
  subBt?: Record<string, SubsignalBacktest>;
}) {
  const spark = bt?.equity_tail_rebased ?? [];
  const sparkSvg = spark.length >= 2 ? <SparkEquityTimeline pts={spark} /> : null;
  const lo = bt?.long_only;
  const sparkLo = lo?.equity_tail_rebased ?? [];
  const sparkLoSvg =
    sparkLo.length >= 2 ? <SparkEquityTimeline pts={sparkLo} stroke="var(--long-only)" /> : null;

  return (
    <div className="cat-wide">
      <div className="cat-wide-head">
        <span className="cid">{c.id}</span>
        <div className="cat-titles">
          <h3>{c.title}</h3>
          <span className="muted small">{c.subtitle}</span>
        </div>
        <div className="cat-live">
          <span className={dirClass(c.direction)}>{dirLabel(c.direction)}</span>
          <span className="raw">
            z {c.raw_score?.toFixed(2) ?? "—"} · conf {c.confidence?.toFixed(0) ?? "—"}
          </span>
        </div>
      </div>
      <p className="cat-detail small">{c.detail}</p>
      {bt ? (
        <div className="cat-bt">
          <div className="bt-grid">
            <div>
              <span className="bt-label">Mean OOS Sharpe</span>
              <strong>
                {bt.walk_forward.mean_oos_sharpe == null ? "—" : bt.walk_forward.mean_oos_sharpe.toFixed(3)}
              </strong>
            </div>
            <div>
              <span className="bt-label">WF steps</span>
              <strong>{bt.walk_forward.n_steps}</strong>
            </div>
            <div>
              <span className="bt-label">Full-sample Sharpe</span>
              <strong>{Number.isFinite(bt.sharpe_full_sample) ? bt.sharpe_full_sample.toFixed(3) : "—"}</strong>
            </div>
            <div>
              <span className="bt-label">CAGR (full)</span>
              <strong>{Number.isFinite(bt.total_return_pct) ? `${bt.total_return_pct.toFixed(1)}%` : "—"}</strong>
            </div>
            <div className="bt-span">
              <span className="bt-label">Mix % long / short</span>
              <strong>
                {bt.direction_mix_pct.long.toFixed(0)} / {bt.direction_mix_pct.short.toFixed(0)}
              </strong>
            </div>
          </div>
          {bh ? (
            <div className="bt-grid cat-bh-grid">
              <div>
                <span className="bt-label">B&amp;H mean OOS Sharpe</span>
                <strong>
                  {bh.walk_forward.mean_oos_sharpe == null ? "—" : bh.walk_forward.mean_oos_sharpe.toFixed(3)}
                </strong>
              </div>
              <div>
                <span className="bt-label">B&amp;H full Sharpe</span>
                <strong>{Number.isFinite(bh.sharpe_full_sample) ? bh.sharpe_full_sample.toFixed(3) : "—"}</strong>
              </div>
              <div>
                <span className="bt-label">B&amp;H CAGR %</span>
                <strong>{Number.isFinite(bh.total_return_pct) ? `${bh.total_return_pct.toFixed(1)}%` : "—"}</strong>
              </div>
            </div>
          ) : null}
          <div className="spark-row-dual">
            <div className="spark-wrap">
              <span className="bt-label">Solo equity — long/short (rebased, downsampled)</span>
              {sparkSvg ?? <span className="muted small">—</span>}
            </div>
            {bh && (bh.equity_tail_rebased?.length ?? 0) >= 2 ? (
              <div className="spark-wrap">
                <span className="bt-label">Buy &amp; hold XAUUSD (same window, comparison)</span>
                <SparkEquityTimeline pts={bh.equity_tail_rebased} stroke="var(--muted)" />
              </div>
            ) : null}
          </div>
          {lo ? (
            <>
              <div className="bt-grid cat-lo-grid">
                <div>
                  <span className="bt-label">L-O mean OOS Sharpe</span>
                  <strong>
                    {lo.walk_forward.mean_oos_sharpe == null ? "—" : lo.walk_forward.mean_oos_sharpe.toFixed(3)}
                  </strong>
                </div>
                <div>
                  <span className="bt-label">L-O full Sharpe</span>
                  <strong>{Number.isFinite(lo.sharpe_full_sample) ? lo.sharpe_full_sample.toFixed(3) : "—"}</strong>
                </div>
                <div>
                  <span className="bt-label">L-O CAGR %</span>
                  <strong>{Number.isFinite(lo.total_return_pct) ? `${lo.total_return_pct.toFixed(1)}%` : "—"}</strong>
                </div>
                <div className="bt-span">
                  <span className="bt-label">L-O book: long gold / flat</span>
                  <strong>
                    {lo.direction_mix_pct.long.toFixed(0)} / {lo.direction_mix_pct.neutral.toFixed(0)}
                  </strong>
                </div>
              </div>
              <div className="spark-wrap cat-lo-spark-only">
                <span className="bt-label">Long-only equity (short signals → flat)</span>
                {sparkLoSvg ?? <span className="muted small">—</span>}
              </div>
            </>
          ) : null}
        </div>
      ) : (
        <p className="muted small">Per-category backtest missing — refresh data or restart API.</p>
      )}

      {legs.length ? (
        <div className="sub-legs">
          <h4 className="sub-legs-title">Per-signal solo backtests</h4>
          <p className="muted small">
            Each row trades <strong>only that raw feature</strong>: long if z &gt; 0, short if z &lt; 0, z = 0 or missing
            → long, × one-session XAUUSD return. <strong>Buy &amp; hold</strong> columns are identical across rows (same
            XAUUSD path). Long-only variant: shorts → flat.
          </p>
          <div className="sub-leg-table-wrap">
            <table className="sub-leg-table">
              <thead>
                <tr>
                  <th>Signal</th>
                  <th>Live z</th>
                  <th>Vote</th>
                  <th>OOS Sharpe</th>
                  <th>L-O OOS</th>
                  <th>B&amp;H OOS</th>
                  <th>Full Sharpe</th>
                  <th>L-O Full</th>
                  <th>B&amp;H Full</th>
                  <th>CAGR %</th>
                  <th>L-O CAGR %</th>
                  <th>B&amp;H CAGR %</th>
                  <th>L / S %</th>
                  <th>Equity</th>
                  <th>L-O eq</th>
                  <th>B&amp;H eq</th>
                </tr>
              </thead>
              <tbody>
                {legs.map((lg) => {
                  const sb = subBt?.[lg.id];
                  const slo = sb?.long_only;
                  const sp = sb?.equity_tail_rebased ?? [];
                  const splo = slo?.equity_tail_rebased ?? [];
                  const bhSub = bh?.equity_tail_rebased_sub ?? [];
                  const mini =
                    sp.length >= 2 ? <SparkEquityTimeline pts={sp} /> : <span className="muted small">—</span>;
                  const miniLo =
                    splo.length >= 2 ? (
                      <SparkEquityTimeline pts={splo} stroke="var(--long-only)" />
                    ) : (
                      <span className="muted small">—</span>
                    );
                  const miniBh =
                    bhSub.length >= 2 ? (
                      <SparkEquityTimeline pts={bhSub} stroke="var(--muted)" />
                    ) : (
                      <span className="muted small">—</span>
                    );
                  return (
                    <tr key={lg.id}>
                      <td className="sub-leg-name">{lg.label}</td>
                      <td>{lg.raw_score != null ? lg.raw_score.toFixed(2) : "—"}</td>
                      <td>
                        <span className={dirClass(lg.direction)}>{dirLabel(lg.direction)}</span>
                      </td>
                      <td>
                        {sb?.walk_forward.mean_oos_sharpe == null
                          ? "—"
                          : sb.walk_forward.mean_oos_sharpe.toFixed(3)}
                      </td>
                      <td>
                        {slo?.walk_forward.mean_oos_sharpe == null
                          ? "—"
                          : slo.walk_forward.mean_oos_sharpe.toFixed(3)}
                      </td>
                      <td>
                        {bh?.walk_forward.mean_oos_sharpe == null
                          ? "—"
                          : bh.walk_forward.mean_oos_sharpe.toFixed(3)}
                      </td>
                      <td>
                        {sb && Number.isFinite(sb.sharpe_full_sample) ? sb.sharpe_full_sample.toFixed(3) : "—"}
                      </td>
                      <td>
                        {slo && Number.isFinite(slo.sharpe_full_sample)
                          ? slo.sharpe_full_sample.toFixed(3)
                          : "—"}
                      </td>
                      <td>
                        {bh && Number.isFinite(bh.sharpe_full_sample) ? bh.sharpe_full_sample.toFixed(3) : "—"}
                      </td>
                      <td>
                        {sb && Number.isFinite(sb.total_return_pct) ? `${sb.total_return_pct.toFixed(1)}%` : "—"}
                      </td>
                      <td>
                        {slo && Number.isFinite(slo.total_return_pct) ? `${slo.total_return_pct.toFixed(1)}%` : "—"}
                      </td>
                      <td>
                        {bh && Number.isFinite(bh.total_return_pct) ? `${bh.total_return_pct.toFixed(1)}%` : "—"}
                      </td>
                      <td className="nowrap">
                        {sb ? (
                          <>
                            {sb.direction_mix_pct.long.toFixed(0)} / {sb.direction_mix_pct.short.toFixed(0)}
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="sub-leg-spark">{mini}</td>
                      <td className="sub-leg-spark">{miniLo}</td>
                      <td className="sub-leg-spark">{miniBh}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Dashboard({
  latest,
  wf,
  wfErr,
  wfLoading,
}: {
  latest: Latest;
  wf: Wf | null;
  wfErr: string | null;
  wfLoading: boolean;
}) {
  const pts = wf?.equity_curve_tail ?? [];
  const W = 900;
  const plotTop = 14;
  const plotBottom = 210;
  const plotLeft = 52;
  const plotRight = 872;
  const axisY = 232;
  const svgH = 268;
  const plotW = plotRight - plotLeft;
  const plotH = plotBottom - plotTop;

  let chart: ReactNode = null;
  if (wfErr) {
    chart = <p className="muted small">{wfErr}</p>;
  } else if (pts.length >= 2) {
    const sVals = pts.map((p) => p.s);
    const bVals = pts.map((p) => p.b);
    const lVals = pts.map((p) => (typeof p.l === "number" ? p.l : p.s));
    const min = Math.min(...sVals, ...bVals, ...lVals) * 0.98;
    const max = Math.max(...sVals, ...bVals, ...lVals) * 1.02;
    const n = pts.length;
    const xAt = (i: number) => plotLeft + (i / (n - 1)) * plotW;
    const yAt = (v: number) => plotBottom - ((v - min) / (max - min)) * plotH;
    const pathS = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(p.s).toFixed(1)}`).join(" ");
    const pathL = pts
      .map((p, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(typeof p.l === "number" ? p.l : p.s).toFixed(1)}`)
      .join(" ");
    const pathB = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${xAt(i).toFixed(1)} ${yAt(p.b).toFixed(1)}`).join(" ");
    const ticks = tickIndices(n);
    chart = (
      <>
        <svg viewBox={`0 0 ${W} ${svgH}`} className="chart chart-timeline">
          {ticks.map((ti) => (
            <line
              key={ti}
              x1={xAt(ti)}
              y1={plotTop}
              x2={xAt(ti)}
              y2={plotBottom}
              stroke="var(--border)"
              strokeWidth="1"
              opacity={0.35}
            />
          ))}
          <line
            x1={plotLeft}
            y1={plotBottom}
            x2={plotRight}
            y2={plotBottom}
            stroke="var(--muted)"
            strokeWidth="1"
            opacity={0.5}
          />
          <path d={pathB} fill="none" stroke="var(--muted)" strokeWidth="1.5" opacity={0.75} />
          <path
            d={pathL}
            fill="none"
            stroke="var(--long-only)"
            strokeWidth="2"
            strokeDasharray="6 4"
            opacity={0.95}
          />
          <path d={pathS} fill="none" stroke="var(--gold)" strokeWidth="2" />
          {ticks.map((ti) => (
            <text
              key={`l-${ti}`}
              x={xAt(ti)}
              y={axisY}
              fill="#8a8278"
              fontSize="11"
              fontFamily="system-ui, sans-serif"
              textAnchor="middle"
            >
              {shortDate(pts[ti].d)}
            </text>
          ))}
        </svg>
        <div className="legend legend-3">
          <span>
            <i className="dot gold" /> Long/short consensus
          </span>
          <span>
            <i className="dot longonly" /> Long-only (short → flat)
          </span>
          <span>
            <i className="dot muted" /> Buy &amp; hold XAUUSD
          </span>
        </div>
      </>
    );
  } else {
    chart = <p className="muted small">Loading series…</p>;
  }

  const wfSummary = wf?.walk_forward;
  const wfSteps = wfSummary?.steps ?? [];
  const em = wf?.equity_meta;

  return (
    <>
      {wfLoading ? (
        <div className="card warn wf-loading-banner" role="status">
          <p className="muted small" style={{ margin: 0 }}>
            Loading walk-forward &amp; chart payload (often <strong>30–90s</strong>) — consensus below is ready. If this
            never clears, check the API terminal for errors or click <strong>Refresh</strong>.
          </p>
        </div>
      ) : null}
      <section className="grid2">
        <div className="card consensus">
          <h2>Latest consensus</h2>
          {latest.strategy ? (
            <p className="consensus-strategy muted small">
              API: <strong>{latest.strategy.source === "tuned" ? "tuned" : "production"}</strong>
              {latest.strategy.tuning_run_name ? (
                <>
                  {" "}
                  · <code>{latest.strategy.tuning_run_name}</code>
                </>
              ) : null}
            </p>
          ) : null}
          <p className="date">{latest.date}</p>
          <div className={dirClass(latest.consensus.direction)}>
            {dirLabel(latest.consensus.direction)}
          </div>
          <p className="conf">
            Confidence{" "}
            <strong>{latest.consensus.confidence?.toFixed(0) ?? "—"}</strong>
          </p>
        </div>
        <div className="card">
          <h2>Walk-forward (OOS)</h2>
          <p className="muted small">
            Default grid: 378 / 42 / 42 (IS / OOS / step). Mean OOS Sharpe across non-overlapping steps.
          </p>
          {wfSummary ? (
            <>
              <p className="stat">
                Steps: <strong>{wfSummary.n_steps}</strong>
              </p>
              <p className="stat">
                Mean OOS Sharpe:{" "}
                <strong>
                  {wfSummary.mean_oos_sharpe == null ? "—" : wfSummary.mean_oos_sharpe.toFixed(3)}
                </strong>
              </p>
              <p className="stat">
                Mean OOS Sharpe (long-only):{" "}
                <strong>
                  {wfSummary.mean_oos_sharpe_long_only == null
                    ? "—"
                    : wfSummary.mean_oos_sharpe_long_only.toFixed(3)}
                </strong>
              </p>
              <p className="stat">
                Mean OOS Sharpe (buy &amp; hold XAUUSD):{" "}
                <strong>
                  {wfSummary.mean_oos_sharpe_buy_hold == null
                    ? "—"
                    : wfSummary.mean_oos_sharpe_buy_hold.toFixed(3)}
                </strong>
              </p>
              {wfSummary.sharpe_methodology ? (
                <div className="muted small" style={{ marginTop: "1rem", lineHeight: 1.5 }}>
                  <p>
                    <strong>OOS window:</strong> {wfSummary.sharpe_methodology.oos_trading_days_per_window} trading days
                    per step (IS {wfSummary.sharpe_methodology.is_trading_days_per_window}d, step{" "}
                    {wfSummary.sharpe_methodology.step_trading_days}d). Env defaults:{" "}
                    <code>GOLD_WF_IS</code> / <code>GOLD_WF_OOS</code> / <code>GOLD_WF_STEP</code>.
                  </p>
                  <p>{wfSummary.sharpe_methodology.mean_oos_sharpe}</p>
                  <p>{wfSummary.sharpe_methodology.full_sample_sharpe}</p>
                  <p>{wfSummary.sharpe_methodology.why_they_differ}</p>
                </div>
              ) : null}
            </>
          ) : (
            <p className="muted small">{wfErr ?? "—"}</p>
          )}
        </div>
      </section>

      {wfSteps.length ? (
        <section className="card">
          <h2>Walk-forward timeline (OOS windows)</h2>
          <p className="muted small">
            Each row is one out-of-sample block (dates are session ends). IS Sharpe is over the window immediately
            before that OOS block. Previously only the first 50 windows were returned (so the table stopped around
            ~2010); now the API sends the full series unless <code>GOLD_WF_MAX_STEPS</code> caps it.
          </p>
          {wfSummary ? (
            <p className="muted small">
              Loaded <strong>{wfSteps.length}</strong> window{wfSteps.length === 1 ? "" : "s"}
              {wfSummary.n_steps != null && wfSummary.n_steps !== wfSteps.length
                ? ` of ${wfSummary.n_steps} total (truncated — increase GOLD_WF_MAX_STEPS).`
                : wfSummary.n_steps != null
                  ? ` (${wfSummary.n_steps} total in sample).`
                  : "."}
            </p>
          ) : null}
          <WfOosComparisonCharts steps={wfSteps} />
          <div className="wf-steps-wrap">
            <table className="wf-steps">
              <thead>
                <tr>
                  <th>OOS start</th>
                  <th>OOS end</th>
                  <th>OOS Sharpe</th>
                  <th>OOS L-O</th>
                  <th>OOS B&amp;H</th>
                  <th>IS Sharpe</th>
                  <th>IS L-O</th>
                  <th>IS B&amp;H</th>
                </tr>
              </thead>
              <tbody>
                {wfSteps.map((st, i) => (
                  <tr key={`${st.oos_start}-${i}`}>
                    <td>{st.oos_start}</td>
                    <td>{st.oos_end ?? "—"}</td>
                    <td>{Number.isFinite(st.oos_sharpe) ? st.oos_sharpe.toFixed(3) : "—"}</td>
                    <td>
                      {st.oos_sharpe_long_only != null && Number.isFinite(st.oos_sharpe_long_only)
                        ? st.oos_sharpe_long_only.toFixed(3)
                        : "—"}
                    </td>
                    <td>
                      {st.oos_sharpe_buy_hold != null && Number.isFinite(st.oos_sharpe_buy_hold)
                        ? st.oos_sharpe_buy_hold.toFixed(3)
                        : "—"}
                    </td>
                    <td>{st.is_sharpe != null && Number.isFinite(st.is_sharpe) ? st.is_sharpe.toFixed(3) : "—"}</td>
                    <td>
                      {st.is_sharpe_long_only != null && Number.isFinite(st.is_sharpe_long_only)
                        ? st.is_sharpe_long_only.toFixed(3)
                        : "—"}
                    </td>
                    <td>
                      {st.is_sharpe_buy_hold != null && Number.isFinite(st.is_sharpe_buy_hold)
                        ? st.is_sharpe_buy_hold.toFixed(3)
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section className="card">
        <h2>Equity (global consensus)</h2>
        {em ? (
          <p className="muted small">
            Chart dates <strong>{em.chart_first_date}</strong> → <strong>{em.chart_last_date}</strong> · merged panel{" "}
            <strong>{em.panel_start}</strong> → <strong>{em.panel_end}</strong> · <strong>{em.n_points}</strong> points
            (downsampled from <strong>{em.n_bars_full}</strong> bars). First WF OOS:{" "}
            <strong>{em.wf_first_oos ?? "—"}</strong>.
          </p>
        ) : null}
        <p className="muted small">{em?.hint}</p>
        <p className="muted small">
          Long/short consensus, <strong>long-only</strong> variant (same signals but shorts become flat), and buy-hold
          XAUUSD — all <strong>rebased to 1.0</strong> at the first bar.
        </p>
        {wf ? <EquityFullSampleBlock wf={wf} /> : null}
        {chart}
      </section>

      <section className="card">
        <h2>Categories</h2>
        <p className="muted small">
          Each row: signal definition, live vote, <strong>category-level</strong> solo backtest vs{" "}
          <strong>buy &amp; hold XAUUSD</strong> (same calendar, same WF grid), long-only lane, then per-leg tables
          with B&amp;H columns and sparklines (gold / teal / gray).
        </p>
        {wfErr ? (
          <p className="muted small" style={{ marginBottom: "1rem", padding: "0.75rem 1rem", border: "1px solid var(--gold-dim)", borderRadius: 8 }}>
            <strong>Walk-forward did not load.</strong> Live <strong>z</strong> / <strong>vote</strong> still work (from{" "}
            <code>/signals/latest</code>), but OOS Sharpe, CAGR, B&amp;H columns, and sparks need the walk-forward
            payload. {wfErr}
          </p>
        ) : null}
        <div className="cat-list">
          {latest.categories.map((c) => (
            <CategoryDetailCard
              key={c.id}
              c={c}
              bt={wf?.category_backtests?.[c.id]}
              bh={wf?.buy_hold_backtest}
              legs={(latest.signal_legs ?? []).filter((l) => l.category === c.id)}
              subBt={wf?.subsignal_backtests}
            />
          ))}
        </div>
      </section>

      {latest.warnings?.length ? (
        <section className="card warn">
          <h2>Data warnings</h2>
          <ul>
            {latest.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

function Methodology() {
  return (
    <article className="card prose">
      <h2>Methodology &amp; lineage</h2>
      <ul>
        <li>
          <strong>Timing:</strong> Signal at COB <em>T</em>; backtest entry XAUUSD mid COB <em>T</em>, exit COB{" "}
          <em>T+1</em> (one session; flip next session if the signal changes). See <code>specs/execution-timing.md</code>.
        </li>
        <li>
          <strong>Returns:</strong> <code>xauusd_spot.csv</code> from BDH <code>XAUUSD Curncy</code>; features on{" "}
          <code>GC1 Comdty</code> (+ <code>GC2</code> curve).
        </li>
        <li>
          <strong>Rates (B):</strong> 10Y nominal (TNX), TIPS real or breakeven (one leg), 2s10s when 2Y is in the panel.
          Optional FRED <code>DGS2</code> fill for 2Y when <code>USGG2YR</code> is missing and <code>FRED_API_KEY</code> is
          set. The legacy shadow sub-leg is inactive (zeros).
        </li>
        <li>
          <strong>Flow (F):</strong> COT nets lagged +3 business days; GLD shares flow lagged +1 session.
        </li>
        <li>
          <strong>Stage 1 discrete (production):</strong> Always long or short: <code>sign(composite z)</code>, with z = 0
          or missing → long. <code>GOLD_Z_THRESHOLD</code> is for confidence scaling, not direction.
        </li>
        <li>
          <strong>Tuned mode (API default when CSVs exist):</strong> If the API loads{" "}
          <code>data/tuning_runs/&lt;run&gt;/per_leg_per_step.csv</code> (latest folder unless{" "}
          <code>GOLD_TUNING_RUN_DIR</code>), each walk-forward block applies research <em>deadband τ</em> on legs and
          tuned weights + τ on categories A/B/F (τ-only on C/D/G). The header pill shows <strong>Tuned strategy</strong>.
          Disable with <code>GOLD_USE_LATEST_TUNING=0</code>. Hosted static UI needs <code>VITE_API_BASE</code> pointing at
          that API after rebuild.
        </li>
        <li>
          <strong>Stage 2:</strong> Majority long vs short; on a tie, break by the sum of category raw z-scores (sum = 0
          → long). Confidence: median with disagreement penalty. Backtest P&amp;L: consensus × T+1 XAUUSD returns.
        </li>
        <li>
          <strong>Charts:</strong> Global and per-category equity curves use the full merged history, downsampled for
          the browser; dates on the axes match that series. Walk-forward OOS starts after IS+z-window warmup, so the
          first OOS block is later than the panel start date.
        </li>
        <li>
          <strong>Walk-forward table:</strong> Returns every OOS window by default (no 50-row cap). Optional cap:{" "}
          <code>GOLD_WF_MAX_STEPS</code>. The WF chart plots OOS Sharpe vs B&amp;H and per-step excess Sharpe.
        </li>
        <li>
          <strong>Equity panel stats:</strong> Full-sample Sharpe, CAGR, max drawdown, ann. vol (daily √252), hit
          ratios, daily
          outperformance vs B&amp;H, correlation, and OOS win counts vs B&amp;H.
        </li>
        <li>
          <strong>Per-signal legs:</strong> Each leg uses the same discrete rule as the API build (sign(z) in production;
          deadband τ on WF blocks when tuned) with one-session XAUUSD P&amp;L, for attribution only.
        </li>
        <li>
          <strong>Long-only lane:</strong> Same directional signal, but short votes are treated as flat (no short gold);
          charts and tables show this alongside full long/short performance.
        </li>
        <li>
          <strong>Buy &amp; hold benchmark:</strong> Spot XAUUSD daily returns on the same dates and WF windows appear
          next to every strategy lane (consensus, categories, and raw legs) for comparison.
        </li>
        <li>
          <strong>Data contract:</strong> <code>specs/data-contract.md</code> and <code>specs/data-pipeline.md</code>.
        </li>
      </ul>
    </article>
  );
}

const css = `
.site-footer {
  margin: 2rem 0 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  max-width: 72ch;
}
.site-footer code { font-size: 0.8em; }
.load-card .load-title { font-size: 1.1rem; margin: 0 0 0.75rem; }
.load-card .load-detail { margin: 0; line-height: 1.55; max-width: 58ch; }
.hero { margin-bottom: 2rem; }
.eyebrow { text-transform: uppercase; letter-spacing: 0.2em; font-size: 0.7rem; color: var(--gold-dim); margin: 0 0 0.5rem; }
.lede { color: var(--muted); max-width: 52ch; margin: 0.5rem 0 1.25rem; }
.tabs { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
.tabs button {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 0.45rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}
.tabs button.active { border-color: var(--gold); color: var(--gold); }
.tabs button.ghost { border-style: dashed; color: var(--muted); }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
.card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
}
.card.error { border-color: #6b3030; }
.card.warn { border-color: var(--gold-dim); }
.wf-loading-banner { margin-bottom: 1rem; padding: 0.85rem 1.25rem; }
.hero-strategy {
  margin: 0.5rem 0 0;
  line-height: 1.5;
}
.strategy-pill {
  display: inline-block;
  padding: 0.2rem 0.65rem;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.strategy-pill.tuned {
  background: rgba(201, 162, 74, 0.22);
  color: var(--gold);
  border: 1px solid rgba(201, 162, 74, 0.35);
}
.strategy-pill.prod {
  background: rgba(107, 101, 96, 0.2);
  color: var(--muted);
  border: 1px solid var(--border);
}
.consensus-strategy { margin: 0 0 0.35rem; }
.consensus .date { color: var(--muted); margin-top: 0; }
.tag { display: inline-block; margin-top: 0.75rem; padding: 0.35rem 0.85rem; border-radius: 999px; font-weight: 600; font-size: 1.1rem; }
.tag.long { background: rgba(61, 154, 106, 0.2); color: var(--long); }
.tag.short { background: rgba(196, 92, 92, 0.2); color: var(--short); }
.tag.neutral { background: rgba(107, 101, 96, 0.25); color: var(--neutral); }
.conf { margin-top: 1rem; }
.muted { color: var(--muted); }
.small { font-size: 0.85rem; }
.stat { font-size: 1.05rem; }
.chart { width: 100%; height: auto; display: block; }
.legend { display: flex; gap: 1.5rem; margin-top: 0.5rem; font-size: 0.85rem; color: var(--muted); flex-wrap: wrap; }
.legend-3 { gap: 1rem 1.5rem; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.dot.gold { background: var(--gold); }
.dot.longonly { background: var(--long-only); }
.dot.muted { background: var(--muted); }
.chart-timeline { display: block; max-width: 100%; height: auto; }
.cat-list { display: flex; flex-direction: column; gap: 1rem; }
.cat-wide {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem 1.1rem;
  background: #12100e;
}
.cat-wide-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 0.75rem 1rem;
}
.cat-titles h3 { margin: 0; font-size: 1.05rem; font-family: "DM Serif Display", Georgia, serif; font-weight: 400; }
.cat-live { margin-left: auto; text-align: right; display: flex; flex-direction: column; gap: 0.25rem; align-items: flex-end; }
.cat-detail { margin: 0.65rem 0 0; color: var(--muted); line-height: 1.45; }
.cat-bt {
  margin-top: 0.85rem;
  padding-top: 0.85rem;
  border-top: 1px solid var(--border);
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.5rem;
  align-items: flex-end;
}
.cat-lo-grid { margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px dashed var(--border); width: 100%; }
.cat-bh-grid { margin-top: 0.65rem; padding-top: 0.65rem; border-top: 1px solid var(--border); width: 100%; opacity: 0.95; }
.spark-row-dual {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.5rem;
  align-items: flex-end;
  margin-top: 0.35rem;
}
.spark-row-dual .spark-wrap { flex: 1; min-width: 200px; }
.cat-lo-spark-only { margin-top: 0.5rem; }
.bt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.65rem 1.25rem;
  flex: 1;
  min-width: 200px;
}
.bt-span { grid-column: 1 / -1; }
.bt-label { display: block; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--gold-dim); margin-bottom: 0.15rem; }
.spark-wrap { display: flex; flex-direction: column; gap: 0.35rem; max-width: 100%; }
.spark { display: block; }
.spark-timeline { width: 100%; max-width: 300px; height: auto; }
.wf-steps-wrap { overflow: auto; max-height: 14rem; margin-top: 0.5rem; border: 1px solid var(--border); border-radius: 8px; }
table.wf-steps { width: 100%; font-size: 0.8rem; border-collapse: collapse; }
.wf-steps th, .wf-steps td { text-align: left; padding: 0.4rem 0.55rem; border-bottom: 1px solid var(--border); }
.wf-steps th { color: var(--gold-dim); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.68rem; }
.wf-steps tr:last-child td { border-bottom: none; }
.wf-oos-charts { margin: 0.75rem 0 1rem; }
.wf-oos-caption { margin-bottom: 0.35rem; line-height: 1.45; }
.wf-oos-svg { display: block; width: 100%; max-width: 900px; height: auto; }
.wf-oos-legend { display: flex; flex-wrap: wrap; gap: 0.75rem 1.25rem; margin-top: 0.35rem; font-size: 0.82rem; color: var(--muted); align-items: center; }
.equity-stats-block { margin: 1rem 0 1.25rem; padding: 1rem 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.equity-stats-heading { margin: 0 0 0.5rem; font-size: 1rem; font-family: "DM Serif Display", Georgia, serif; font-weight: 400; }
.stat-cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem 1.5rem; margin-top: 0.75rem; }
.stat-col-title { margin: 0 0 0.4rem; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--gold-dim); font-weight: 600; }
.stat-dl { margin: 0; display: grid; grid-template-columns: 1fr auto; gap: 0.25rem 0.75rem; font-size: 0.82rem; }
.stat-dl dt { color: var(--muted); margin: 0; }
.stat-dl dd { margin: 0; text-align: right; font-weight: 600; }
.stat-dl-inline { grid-template-columns: auto 1fr; max-width: 42rem; }
.stat-extra { margin-top: 1rem; padding-top: 0.85rem; border-top: 1px dashed var(--border); }
.stat-extra .stat-dl-inline dt { min-width: 12rem; }
.sub-legs { margin-top: 1.1rem; padding-top: 1rem; border-top: 1px solid var(--border); }
.sub-legs-title { margin: 0 0 0.35rem; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--gold-dim); font-weight: 600; }
.sub-leg-table-wrap { overflow-x: auto; margin-top: 0.5rem; }
.sub-leg-table { width: 100%; font-size: 0.78rem; border-collapse: collapse; min-width: 1320px; }
.sub-leg-table th, .sub-leg-table td { text-align: left; padding: 0.45rem 0.4rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
.sub-leg-table th { color: var(--gold-dim); font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.04em; }
.sub-leg-name { max-width: 15rem; line-height: 1.35; }
.sub-leg-spark .spark-timeline { max-width: 220px; }
.nowrap { white-space: nowrap; }
.cid { font-weight: 600; color: var(--gold); font-size: 1.25rem; min-width: 1.5rem; }
.raw { font-size: 0.8rem; color: var(--muted); }
pre.cmd {
  background: #1c1a17;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.85rem 1rem;
  font-size: 0.8rem;
  overflow-x: auto;
  margin: 0.75rem 0;
  white-space: pre-wrap;
}
.prose ul { padding-left: 1.2rem; }
.prose li { margin-bottom: 0.65rem; }
code { font-size: 0.88em; background: #1c1a17; padding: 0.1rem 0.35rem; border-radius: 4px; }
`;
