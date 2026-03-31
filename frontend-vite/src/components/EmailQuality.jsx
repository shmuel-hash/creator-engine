import React from 'react';
import { I } from './Icons';
import Pill from './Pill';

export default function EmailQuality({ email }) {
  if (!email) return null;

  const lower = email.toLowerCase();
  if (['available', 'upon request', 'contact via', 'dm for', 'n/a', 'none', 'tbd', 'pending'].some(f => lower.includes(f))) {
    return <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>{I.mail()} No direct email found</span>;
  }
  if (!email.includes('@')) return null;

  const d = email.split('@')[1]?.toLowerCase() || '';
  const gen = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com', 'icloud.com'].includes(d);
  const agent = d.includes('manager') || d.includes('talent') || d.includes('agency') || email.includes('mgmt') || email.includes('booking');

  let label, pc, pb;
  if (agent) { label = 'Agent'; pc = 'var(--purple)'; pb = 'var(--purple-light)'; }
  else if (!gen) { label = 'Personal'; pc = 'var(--sage)'; pb = 'var(--sage-light)'; }
  else { label = 'Generic'; pc = 'var(--text-muted)'; pb = 'var(--bg-muted)'; }

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
      {I.mail()} {email} <Pill color={pc} bg={pb} style={{ fontSize: 10 }}>{label}</Pill>
    </span>
  );
}
