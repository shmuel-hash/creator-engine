import React from 'react';
import { PLAT } from '../utils/api';

export default function PlatformPill({ platform, handle, url }) {
  const m = PLAT[platform] || { a: (platform || '').slice(0, 2).toUpperCase(), c: 'var(--text-secondary)', l: platform };
  const inner = (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
      <span style={{ color: m.c, fontWeight: 700 }}>{m.a}</span>
      {handle ? `@${handle.replace('@', '')}` : m.l}
    </span>
  );
  if (url) return <a href={url} target="_blank" rel="noopener" style={{ textDecoration: 'none' }}>{inner}</a>;
  return inner;
}
