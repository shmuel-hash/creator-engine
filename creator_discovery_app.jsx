import { useState, useRef, useEffect, createContext, useContext } from "react";

const API = "https://creator-engine-production.up.railway.app/api";

const ThemeCtx = createContext();
const useTheme = () => useContext(ThemeCtx);

const themes = {
  dark: {
    bg: "#080812", surface: "#0e0e20", surfaceAlt: "#13132a",
    border: "#1c1c38", borderHover: "#4f46e5",
    text: "#e2e2f0", textSoft: "#9494b8", textDim: "#5a5a7e",
    accent: "#6366f1", accentSoft: "#818cf8",
    green: "#10b981", greenBg: "#10b98112",
    amber: "#eab308", amberBg: "#eab30812",
    red: "#ef4444", redBg: "#ef444412",
    cyan: "#06b6d4", cardShadow: "none", inputBg: "#0e0e20",
  },
  light: {
    bg: "#f8f8fb", surface: "#ffffff", surfaceAlt: "#f3f3f8",
    border: "#e4e4ec", borderHover: "#6366f1",
    text: "#1a1a2e", textSoft: "#6b6b85", textDim: "#9e9eb5",
    accent: "#4f46e5", accentSoft: "#6366f1",
    green: "#059669", greenBg: "#05966912",
    amber: "#d97706", amberBg: "#d9770612",
    red: "#dc2626", redBg: "#dc262612",
    cyan: "#0891b2",
    cardShadow: "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
    inputBg: "#f3f3f8",
  },
};

const FONT = "'Outfit', system-ui, sans-serif";
const MONO = "'DM Mono', monospace";

const PLATFORMS = {
  tiktok: { name: "TikTok", color: "#ff0050" },
  instagram: { name: "Instagram", color: "#C13584" },
  youtube: { name: "YouTube", color: "#FF0000" },
  twitter: { name: "X", color: "#1DA1F2" },
  reddit: { name: "Reddit", color: "#FF4500" },
  ugc_marketplace: { name: "UGC", color: "#7c3aed" },
  unknown: { name: "Web", color: "#6b7280" },
};

const PRESETS = [
  { label: "Doctors / Medical", q: "doctor MD physician health medical creator TikTok" },
  { label: "Gen Z Wellness", q: "gen z wellness healthy lifestyle young creator TikTok" },
  { label: "Fitness", q: "fitness workout gym personal trainer creator TikTok Instagram" },
  { label: "Mom / Family", q: "mom parenting family lifestyle creator TikTok Instagram" },
  { label: "Gut Health", q: "gut health microbiome probiotics creator TikTok" },
  { label: "Heart Health", q: "heart health cardiology cardiovascular supplement creator" },
  { label: "Longevity", q: "longevity anti-aging biohacking NAD creator TikTok" },
  { label: "UGC for Hire", q: "UGC creator for hire supplement health wellness" },
];

function fmt(n) { return n >= 1e6 ? (n/1e6).toFixed(1)+"M" : n >= 1e3 ? (n/1e3).toFixed(1)+"K" : n?.toString() || "—"; }

function Badge({ children, color }) {
  const t = useTheme();
  const c = color || t.accent;
  return <span style={{ display: "inline-flex", fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 4, letterSpacing: 0.3, background: c + "14", color: c }}>{children}</span>;
}

function Btn({ children, onClick, variant = "primary", disabled, small }) {
  const t = useTheme();
  const styles = {
    primary: { background: t.accent, color: "#fff", border: "none" },
    ghost: { background: "transparent", color: t.textSoft, border: `1px solid ${t.border}` },
    success: { background: t.green, color: "#fff", border: "none" },
  };
  return <button onClick={onClick} disabled={disabled} style={{
    padding: small ? "5px 12px" : "9px 18px", borderRadius: 7, cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: FONT, fontWeight: 600, fontSize: small ? 11 : 12, letterSpacing: 0.2,
    transition: "all 0.15s", opacity: disabled ? 0.4 : 1,
    display: "inline-flex", alignItems: "center", gap: 6, ...styles[variant],
  }}>{children}</button>;
}

function ScoreRing({ score, size = 32 }) {
  const t = useTheme();
  const r = (size - 4) / 2, circ = 2 * Math.PI * r;
  const color = score >= 80 ? t.green : score >= 60 ? t.amber : t.red;
  return <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={t.border} strokeWidth={2.5} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={2.5}
        strokeDasharray={circ} strokeDashoffset={circ - (score/100) * circ} strokeLinecap="round" />
    </svg>
    <span style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 9, fontWeight: 700, color, fontFamily: MONO }}>{score}</span>
  </div>;
}

