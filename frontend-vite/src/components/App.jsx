import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import { I } from './Icons';
import { DetailCtx } from './DetailContext';
import DetailPanel from './DetailPanel';
import DiscoverTab from './DiscoverTab';
import DatabaseTab from './DatabaseTab';
import ImportTab from './ImportTab';

export default function App() {
  const [tab, setTab] = useState('discover');
  const [stats, setStats] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => { api('/stats').then(setStats).catch(() => {}); }, [tab]);

  const tabs = [
    { id: 'discover', label: 'Discover', icon: I.search },
    { id: 'database', label: 'Database', icon: I.users },
    { id: 'import', label: 'Import', icon: I.upload },
  ];

  return (
    <DetailCtx.Provider value={{ selected, setSelected }}>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        {/* Top nav */}
        <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px', height: 64, borderBottom: '1px solid var(--border)', background: 'rgba(250,248,245,0.85)', backdropFilter: 'blur(12px)', position: 'sticky', top: 0, zIndex: 50 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }} onClick={() => setTab('discover')}>
            <div style={{ width: 34, height: 34, borderRadius: 10, background: 'var(--terracotta)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', boxShadow: '0 2px 8px rgba(196,93,62,0.3)' }}>{I.sparkles(18)}</div>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: 22, color: 'var(--text)' }}>Creator Engine</span>
          </div>
          <nav style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {tabs.map(t => {
              const active = tab === t.id;
              return (
                <button key={t.id} onClick={() => setTab(t.id)} style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', border: 'none', background: 'transparent', cursor: 'pointer',
                  fontSize: 13, fontWeight: active ? 600 : 400, color: active ? 'var(--text)' : 'var(--text-muted)',
                  borderRadius: 10, position: 'relative', transition: 'all 0.15s', fontFamily: 'var(--font-body)',
                }}>
                  <span style={{ color: active ? 'var(--terracotta)' : 'var(--text-muted)', transition: 'color 0.15s' }}>{t.icon()}</span>
                  {t.label}
                  {active && <div style={{ position: 'absolute', bottom: 0, left: 8, right: 8, height: 2, background: 'var(--terracotta)', borderRadius: 1 }} />}
                </button>
              );
            })}
          </nav>
        </header>

        <main style={{ flex: 1 }}>
          <div style={{ display: tab === 'discover' ? 'block' : 'none' }}><DiscoverTab /></div>
          <div style={{ display: tab === 'database' ? 'block' : 'none' }}><DatabaseTab /></div>
          {tab === 'import' && <ImportTab />}
        </main>

        <footer style={{ padding: '12px 24px', borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
          Creator Engine v2.0 · Luma Nutrition · <a href="https://creator-engine-production.up.railway.app/docs" target="_blank" rel="noopener" style={{ color: 'var(--terracotta)', textDecoration: 'none' }}>API Docs</a>
        </footer>
      </div>

      <DetailPanel />
    </DetailCtx.Provider>
  );
}
