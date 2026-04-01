import React, { useState, useEffect, useCallback, useRef, useMemo, useContext } from 'react';
import { api, CREATOR_TYPES, CONTENT_NICHES } from '../utils/api';
import { I } from './Icons';
import Pill from './Pill';
import CreatorCard from './CreatorCard';
import ListItem from './ListItem';
import { DetailCtx } from './DetailContext';

const GENERAL_PRESETS = [
  { l: 'Doctor TikTok', q: 'doctors who talk about heart health on TikTok' },
  { l: 'Gen Z Wellness', q: 'Gen Z wellness creators on Instagram and TikTok' },
  { l: 'Gut Health', q: 'gut health nutrition creators with 50k-500k followers' },
  { l: 'Mom Creators', q: 'mom health and fitness influencers on Instagram' },
  { l: 'UGC Health', q: 'UGC creators specializing in health supplements' },
  { l: 'Longevity', q: 'longevity biohacking creators on YouTube' },
];

const DOCTOR_PRESETS = [
  { l: 'Cardiologists', q: 'cardiologists who create content about heart health on TikTok and Instagram' },
  { l: 'GI Doctors', q: 'gastroenterologists and GI doctors who talk about gut health on social media' },
  { l: 'Longevity MDs', q: 'anti-aging and longevity doctors with social media presence' },
  { l: 'RDs & Dietitians', q: 'registered dietitians who review supplements and talk about nutrition' },
  { l: 'Pharmacists', q: 'pharmacists who review supplements on TikTok and YouTube' },
  { l: 'NPs & PAs', q: 'nurse practitioners and physician assistants who create health content' },
  { l: 'Sleep Doctors', q: 'sleep medicine doctors who create content about sleep health' },
  { l: 'Endocrinologists', q: 'endocrinologists who discuss blood sugar and metabolic health on social media' },
];

const BRAND_INTEL_PRESETS = [
  { l: 'Athletic Greens', q: 'creators who partner with or mention Athletic Greens AG1', b: '@drinkag1' },
  { l: 'Seed Health', q: 'creators who promote Seed probiotics and gut health supplements', b: '@seed' },
  { l: 'Ritual', q: 'creators who partner with Ritual vitamins and supplements', b: '@ritual' },
  { l: 'Thorne', q: 'creators who review or promote Thorne supplements', b: '@thaborneresearch' },
  { l: 'Bloom Nutrition', q: 'creators who partner with Bloom Nutrition greens and supplements', b: '@bloomnu' },
  { l: 'LMNT', q: 'creators who promote LMNT electrolyte supplements', b: '@drinklmnt' },
];

const STATUS_LABELS = {
  starting: 'Starting search...',
  parsing_intent: 'Understanding your query...',
  searching: 'Searching across platforms...',
  analyzing: 'Analyzing and scoring creators...',
  deep_searching: 'Digging deeper — LinkedIn, Reddit, talent agencies...',
  complete: 'Complete',
  failed: 'Failed',
};

