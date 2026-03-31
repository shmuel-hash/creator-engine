import React, { useState, useEffect, useRef } from 'react';
import { api } from '../utils/api';
import { I } from './Icons';

export default function EnrichmentProgress({ creatorId, onComplete }) {
  const [status, setStatus] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    if (!creatorId) return;
    const poll = async () => {
      try {
        const s = await api(`/creators/${creatorId}/enrich/status`);
        setStatus(s);
        if (s.status === 'complete' || s.status === 'failed') {
          clearInterval(ref.current);
          if (s.status === 'complete' && onComplete) onComplete(creatorId);
        }
      } catch (e) { /* ignore */ }
    };
    poll();
    ref.current = setInterval(poll, 2000);
    return () => clearInterval(ref.current);
  }, [creatorId]);

  if (!status || status.status === 'not_started') return null;

  const pct = status.status === 'complete' ? 100 : ((status.step || 0) / (status.total_steps || 3)) * 100;
  const running = !['complete', 'failed', 'not_started'].includes(status.status);

  return (
    <div style={{ padding: '10px 14px', background: 'var(--terracotta-light)', borderRadius: 'var(--radius-xs)', marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}>
          {running && I.loader()}
          {status.status === 'complete' && <span style={{ color: 'var(--sage)' }}>{I.check()}</span>}
          {status.status === 'failed' && <span style={{ color: 'var(--red)' }}>{I.x()}</span>}
          {status.step_label || status.status}
        </span>
        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{status.step}/{status.total_steps}</span>
      </div>
      <div style={{ height: 3, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', background: status.status === 'failed' ? 'var(--red)' : 'var(--terracotta)', borderRadius: 2, width: `${pct}%`, transition: 'width 0.5s ease' }} />
      </div>
      {status.error && <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 4 }}>{status.error}</div>}
    </div>
  );
}
