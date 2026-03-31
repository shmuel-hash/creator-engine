import React from 'react';

export default function ScoreRing({ score, size = 42 }) {
  const pct = Math.min(100, Math.max(0, score || 0));
  const color = pct >= 70 ? 'var(--sage)' : pct >= 40 ? 'var(--amber)' : 'var(--text-muted)';
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const off = circ * (1 - pct / 100);

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth="3" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="3" strokeDasharray={circ} strokeDashoffset={off} strokeLinecap="round" style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
      </svg>
      <span style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: size * 0.3, fontWeight: 700, fontFamily: 'var(--font-mono)', color }}>
        {Math.round(score)}
      </span>
    </div>
  );
}
