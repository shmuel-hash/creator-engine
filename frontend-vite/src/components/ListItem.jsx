import React from 'react';
import { PLAT, fmtNum } from '../utils/api';
import { I } from './Icons';
import Pill from './Pill';
import Avatar from './Avatar';
import PlatformPill from './PlatformPill';
import ScoreRing from './ScoreRing';

export default function ListItem({ creator, isDuplicate, onSelect, isDiscoveryResult, onSaveAndEnrich }) {
  const c = creator;
  const ai = c.ai_analysis || {};
  const creds = ai.credentials || [];

  const platforms = [];
  if (c.tiktok_handle) platforms.push({ n: 'tiktok', h: c.tiktok_handle, f: c.tiktok_followers });
  if (c.instagram_handle) platforms.push({ n: 'instagram', h: c.instagram_handle, f: c.instagram_followers });
  if (c.youtube_handle) platforms.push({ n: 'youtube', h: c.youtube_handle, f: c.youtube_subscribers });
  if (platforms.length === 0 && c.handle) platforms.push({ n: c.platform || 'unknown', h: c.handle, f: c.followers });

  const listAi = c.ai_analysis || {};

  return (
    <div className="card-warm" style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 16px', cursor: 'pointer', opacity: isDuplicate ? 0.5 : 1 }} onClick={() => onSelect && onSelect(c)}>
      <Avatar name={c.name} size={40} src={listAi.avatar_url || listAi.apify_profile?.avatar_url} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>{c.name}</span>
          {isDuplicate && <Pill color="var(--amber)" bg="var(--amber-light)" style={{ fontSize: 9 }}>In DB</Pill>}
          {creds.slice(0, 1).map((cr, i) => <Pill key={i} color="var(--blue)" bg="var(--blue-light)" style={{ fontSize: 9 }}>{cr}</Pill>)}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text-muted)' }}>
          {platforms.map((p, i) => <PlatformPill key={i} platform={p.n} handle={p.h} />)}
          {c.categories?.slice(0, 2).map(cat => <span key={cat} style={{ fontFamily: 'var(--font-mono)' }}>{cat}</span>)}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        {platforms[0]?.f && <div style={{ textAlign: 'center' }}><div style={{ fontSize: 13, fontWeight: 700 }}>{fmtNum(platforms[0].f)}</div><div style={{ fontSize: 9, color: 'var(--text-muted)' }}>followers</div></div>}
        {c.relevance_score != null && <ScoreRing score={c.relevance_score} size={36} />}
      </div>
    </div>
  );
}
