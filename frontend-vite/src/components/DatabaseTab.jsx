import React, { useState, useEffect, useCallback, useContext } from 'react';
import { api, fmtNum, CREATOR_TYPES, CONTENT_NICHES } from '../utils/api';
import { I } from './Icons';
import CreatorCard from './CreatorCard';
import ListItem from './ListItem';
import { DetailCtx } from './DetailContext';

export default function DatabaseTab() {
  const { setSelected } = useContext(DetailCtx);
  const [creators, setCreators] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({});
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState('grid');
  const [sortBy, setSortBy] = useState('relevance_score');
  const [sortDir, setSortDir] = useState('desc');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api('/creators', { params: { search: search || undefined, page, per_page: 24, sort_by: sortBy, sort_dir: sortDir, ...filters } });
      setCreators(d.creators || []);
      setTotal(d.total || 0);
    } catch (e) { /* ignore */ }
    setLoading(false);
  }, [search, page, filters, sortBy, sortDir]);

  useEffect(() => { load(); }, [load]);

  const handleEnrich = async (id) => { await api(`/creators/${id}/enrich`, { method: 'POST' }); return id; };

  return (
    <div>
      {/* Hero */}
      <div style={{ background: 'linear-gradient(135deg, var(--sage-light) 0%, var(--cream) 50%, var(--terracotta-light) 100%)', padding: '40px 0 32px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>{I.database(16)}<span style={{ fontSize: 13, fontWeight: 600, color: 'var(--sage)' }}>Creator Database</span></div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 36, color: 'var(--text)', marginBottom: 4 }}>Your Creators</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>{total} creators in your database</p>
            <button className="btn-ghost" onClick={async () => { if (!confirm('Delete all discovered/test creators?')) return; await api('/creators/bulk/discovered', { method: 'DELETE' }); load(); }} style={{ fontSize: 11, padding: '4px 10px', color: 'var(--red)' }}>Clear test data</button>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div style={{ position: 'sticky', top: 64, zIndex: 30, background: 'rgba(250,248,245,0.85)', backdropFilter: 'blur(12px)', borderBottom: '1px solid var(--border)' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 48, gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
            <div style={{ position: 'relative', maxWidth: 260, flex: 1 }}>
              <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}>{I.search(14)}</span>
              <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder="Search creators..."
                style={{ width: '100%', padding: '7px 10px 7px 32px', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', fontSize: 13, background: 'var(--bg-card)', color: 'var(--text)', outline: 'none', fontFamily: 'var(--font-body)' }} />
            </div>
            <select value={sortBy + '|' + sortDir} onChange={e => { const [s, d] = e.target.value.split('|'); setSortBy(s); setSortDir(d); setPage(1); }} style={{ padding: '7px 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', fontSize: 12, background: 'var(--bg-card)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
              <option value="relevance_score|desc">Highest Score</option>
              <option value="relevance_score|asc">Lowest Score</option>
              <option value="total_followers|desc">Most Followers</option>
              <option value="created_at|desc">Newest First</option>
              <option value="created_at|asc">Oldest First</option>
              <option value="name|asc">Name A-Z</option>
            </select>
            <select onChange={e => { setFilters(f => ({ ...f, categories: e.target.value || undefined })); setPage(1); }} style={{ padding: '7px 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', fontSize: 12, background: 'var(--bg-card)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
              <option value="">All Types</option>
              {CREATOR_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <select onChange={e => { setFilters(f => ({ ...f, niche: e.target.value || undefined })); setPage(1); }} style={{ padding: '7px 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', fontSize: 12, background: 'var(--bg-card)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
              <option value="">All Niches</option>
              {CONTENT_NICHES.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'var(--bg-muted)', borderRadius: 'var(--radius-xs)', padding: 3 }}>
            <button onClick={() => setViewMode('grid')} style={{ padding: 6, borderRadius: 4, border: 'none', cursor: 'pointer', background: viewMode === 'grid' ? 'var(--bg-card)' : 'transparent', color: viewMode === 'grid' ? 'var(--text)' : 'var(--text-muted)', display: 'flex', boxShadow: viewMode === 'grid' ? 'var(--shadow-sm)' : 'none' }}>{I.grid()}</button>
            <button onClick={() => setViewMode('list')} style={{ padding: 6, borderRadius: 4, border: 'none', cursor: 'pointer', background: viewMode === 'list' ? 'var(--bg-card)' : 'transparent', color: viewMode === 'list' ? 'var(--text)' : 'var(--text-muted)', display: 'flex', boxShadow: viewMode === 'list' ? 'var(--shadow-sm)' : 'none' }}>{I.list()}</button>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 24px 40px' }}>
        {loading ? <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>{I.loader(20)} Loading...</div>
          : creators.length === 0 ? <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)', fontSize: 14 }}>No creators found. Try adjusting filters or import data.</div>
            : viewMode === 'grid' ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 16 }}>
                {creators.map((c, i) => <CreatorCard key={c.id} creator={c} onEnrich={handleEnrich} onSelect={setSelected} delay={i} />)}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {creators.map(c => <ListItem key={c.id} creator={c} onSelect={setSelected} />)}
              </div>
            )}
        {total > 24 && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 24 }}>
            <button disabled={page <= 1} className="btn-ghost" onClick={() => setPage(p => p - 1)} style={{ opacity: page <= 1 ? 0.4 : 1 }}>Previous</button>
            <span style={{ padding: '6px 12px', fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Page {page} of {Math.ceil(total / 24)}</span>
            <button disabled={page >= Math.ceil(total / 24)} className="btn-ghost" onClick={() => setPage(p => p + 1)} style={{ opacity: page >= Math.ceil(total / 24) ? 0.4 : 1 }}>Next</button>
          </div>
        )}
      </div>
    </div>
  );
}