function Section({ label, children }) {
  const t = useTheme();
  return <div style={{ marginBottom: 12 }}>
    <div style={{ fontSize: 9, color: t.textDim, fontWeight: 700, letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 6 }}>{label}</div>
    {children}
  </div>;
}

function StrategyPanel({ strategy }) {
  const t = useTheme();
  const [open, setOpen] = useState(false);
  if (!strategy || strategy.error) return null;

  return <div style={{ marginTop: 10, borderRadius: 8, overflow: "hidden", border: `1px solid ${t.border}`, background: t.surfaceAlt }}>
    <div onClick={() => setOpen(!open)} style={{ padding: "10px 14px", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 14 }}>🎯</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: t.text }}>Outreach Strategy</span>
        {strategy.recommended_product && <Badge color={t.accent}>{strategy.recommended_product}</Badge>}
        {strategy.brand_fit_score && <Badge color={strategy.brand_fit_score >= 7 ? t.green : t.amber}>Fit: {strategy.brand_fit_score}/10</Badge>}
      </div>
      <span style={{ color: t.textDim, fontSize: 11 }}>{open ? "▾" : "▸"}</span>
    </div>

    {open && <div style={{ padding: "0 14px 14px", borderTop: `1px solid ${t.border}` }}>
      {strategy.creator_summary && <p style={{ fontSize: 12, color: t.textSoft, lineHeight: 1.65, margin: "12px 0", padding: "10px 12px", background: t.accent + "08", borderRadius: 6, borderLeft: `3px solid ${t.accent}` }}>{strategy.creator_summary}</p>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, margin: "10px 0 14px" }}>
        {[
          { label: "Product", val: strategy.recommended_product, c: t.accent },
          { label: "Fit", val: `${strategy.brand_fit_score}/10`, c: strategy.brand_fit_score >= 7 ? t.green : t.amber },
          { label: "Priority", val: strategy.priority_level?.toUpperCase(), c: strategy.priority_level === "high" ? t.green : t.amber },
          { label: "Est. Rate", val: strategy.estimated_rate_range, c: t.cyan },
        ].map((m, i) => <div key={i} style={{ padding: "8px 10px", borderRadius: 6, background: t.bg, borderLeft: `3px solid ${m.c}` }}>
          <div style={{ fontSize: 9, color: t.textDim, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 2 }}>{m.label}</div>
          <div style={{ fontSize: 11, fontWeight: 700, color: m.c }}>{m.val || "—"}</div>
        </div>)}
      </div>

      {strategy.outreach_angle && <Section label="Outreach Angle"><p style={{ fontSize: 12, color: t.text, lineHeight: 1.6, margin: 0 }}>{strategy.outreach_angle}</p></Section>}

      {strategy.past_partnerships?.length > 0 && <Section label="Known Partnerships">
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>{strategy.past_partnerships.map((p, i) => <Badge key={i} color={t.amber}>{p}</Badge>)}</div>
        {strategy.partnership_insights && <p style={{ fontSize: 11, color: t.textSoft, marginTop: 6, lineHeight: 1.5 }}>{strategy.partnership_insights}</p>}
      </Section>}

      {strategy.personalization_hooks?.length > 0 && <Section label="Personalization Hooks">
        {strategy.personalization_hooks.map((h, i) => <div key={i} style={{ fontSize: 11, color: t.text, padding: "3px 0 3px 10px", borderLeft: `2px solid ${t.accent}30`, marginBottom: 3, lineHeight: 1.5 }}>{h}</div>)}
      </Section>}

      {strategy.content_ideas?.length > 0 && <Section label="Content Ideas for Luma">
        {strategy.content_ideas.map((idea, i) => <div key={i} style={{ fontSize: 11, color: t.text, padding: "3px 0 3px 10px", borderLeft: `2px solid ${t.green}30`, marginBottom: 3, lineHeight: 1.5 }}>{idea}</div>)}
      </Section>}

      {strategy.suggested_email_body && <Section label="Draft Outreach Email">
        {strategy.suggested_subject_line && <div style={{ fontSize: 10, color: t.textDim, marginBottom: 6 }}>Subject: <span style={{ color: t.accent, fontWeight: 600 }}>{strategy.suggested_subject_line}</span></div>}
        <pre style={{ fontSize: 11, color: t.text, lineHeight: 1.65, whiteSpace: "pre-wrap", padding: 12, background: t.bg, borderRadius: 6, border: `1px solid ${t.border}`, fontFamily: FONT, margin: 0 }}>{strategy.suggested_email_body}</pre>
      </Section>}

      {strategy.red_flags?.length > 0 && <Section label="⚠ Flags to Consider">
        {strategy.red_flags.map((f, i) => <div key={i} style={{ fontSize: 11, color: t.red, opacity: 0.85, padding: "2px 0" }}>• {f}</div>)}
      </Section>}
    </div>}
  </div>;
}

