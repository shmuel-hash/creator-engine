import React from 'react';

export default function Pill({ children, color = 'var(--text-muted)', bg = 'var(--bg-muted)', style = {} }) {
  return <span className="pill" style={{ color, background: bg, ...style }}>{children}</span>;
}