export default function DiscoverTab() {
  const { setSelected } = useContext(DetailCtx);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchStatus, setSearchStatus] = useState(null);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [resultCount, setResultCount] = useState(20);
  const [existing, setExisting] = useState([]);
  const [viewMode, setViewMode] = useState('grid');
  const [typeFilter, setTypeFilter] = useState('');
  const [nicheFilter, setNicheFilter] = useState('');
  const [batchEnriching, setBatchEnriching] = useState(false);
  const [savedThisSession, setSavedThisSession] = useState(new Set());
  const [searchMode, setSearchMode] = useState('general');
  const [credentialFilter, setCredentialFilter] = useState('');
  const [deepSearching, setDeepSearching] = useState(false);
  const [brandHandles, setBrandHandles] = useState('');
  const [recentSearches, setRecentSearches] = useState([]);
  const [searchStartTime, setSearchStartTime] = useState(null);
  const [elapsed, setElapsed] = useState(0);

  const doctorMode = searchMode === 'doctor';
  const brandIntelMode = searchMode === 'brand_intel';
  const pollRef = useRef(null);
  const batchPollRef = useRef(null);
  const deepPollRef = useRef(null);
  const timerRef = useRef(null);

  // Elapsed timer — ticks every second while searching
  useEffect(() => {
    if ((searching || deepSearching) && searchStartTime) {
      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - searchStartTime) / 1000));
      }, 1000);
      return () => clearInterval(timerRef.current);
    } else {
      setElapsed(0);
      clearInterval(timerRef.current);
    }
  }, [searching, deepSearching, searchStartTime]);

  useEffect(() => { api('/creators', { params: { per_page: 500 } }).then(d => setExisting(d.creators || [])).catch(() => {}); }, []);

  // On mount: load recent searches + restore last search or resume running search
  const mountedRef = useRef(false);
  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;
    api('/discover/history').then(history => {
      const completed = (history || []).filter(s => s.status === 'complete' && s.results_count > 0);
      setRecentSearches(completed.slice(0, 6));
      const running = (history || []).find(s => ['starting', 'parsing_intent', 'searching', 'analyzing', 'deep_searching'].includes(s.status));
      if (running) {
        setSearching(running.status !== 'deep_searching');
        setDeepSearching(running.status === 'deep_searching');
        setQuery(running.query || '');
        setSearchStatus({ status: running.status });
        pollRef.current = setInterval(async () => {
          try {
            const st = await api(`/discover/${running.id}`);
            setSearchStatus(st);
            if (st.status === 'complete') { clearInterval(pollRef.current); setResults(st); setSearching(false); setDeepSearching(false); api('/creators', { params: { per_page: 500 } }).then(d => setExisting(d.creators || [])).catch(() => {}); }
            else if (st.status === 'failed') { clearInterval(pollRef.current); setError(st.error || 'Search failed'); setSearching(false); setDeepSearching(false); }
          } catch (e) { /* ignore */ }
        }, 3000);
      } else if (!results && completed.length > 0) {
        const last = completed[0];
        api(`/discover/${last.id}`).then(st => {
          if (st.status === 'complete' && st.results) { setResults(st); setQuery(last.query || ''); setSearchStatus(st); }
        }).catch(() => {});
      }
    }).catch(() => {});
  }, []);

  const dedupSet = useMemo(() => {
    const s = new Set();
    existing.forEach(c => {
      if (c.name) s.add(c.name.toLowerCase().trim());
      if (c.email) s.add(c.email.toLowerCase().trim());
      ['tiktok_handle', 'instagram_handle', 'youtube_handle', 'twitter_handle'].forEach(k => { if (c[k]) s.add(c[k].toLowerCase().replace('@', '').trim()); });
    });
    return s;
  }, [existing]);

  const checkDup = (r) => {
    if (savedThisSession.has(r.id) || r._saved) return false;
    if (r.name && dedupSet.has(r.name.toLowerCase().trim())) return true;
    if (r.email && dedupSet.has(r.email.toLowerCase().trim())) return true;
    const h = (r.handle || '').toLowerCase().replace('@', '').trim();
    return h && dedupSet.has(h);
  };

  const handleCancel = () => {
    clearInterval(pollRef.current); clearInterval(deepPollRef.current);
    setSearching(false); setDeepSearching(false); setSearchStatus(null); setSearchStartTime(null);
    if (results?.search_id) api(`/discover/${results.search_id}/cancel`, { method: 'POST' }).catch(() => {});
  };

  const loadPastSearch = (s) => {
    setError(null); setResults(null); setSearchStatus(null); setQuery(s.query || '');
    api(`/discover/${s.id}`).then(st => {
      if (st.status === 'complete' && st.results) { setResults(st); setSearchStatus(st); }
      else { setError('Search results not available'); }
    }).catch(e => setError(e.message));
  };

  const presets = searchMode === 'doctor' ? DOCTOR_PRESETS : searchMode === 'brand_intel' ? BRAND_INTEL_PRESETS : GENERAL_PRESETS;
  const statusLabels = { ...STATUS_LABELS, searching: searchMode === 'brand_intel' ? 'Scraping brand profiles & searching web...' : 'Searching across platforms...' };

  const doSearch = async (q, brandOverride) => {
    if (!q.trim()) return;
    setSearching(true); setError(null); setResults(null); setSearchStatus(null); setCredentialFilter(''); setSearchStartTime(Date.now()); clearInterval(pollRef.current);
    const body = { query: q, platforms: ['tiktok', 'instagram', 'youtube'], max_results: resultCount, search_mode: searchMode };
    if (searchMode === 'brand_intel') {
      const handles = (brandOverride || brandHandles).split(',').map(h => h.trim()).filter(Boolean);
      if (handles.length > 0) body.brand_handles = handles;
    }
    try {
      const d = await api('/discover', { method: 'POST', body });
      setSearchStatus({ status: 'starting' });
      pollRef.current = setInterval(async () => {
        try {
          const st = await api(`/discover/${d.search_id}`);
          setSearchStatus(st);
          if (st.status === 'complete') { clearInterval(pollRef.current); setResults(st); setSearching(false); setSearchStartTime(null); api('/creators', { params: { per_page: 500 } }).then(d => setExisting(d.creators || [])).catch(() => {}); }
          else if (st.status === 'failed') { clearInterval(pollRef.current); setError(st.error || 'Search failed'); setSearching(false); setSearchStartTime(null); }
        } catch (e) { /* ignore */ }
      }, 3000);
    } catch (e) { setError(e.message); setSearching(false); }
  };

  useEffect(() => () => { clearInterval(pollRef.current); clearInterval(batchPollRef.current); clearInterval(deepPollRef.current); }, []);

  const handleGoDeeper = async () => {
    if (!results?.search_id) return;
    setDeepSearching(true); setSearchStatus({ status: 'deep_searching' });
    try {
      await api(`/discover/${results.search_id}/go-deeper`, { method: 'POST' });
      deepPollRef.current = setInterval(async () => {
        try {
          const st = await api(`/discover/${results.search_id}`);
          setSearchStatus(st);
          if (st.status === 'complete') { clearInterval(deepPollRef.current); setResults(st); setDeepSearching(false); }
          else if (st.status === 'failed') { clearInterval(deepPollRef.current); setDeepSearching(false); setError(st.error || 'Deep search failed'); }
        } catch (e) { /* ignore */ }
      }, 3000);
    } catch (e) { setError(e.message); setDeepSearching(false); }
  };

  const handleSAE = async (result) => {
    const saved = await api(`/discover/results/${result.id}/save-and-enrich`, { method: 'POST' });
    setSavedThisSession(prev => new Set([...prev, result.id]));
    setResults(p => p ? { ...p, results: p.results.map(r => r.id === result.id ? { ...r, _saved: true, _enrichingCreatorId: saved.creator.id } : r) } : p);
    if (saved.creator) setExisting(p => [...p, saved.creator]);
    return saved;
  };

  const handleSaveAll = async () => {
    if (!results?.search_id) return;
    setBatchEnriching(true);
    try {
      const resp = await api(`/discover/${results.search_id}/save-and-enrich-all`, { method: 'POST' });
      if (resp.creators?.length) {
        const drIds = resp.creators.map(c => c.discovery_result_id);
        setSavedThisSession(prev => new Set([...prev, ...drIds]));
        setResults(p => p ? { ...p, results: p.results.map(r => { const match = resp.creators.find(c => c.discovery_result_id === r.id); return match ? { ...r, _saved: true, _enrichingCreatorId: match.id } : r; }) } : p);
        batchPollRef.current = setInterval(async () => {
          let pending = 0;
          for (const cr of resp.creators) {
            try {
              const s = await api(`/creators/${cr.id}/enrich/status`);
              if (s.status === 'complete') {
                try { const full = await api(`/creators/${cr.id}`); setResults(p => p ? { ...p, results: p.results.map(r => r.id === cr.discovery_result_id ? { ...r, ...full, _saved: true, _enriched: true, id: r.id } : r) } : p); } catch (e) { /* ignore */ }
              } else if (s.status !== 'failed') pending++;
            } catch (e) { /* ignore */ }
          }
          if (pending === 0) { clearInterval(batchPollRef.current); setBatchEnriching(false); }
        }, 4000);
      } else { setBatchEnriching(false); }
    } catch (e) { console.error(e); setBatchEnriching(false); }
  };

  const sorted = useMemo(() => {
    if (!results?.results) return [];
    let t = results.results.map(r => ({ ...r, _isDup: checkDup(r) }));
    t = t.filter(r => !r._isDup);
    if (typeFilter) t = t.filter(r => (r.ai_analysis?.creator_type || '') === typeFilter || (r.categories || []).some(c => c.toLowerCase().includes(typeFilter.toLowerCase())));
    if (nicheFilter) t = t.filter(r => (r.ai_analysis?.content_niches || []).includes(nicheFilter) || (r.categories || []).some(c => c.toLowerCase().includes(nicheFilter.toLowerCase())));
    if (credentialFilter) t = t.filter(r => (r.ai_analysis?.credential_tier || r.raw_data?.credential_tier || '') === credentialFilter);
    return t.sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0));
  }, [results, dedupSet, typeFilter, nicheFilter, credentialFilter, savedThisSession]);

  const newC = sorted.length;
  const dupC = results?.results ? results.results.filter(r => checkDup(r)).length : 0;
  const hasDeepResults = results?.results?.some(r => r.ai_analysis?.source_layer === 'deep' || r.source_type === 'deep_search');

  return (
    <div>
      {/* Hero */}
      <div style={{ position: 'relative', overflow: 'hidden', marginBottom: 0 }}>
        <div style={{ background: 'linear-gradient(135deg, var(--cream) 0%, var(--peach) 40%, var(--terracotta-light) 100%)', padding: '48px 0 40px' }}>
          <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px' }}>
            <div style={{ maxWidth: 540 }}>
              <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 42, color: 'var(--text)', marginBottom: 8, lineHeight: 1.15 }}>Find Your Perfect Creator</h1>
              <p style={{ color: 'var(--text-secondary)', fontSize: 15, lineHeight: 1.6, marginBottom: 20 }}>Discover doctors, wellness creators, and UGC talent. AI finds, scores, and writes your outreach.</p>

              {/* Mode Switcher */}
              <div style={{ display: 'inline-flex', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, padding: 3, marginBottom: 16, boxShadow: 'var(--shadow-sm)' }}>
                {[
                  { id: 'general', label: 'General', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg> },
                  { id: 'doctor', label: 'Doctor', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg> },
                  { id: 'brand_intel', label: 'Brand Intel', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" /><circle cx="12" cy="10" r="3" /></svg> },
                ].map(m => (
                  <button key={m.id} onClick={() => { setSearchMode(m.id); setResults(null); setError(null); setQuery(''); }} style={{
                    display: 'flex', alignItems: 'center', gap: 5, padding: '7px 16px',
                    borderRadius: 9, fontSize: 12, fontWeight: 600, cursor: 'pointer', border: 'none',
                    background: searchMode === m.id ? 'var(--terracotta)' : 'transparent',
                    color: searchMode === m.id ? 'white' : 'var(--text-secondary)',
                    transition: 'all 0.2s ease',
                  }}>
                    {m.icon}{m.label}
                  </button>
                ))}
              </div>
              {searchMode === 'doctor' && <div style={{ fontSize: 11, color: 'var(--terracotta)', fontStyle: 'italic', marginTop: -10, marginBottom: 10 }}>Specialized search for medical professionals with content presence</div>}
              {searchMode === 'brand_intel' && <div style={{ fontSize: 11, color: 'var(--terracotta)', fontStyle: 'italic', marginTop: -10, marginBottom: 10 }}>Find creators who tag, mention, or partner with specific brands</div>}

              {/* Brand Intel — brand handle input */}
              {searchMode === 'brand_intel' && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', gap: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '4px 4px 4px 14px', alignItems: 'center', maxWidth: 500 }}>
                    <span style={{ color: 'var(--terracotta)', fontSize: 12, fontWeight: 700, flexShrink: 0, fontFamily: 'var(--font-mono)' }}>@</span>
                    <input value={brandHandles} onChange={e => setBrandHandles(e.target.value)}
                      placeholder="athleticgreens, seed, ritual"
                      style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', fontSize: 13, color: 'var(--text)', padding: '8px 0', fontFamily: 'var(--font-mono)' }} />
                    {brandHandles && <button onClick={() => setBrandHandles('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' }}>{I.x()}</button>}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>Comma-separated brand handles (TikTok or Instagram)</div>
                </div>
              )}

              {/* Search bar */}
              <div style={{ display: 'flex', gap: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '4px 4px 4px 16px', alignItems: 'center', boxShadow: 'var(--shadow-md)', maxWidth: 500 }}>
                <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>{I.search()}</span>
                <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && doSearch(query)}
                  placeholder={searchMode === 'doctor' ? "Search by specialty, credential, topic..." : searchMode === 'brand_intel' ? "e.g. find creators who promote AG1 greens..." : "Search creators, niches, platforms..."}
                  style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', fontSize: 14, color: 'var(--text)', padding: '10px 0', fontFamily: 'var(--font-body)' }} />
                {query && <button onClick={() => setQuery('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' }}>{I.x()}</button>}
                <select value={resultCount} onChange={e => setResultCount(Number(e.target.value))} style={{ padding: '6px 8px', background: 'var(--bg-muted)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-xs)', fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  <option value={10}>10</option><option value={20}>20</option><option value={50}>50</option><option value={100}>100</option>
                </select>
                <button onClick={() => doSearch(query)} disabled={searching || !query.trim()} className="btn-terracotta" style={{ borderRadius: 'var(--radius-sm)' }}>
                  {searching ? I.loader() : I.sparkles()} {searching ? 'Searching...' : 'Discover'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px' }}>
        {/* Presets */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', padding: '16px 0 8px' }}>
          {presets.map(p => <button key={p.l} className="btn-ghost" onClick={() => { setQuery(p.q); if (p.b) setBrandHandles(p.b); doSearch(p.q, p.b); }} style={{ borderRadius: 20, fontSize: 12 }}>{p.l}</button>)}
        </div>

        {error && <div style={{ padding: '12px 16px', background: 'var(--red-light)', borderRadius: 'var(--radius-xs)', color: 'var(--red)', fontSize: 13, marginBottom: 16, marginTop: 8 }}>{error}</div>}

        {/* Progress */}
        {(searching || deepSearching) && searchStatus && (() => {
          const steps = deepSearching
            ? [{ key: 'deep_searching', label: 'Digging deeper — LinkedIn, Reddit, agencies', est: 300 }]
            : [
              { key: 'starting', label: 'Starting search...', est: 5 },
              { key: 'parsing_intent', label: 'Understanding your query...', est: 15 },
              { key: 'searching', label: statusLabels.searching, est: 30 },
              { key: 'analyzing', label: 'Analyzing and scoring creators...', est: 250 },
            ];
          const currentIdx = steps.findIndex(s => s.key === searchStatus.status);
          const totalEst = steps.reduce((a, s) => a + s.est, 0);
          const completedEst = steps.slice(0, Math.max(0, currentIdx)).reduce((a, s) => a + s.est, 0);
          const currentStep = steps[currentIdx] || steps[steps.length - 1];
          const stepProgress = currentStep ? Math.min(0.9, elapsed > 0 ? (elapsed - completedEst) / currentStep.est : 0) : 0;
          const pct = Math.min(95, ((completedEst + (currentStep?.est || 0) * Math.max(0, stepProgress)) / totalEst) * 100);
          const mins = Math.floor(elapsed / 60);
          const secs = elapsed % 60;
          const timeStr = mins > 0 ? `${mins}:${secs.toString().padStart(2, '0')}` : `${secs}s`;
          const remainEst = Math.max(0, totalEst - elapsed);
          const remainLabel = remainEst <= 0 ? 'Almost done...' : remainEst > 60 ? `~${Math.ceil(remainEst / 60)} min left` : `~${remainEst}s left`;

          return (
            <div className="card-warm fade-up" style={{ padding: '20px 24px', marginTop: 12, marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {I.loader()}
                  <span style={{ fontSize: 14, fontWeight: 500 }}>{currentStep?.label || searchStatus.status}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{timeStr}</span>
                  <button onClick={handleCancel} style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', padding: '4px 12px', fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer', fontFamily: 'var(--font-body)' }}>Cancel</button>
                </div>
              </div>
              <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{ height: '100%', background: 'var(--terracotta)', borderRadius: 2, transition: 'width 1s ease', width: `${pct}%` }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {deepSearching ? 'Checking LinkedIn, Reddit, talent agencies...' : `Step ${Math.max(1, currentIdx + 1)} of ${steps.length}`}
                </span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  {elapsed > 3 ? remainLabel : ''}
                </span>
              </div>
            </div>
          );
        })()}

        {/* Results */}
        {results && (
          <div style={{ paddingTop: 8, paddingBottom: 32 }}>
            {/* Toolbar */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 14, fontWeight: 600 }}>{sorted.length} new creators</span>
                {dupC > 0 && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{dupC} skipped (already in DB)</span>}
                <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', fontSize: 12, background: 'var(--bg-card)', color: typeFilter ? 'var(--terracotta)' : 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'var(--font-body)' }}>
                  <option value="">All Types</option>
                  {CREATOR_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <select value={nicheFilter} onChange={e => setNicheFilter(e.target.value)} style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', fontSize: 12, background: 'var(--bg-card)', color: nicheFilter ? 'var(--terracotta)' : 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'var(--font-body)' }}>
                  <option value="">All Niches</option>
                  {CONTENT_NICHES.map(n => <option key={n} value={n}>{n}</option>)}
                </select>
                {doctorMode && (
                  <select value={credentialFilter} onChange={e => setCredentialFilter(e.target.value)} style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', fontSize: 12, background: 'var(--bg-card)', color: credentialFilter ? 'var(--terracotta)' : 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'var(--font-body)' }}>
                    <option value="">All Credentials</option>
                    <option value="physician">MD / DO</option>
                    <option value="allied">NP / PA / RD / PharmD</option>
                    <option value="other_medical">ND / Other Medical</option>
                  </select>
                )}
                {(typeFilter || nicheFilter || credentialFilter) && <button onClick={() => { setTypeFilter(''); setNicheFilter(''); setCredentialFilter(''); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--terracotta)', fontSize: 12, fontWeight: 500 }}>Clear</button>}
                {newC > 0 && !batchEnriching && <button className="btn-terracotta" onClick={handleSaveAll} style={{ fontSize: 12, padding: '6px 14px' }}>{I.zap()} Save All & Get Contacts ({newC})</button>}
                {batchEnriching && <span style={{ fontSize: 12, color: 'var(--terracotta)', display: 'flex', alignItems: 'center', gap: 6 }}>{I.loader()} Finding contacts...</span>}
                {doctorMode && results && !deepSearching && !hasDeepResults && (
                  <button onClick={handleGoDeeper} style={{
                    display: 'flex', alignItems: 'center', gap: 5, padding: '6px 14px', fontSize: 12, fontWeight: 600,
                    borderRadius: 'var(--radius-xs)', cursor: 'pointer',
                    border: '1px solid var(--terracotta)', background: 'transparent', color: 'var(--terracotta)',
                    transition: 'all 0.2s ease',
                  }} onMouseOver={e => { e.target.style.background = 'var(--terracotta)'; e.target.style.color = 'white'; }} onMouseOut={e => { e.target.style.background = 'transparent'; e.target.style.color = 'var(--terracotta)'; }}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /><path d="M11 8v6" /><path d="M8 11h6" /></svg>
                    Find Hidden Creators
                  </button>
                )}
                {deepSearching && <span style={{ fontSize: 12, color: 'var(--terracotta)', display: 'flex', alignItems: 'center', gap: 6 }}>{I.loader()} Digging deeper...</span>}
                {hasDeepResults && <Pill color="var(--terracotta)" bg="var(--terracotta-light)">Includes hidden finds</Pill>}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'var(--bg-muted)', borderRadius: 'var(--radius-xs)', padding: 3 }}>
                <button onClick={() => setViewMode('grid')} style={{ padding: 6, borderRadius: 4, border: 'none', cursor: 'pointer', background: viewMode === 'grid' ? 'var(--bg-card)' : 'transparent', color: viewMode === 'grid' ? 'var(--text)' : 'var(--text-muted)', display: 'flex', boxShadow: viewMode === 'grid' ? 'var(--shadow-sm)' : 'none' }}>{I.grid()}</button>
                <button onClick={() => setViewMode('list')} style={{ padding: 6, borderRadius: 4, border: 'none', cursor: 'pointer', background: viewMode === 'list' ? 'var(--bg-card)' : 'transparent', color: viewMode === 'list' ? 'var(--text)' : 'var(--text-muted)', display: 'flex', boxShadow: viewMode === 'list' ? 'var(--shadow-sm)' : 'none' }}>{I.list()}</button>
              </div>
            </div>

            {viewMode === 'grid' ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 16 }}>
                {sorted.map((r, i) => <CreatorCard key={r.id || i} creator={{ ...r, categories: r.categories || [] }} isDiscoveryResult={!r._saved} isDuplicate={r._isDup} onSaveAndEnrich={handleSAE} onSelect={setSelected} delay={i} />)}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {sorted.map((r, i) => <ListItem key={r.id || i} creator={r} isDuplicate={r._isDup} onSelect={setSelected} isDiscoveryResult={!r._saved} onSaveAndEnrich={handleSAE} />)}
              </div>
            )}
          </div>
        )}

        {!results && !searching && !deepSearching && (
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <div style={{ marginBottom: 16, opacity: 0.25 }}>{I.compass(48)}</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 28, color: 'var(--text)', marginBottom: 8 }}>
              {searchMode === 'doctor' ? 'Find Doctor Creators' : searchMode === 'brand_intel' ? 'Brand Intelligence' : 'Discover creators'}
            </div>
            <div style={{ fontSize: 14, maxWidth: 400, margin: '0 auto', lineHeight: 1.6, color: 'var(--text-secondary)', marginBottom: 24 }}>
              {searchMode === 'doctor' ? 'Search for credentialed medical professionals who create content. AI finds MDs, DOs, NPs, and RDs with active social presence.'
                : searchMode === 'brand_intel' ? 'Enter competitor brand handles above, then search. AI will find creators who tag, mention, or partner with those brands — proven UGC talent ready for outreach.'
                  : 'Search naturally — "find doctors who talk about heart health on TikTok" — and AI will find, score, and generate outreach strategies.'}
            </div>
            {recentSearches.length > 0 && (
              <div style={{ maxWidth: 500, margin: '0 auto', textAlign: 'left' }}>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', marginBottom: 8 }}>Recent Searches</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {recentSearches.map(s => (
                    <button key={s.id} onClick={() => loadPastSearch(s)} style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '8px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-xs)', cursor: 'pointer', textAlign: 'left', fontFamily: 'var(--font-body)',
                      fontSize: 13, color: 'var(--text)', transition: 'border-color 0.15s',
                    }} onMouseOver={e => e.currentTarget.style.borderColor = 'var(--terracotta)'} onMouseOut={e => e.currentTarget.style.borderColor = 'var(--border)'}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{s.query}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 12, flexShrink: 0 }}>{s.results_count} results</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