function CreatorCard({ creator, onEnrich, onSave, enriching }) {
  const t = useTheme();
  const [open, setOpen] = useState(false);
  const strategy = creator.ai_analysis?.outreach_strategy || creator.strategy;
  const p = creator.platform || (creator.tiktok_url ? "tiktok" : creator.instagram_url ? "instagram" : "unknown");
  const plat = PLATFORMS[p] || PLATFORMS.unknown;
  const handle = creator.handle || creator.tiktok_handle || creator.instagram_handle || "";

  return <div style={{ background: t.surface, border: `1px solid ${open ? t.borderHover : t.border}`, borderRadius: 10, overflow: "hidden", transition: "border-color 0.2s", boxShadow: t.cardShadow }}>
    <div onClick={() => setOpen(!open)} style={{ padding: "14px 16px", cursor: "pointer" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: t.text }}>{creator.name}</span>
            {creator.relevance_score > 0 && <ScoreRing score={Math.round(creator.relevance_score)} />}
          </div>
          {handle && <div style={{ fontSize: 11, color: t.accentSoft, fontWeight: 500, marginTop: 1 }}>{handle}</div>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Badge color={plat.color}>{plat.name}</Badge>
          {creator.saved && <div style={{ width: 7, height: 7, borderRadius: "50%", background: t.green }} />}
        </div>
      </div>
      {creator.bio && <p style={{ fontSize: 11, color: t.textSoft, margin: "0 0 8px", lineHeight: 1.5, maxHeight: open ? "none" : 32, overflow: "hidden" }}>{creator.bio}</p>}
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 6 }}>
        {(creator.categories || []).slice(0, open ? 15 : 3).map((c, i) => <Badge key={i}>{c}</Badge>)}
        {!open && (creator.categories || []).length > 3 && <span style={{ fontSize: 10, color: t.textDim }}>+{creator.categories.length - 3}</span>}
      </div>
      <div style={{ display: "flex", gap: 14, fontSize: 11, color: t.textDim }}>
        {(creator.followers || creator.total_followers) > 0 && <span><b style={{ color: t.text }}>{fmt(creator.followers || creator.total_followers)}</b> followers</span>}
        {creator.engagement_rate > 0 && <span><b style={{ color: t.text }}>{creator.engagement_rate}%</b> eng</span>}
        {creator.hero_video_rate > 0 && <span><b style={{ color: t.green }}>${creator.hero_video_rate}</b> /video</span>}
        {creator.email && <span style={{ color: t.green }}>✉ email</span>}
      </div>
    </div>

    {open && <div style={{ borderTop: `1px solid ${t.border}`, padding: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 16px", fontSize: 12, marginBottom: 12 }}>
        {[
          creator.email && ["Email", creator.email, t.text],
          creator.phone && ["Phone", creator.phone, t.text],
          creator.age && ["Age", creator.age, t.text],
          creator.gender && ["Gender", creator.gender, t.text],
          creator.quality_tier && ["Quality", creator.quality_tier, t.text],
          creator.pipeline_stage && ["Stage", creator.pipeline_stage, t.text],
          strategy?.recommended_product && ["Best product", strategy.recommended_product, t.accent],
          strategy?.estimated_rate_range && ["Est. rate", strategy.estimated_rate_range, t.green],
        ].filter(Boolean).map(([k, v, c], i) => <div key={i}><span style={{ color: t.textDim }}>{k} </span><span style={{ color: c }}>{v}</span></div>)}
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
        {creator.tiktok_url && <a href={creator.tiktok_url} target="_blank" rel="noreferrer" style={{ fontSize: 10, color: "#ff0050", textDecoration: "none", padding: "3px 8px", border: "1px solid #ff005025", borderRadius: 4, fontWeight: 500 }}>TikTok ↗</a>}
        {creator.instagram_url && <a href={creator.instagram_url} target="_blank" rel="noreferrer" style={{ fontSize: 10, color: "#C13584", textDecoration: "none", padding: "3px 8px", border: "1px solid #C1358425", borderRadius: 4, fontWeight: 500 }}>Instagram ↗</a>}
        {creator.youtube_url && <a href={creator.youtube_url} target="_blank" rel="noreferrer" style={{ fontSize: 10, color: "#FF0000", textDecoration: "none", padding: "3px 8px", border: "1px solid #FF000025", borderRadius: 4, fontWeight: 500 }}>YouTube ↗</a>}
        {creator.profile_url && !creator.tiktok_url && <a href={creator.profile_url} target="_blank" rel="noreferrer" style={{ fontSize: 10, color: t.accent, textDecoration: "none", padding: "3px 8px", border: `1px solid ${t.accent}25`, borderRadius: 4, fontWeight: 500 }}>Profile ↗</a>}
      </div>

      <StrategyPanel strategy={strategy} />

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <Btn onClick={() => onEnrich(creator)} variant={strategy ? "ghost" : "primary"} disabled={enriching}>
          {enriching ? "Analyzing..." : strategy ? "↻ Re-analyze" : "🔍 Analyze & Build Strategy"}
        </Btn>
        {!creator.saved && <Btn onClick={() => onSave(creator)} variant="success">Save</Btn>}
        {creator.email && <Btn variant="ghost" onClick={() => window.open(`mailto:${creator.email}`)}>✉ Email</Btn>}
      </div>
    </div>}
  </div>;
}

// ─── STATUS BANNER ───
function StatusBanner({ apiStatus }) {
  const t = useTheme();
  if (apiStatus === "connected") return null;
  const color = apiStatus === "checking" ? t.amber : t.red;
  return <div style={{ padding: "6px 14px", background: color + "15", borderBottom: `1px solid ${color}30`, fontSize: 11, color, textAlign: "center", fontWeight: 500 }}>
    {apiStatus === "checking" ? "Connecting to backend..." : "⚠ Backend not reachable — make sure Railway is running"}
  </div>;
}

// ─── MAIN APP ───
export default function App() {
  const [mode, setMode] = useState("dark");
  const t = themes[mode];
  const toggleMode = () => setMode(m => m === "dark" ? "light" : "dark");

  const [tab, setTab] = useState("discover");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState([]);
  const [creators, setCreators] = useState([]);
  const [filter, setFilter] = useState("");
  const [enrichingId, setEnrichingId] = useState(null);
  const [importStatus, setImportStatus] = useState(null);
  const [apiStatus, setApiStatus] = useState("checking");
  const fileRef = useRef(null);

  // Check backend connection on mount
  useEffect(() => {
    fetch(`${API.replace('/api', '')}/health`).then(r => {
      if (r.ok) { setApiStatus("connected"); loadCreators(); }
      else setApiStatus("error");
    }).catch(() => setApiStatus("error"));
  }, []);

  const doSearch = async (q) => {
    if (!q.trim()) return;
    setSearching(true);
    try {
      const r = await fetch(`${API}/discover`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, platforms: ["tiktok","instagram","youtube","twitter","reddit"], max_results: 20 }),
      });
      if (r.ok) { const d = await r.json(); setResults(d.results || []); }
    } catch (e) { console.error("Search failed:", e); }
    setSearching(false);
  };

  const doImport = async (file) => {
    setImportStatus({ s: "loading", m: `Importing ${file.name}...` });
    try {
      const form = new FormData(); form.append("file", file);
      const r = await fetch(`${API}/import`, { method: "POST", body: form });
      if (r.ok) {
        const d = await r.json();
        setImportStatus({ s: "done", m: `Imported ${d.imported}/${d.total_rows} creators, ${d.duplicates_skipped} duplicates skipped` });
        loadCreators();
      } else { setImportStatus({ s: "error", m: "Import failed — check file format" }); }
    } catch { setImportStatus({ s: "error", m: "Could not connect to backend" }); }
  };

  const loadCreators = async () => {
    try { const r = await fetch(`${API}/creators?per_page=200`); if (r.ok) { const d = await r.json(); setCreators(d.creators || []); } } catch {}
  };

  const doEnrich = async (creator) => {
    setEnrichingId(creator.id);
    try {
      const r = await fetch(`${API}/creators/${creator.id}/enrich`, { method: "POST" });
      if (r.ok) {
        const d = await r.json();
        setCreators(prev => prev.map(c => c.id === creator.id ? {
          ...c,
          ai_analysis: { outreach_strategy: d.outreach_strategy },
          email: d.email_search?.primary_email || c.email,
          relevance_score: d.outreach_strategy?.brand_fit_score ? d.outreach_strategy.brand_fit_score * 10 : c.relevance_score,
        } : c));
      }
    } catch (e) { console.error("Enrich failed:", e); }
    setEnrichingId(null);
  };

  const doSave = async (result) => {
    try {
      const r = await fetch(`${API}/discover/results/${result.id}/save`, { method: "POST" });
      if (r.ok) {
        const saved = await r.json();
        setCreators(prev => [...prev, saved]);
        setResults(prev => prev.map(x => x.id === result.id ? { ...x, saved: true, creator_id: saved.id } : x));
      }
    } catch {}
  };

  const filteredCreators = creators.filter(c => {
    if (!filter) return true;
    const s = filter.toLowerCase();
    return c.name?.toLowerCase().includes(s) || c.email?.toLowerCase().includes(s) ||
      (c.categories || []).some(cat => cat.toLowerCase().includes(s)) ||
      c.tiktok_handle?.toLowerCase().includes(s) || c.instagram_handle?.toLowerCase().includes(s);
  });

  return <ThemeCtx.Provider value={t}>
    <div style={{ minHeight: "100vh", background: t.bg, color: t.text, fontFamily: FONT, transition: "background 0.3s, color 0.3s" }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet" />

      <StatusBanner apiStatus={apiStatus} />

      <header style={{ padding: "12px 24px", borderBottom: `1px solid ${t.border}`, display: "flex", justifyContent: "space-between", alignItems: "center", background: t.surface, transition: "background 0.3s" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 30, height: 30, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 800, background: `linear-gradient(135deg, ${t.accent}, ${t.cyan})`, color: "#fff" }}>L</div>
          <div>
            <h1 style={{ margin: 0, fontSize: 14, fontWeight: 800, letterSpacing: -0.3 }}>Creator Discovery</h1>
            <span style={{ fontSize: 9, color: t.textDim, fontWeight: 600, letterSpacing: 0.6, textTransform: "uppercase" }}>Luma Nutrition</span>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ display: "flex", gap: 1, background: t.bg, borderRadius: 7, padding: 2 }}>
            {[
              { id: "discover", label: "Discover", ct: results.length },
              { id: "database", label: "Database", ct: creators.length },
              { id: "import", label: "Import" },
            ].map(x => <button key={x.id} onClick={() => setTab(x.id)} style={{
              padding: "6px 14px", borderRadius: 5, border: "none", cursor: "pointer", fontFamily: FONT,
              background: tab === x.id ? t.accent : "transparent", color: tab === x.id ? "#fff" : t.textSoft,
              fontSize: 11, fontWeight: 600, transition: "all 0.15s",
            }}>{x.label}{x.ct > 0 ? ` ${x.ct}` : ""}</button>)}
          </div>
          <button onClick={toggleMode} aria-label="Toggle theme" style={{
            width: 38, height: 22, borderRadius: 11, border: `1px solid ${t.border}`,
            background: mode === "dark" ? t.accent + "25" : t.amber + "20",
            cursor: "pointer", position: "relative", padding: 0, transition: "all 0.3s",
          }}>
            <div style={{
              width: 16, height: 16, borderRadius: "50%", position: "absolute", top: 2,
              left: mode === "dark" ? 3 : 19, transition: "left 0.25s ease",
              background: mode === "dark" ? t.accentSoft : t.amber,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9,
            }}>{mode === "dark" ? "🌙" : "☀️"}</div>
          </button>
        </div>
      </header>

      <main style={{ padding: "20px 24px", maxWidth: 1060, margin: "0 auto" }}>

        {tab === "discover" && <>
          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, background: t.inputBg, border: `1px solid ${t.border}`, borderRadius: 8, padding: "0 14px" }}>
              <span style={{ color: t.accent, fontSize: 15 }}>⊕</span>
              <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && doSearch(query)}
                placeholder="Describe who you're looking for..." style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: t.text, fontSize: 13, padding: "11px 0", fontFamily: FONT }} />
            </div>
            <Btn onClick={() => doSearch(query)} disabled={searching || !query.trim()}>{searching ? "Searching..." : "Discover"}</Btn>
          </div>
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 20 }}>
            <span style={{ fontSize: 10, color: t.textDim, alignSelf: "center" }}>Quick:</span>
            {PRESETS.map(p => <button key={p.label} onClick={() => { setQuery(p.q); doSearch(p.q); }} style={{
              padding: "4px 9px", borderRadius: 4, border: `1px solid ${t.border}`, background: "transparent",
              color: t.textSoft, fontSize: 10, cursor: "pointer", fontFamily: FONT, fontWeight: 500,
            }}>{p.label}</button>)}
          </div>

          {searching && <div style={{ textAlign: "center", padding: 50 }}>
            <div style={{ display: "inline-block", width: 24, height: 24, border: `2.5px solid ${t.border}`, borderTopColor: t.accent, borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
            <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
            <p style={{ fontSize: 12, color: t.textSoft, marginTop: 10 }}>Searching TikTok, Instagram, YouTube, Reddit & more...</p>
          </div>}

          {!searching && results.length > 0 && <>
            <p style={{ fontSize: 12, fontWeight: 600, color: t.textSoft, marginBottom: 10 }}>{results.length} creators found</p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 10 }}>
              {results.map(r => <CreatorCard key={r.id} creator={r} onEnrich={doEnrich} onSave={() => doSave(r)} enriching={enrichingId === r.id || enrichingId === r.creator_id} />)}
            </div>
          </>}

          {!searching && results.length === 0 && <div style={{ textAlign: "center", padding: "50px 20px" }}>
            <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.5 }}>🔍</div>
            <h3 style={{ margin: "0 0 6px", fontSize: 15, fontWeight: 700 }}>Find Hard-to-Find Creators</h3>
            <p style={{ fontSize: 12, color: t.textSoft, maxWidth: 380, margin: "0 auto", lineHeight: 1.6 }}>
              Search for doctors, Gen Z wellness creators, niche UGC talent. The AI searches TikTok, Instagram, YouTube, Reddit, and UGC marketplaces.
            </p>
          </div>}
        </>}

        {tab === "database" && <>
          <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
            <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, background: t.inputBg, border: `1px solid ${t.border}`, borderRadius: 8, padding: "0 14px" }}>
              <span style={{ color: t.textDim, fontSize: 13 }}>⌕</span>
              <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Filter by name, category, handle..."
                style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: t.text, fontSize: 12, padding: "10px 0", fontFamily: FONT }} />
            </div>
            <Btn variant="ghost" onClick={loadCreators} small>↻ Refresh</Btn>
          </div>
          <p style={{ fontSize: 11, color: t.textDim, marginBottom: 10 }}>{filteredCreators.length} creators</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 10 }}>
            {filteredCreators.map(c => <CreatorCard key={c.id} creator={{ ...c, saved: true }} onEnrich={() => doEnrich(c)} onSave={() => {}} enriching={enrichingId === c.id} />)}
          </div>
          {filteredCreators.length === 0 && <p style={{ textAlign: "center", padding: 30, color: t.textDim, fontSize: 12 }}>
            {creators.length === 0 ? "No creators yet. Import a spreadsheet or discover new ones." : "No match."}
          </p>}
        </>}

        {tab === "import" && <>
          <div
            onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = t.accent; }}
            onDragLeave={e => { e.currentTarget.style.borderColor = t.border; }}
            onDrop={e => { e.preventDefault(); e.currentTarget.style.borderColor = t.border; doImport(e.dataTransfer.files[0]); }}
            onClick={() => fileRef.current?.click()}
            style={{ border: `2px dashed ${t.border}`, borderRadius: 10, padding: "32px 20px", textAlign: "center", cursor: "pointer", marginBottom: 14, transition: "border-color 0.2s" }}>
            <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" onChange={e => e.target.files?.[0] && doImport(e.target.files[0])} style={{ display: "none" }} />
            <div style={{ fontSize: 26, marginBottom: 6, opacity: 0.6 }}>📊</div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Drop your creator spreadsheet here</div>
            <div style={{ fontSize: 11, color: t.textSoft, marginTop: 3 }}>CSV or Excel • Auto-maps 37+ columns</div>
          </div>
          {importStatus && <div style={{
            padding: "9px 14px", borderRadius: 7, fontSize: 12, marginBottom: 14,
            background: importStatus.s === "done" ? t.greenBg : importStatus.s === "error" ? t.redBg : t.accent + "10",
            color: importStatus.s === "done" ? t.green : importStatus.s === "error" ? t.red : t.accentSoft,
            borderLeft: `3px solid ${importStatus.s === "done" ? t.green : importStatus.s === "error" ? t.red : t.accent}`,
          }}>{importStatus.m}</div>}
        </>}
      </main>
    </div>
  </ThemeCtx.Provider>;
}
