import React, { useState } from 'react';
import { api, PLAT, fmtNum } from '../utils/api';
import { I } from './Icons';
import Pill from './Pill';
import Avatar from './Avatar';
import ScoreRing from './ScoreRing';

export default function CreatorCard({ creator, isDiscoveryResult, isDuplicate, pipelineStatus, onAddToPipeline, onSelect, delay = 0 }) {
  const [local, setLocal] = useState(creator);
  const [pushing, setPushing] = useState(false);
  const [pushed, setPushed] = useState(!!pipelineStatus);
  const [pushResult, setPushResult] = useState(pipelineStatus ? { task_url: pipelineStatus.task_url } : null);
  const [err, setErr] = useState(null);
  const c = local;
  const ai = c.ai_analysis || {};
  const creds = ai.credentials || [];

  // Build platform list
  const platforms = [];
  if (c.tiktok_handle || c.tiktok_url) platforms.push({ n: 'tiktok', h: c.tiktok_handle, f: c.tiktok_followers });
  if (c.instagram_handle || c.instagram_url) platforms.push({ n: 'instagram', h: c.instagram_handle, f: c.instagram_followers });
  if (c.youtube_handle || c.youtube_url) platforms.push({ n: 'youtube', h: c.youtube_handle, f: c.youtube_subscribers });
  if (platforms.length === 0 && (c.handle || c.profile_url)) {
    const handle = c.handle;
    const pUrl = c.profile_url || '';
    let detectedPlatform = c.platform || 'unknown';
    if (pUrl.includes('tiktok.com')) detectedPlatform = 'tiktok';
    else if (pUrl.includes('instagram.com')) detectedPlatform = 'instagram';
    else if (pUrl.includes('youtube.com')) detectedPlatform = 'youtube';
    const otherProfiles = ai.other_profiles || {};
    if (otherProfiles.tiktok) platforms.push({ n: 'tiktok', h: otherProfiles.tiktok, f: null });
    if (otherProfiles.instagram) platforms.push({ n: 'instagram', h: otherProfiles.instagram, f: null });
    if (otherProfiles.youtube) platforms.push({ n: 'youtube', h: otherProfiles.youtube, f: null });
    if (platforms.length === 0) platforms.push({ n: detectedPlatform, h: handle, f: c.followers, u: pUrl.includes('tiktok.com') || pUrl.includes('instagram.com') || pUrl.includes('youtube.com') ? pUrl : null });
  }

  const avatarSrc = ai.avatar_url || ai.apify_profile?.avatar_url || null;

  const handleAddToPipeline = async (ev) => {
    ev.stopPropagation();
    setErr(null);
    setPushing(true);
    try {
      const resp = await api(`/discover/results/${c.id}/add-to-pipeline`, { method: 'POST' });
      setPushed(true);
      setPushResult(resp.clickup);
      setLocal(prev => ({ ...prev, _saved: true }));
      if (onAddToPipeline) onAddToPipeline(c, resp);
    } catch (error) {
      setErr(error.message);
      console.error('[AddToPipeline]', c.name, error.message);
    }
    setPushing(false);
  };

  // Determine pipeline status label
  const getPipelineLabel = () => {
    if (pipelineStatus?.status) {
      const s = pipelineStatus.status.toLowerCase();
      if (s === 'open' || s === 'to do') return 'In Pipeline';
      if (s === 'in progress') return 'Outreach Sent';
      if (s === 'review') return 'In Review';
      if (s === 'complete' || s === 'closed') return 'Contracted';
      return pipelineStatus.status;
    }
    return 'In Pipeline';
  };

  return (
    <div className="card-warm" style={{ opacity: isDuplicate ? 0.5 : 1, animationDelay: `${delay * 40}ms` }} onClick={() => onSelect && onSelect(c)}>
      {/* Cover gradient */}
      <div style={{ height: 56, background: isDuplicate ? 'var(--bg-muted)' : 'linear-gradient(135deg, var(--terracotta-light) 0%, var(--peach) 60%, var(--sage-light) 100%)', position: 'relative' }}>
        {c.relevance_score != null && <div style={{ position: 'absolute', top: 8, right: 8 }}><ScoreRing score={c.relevance_score} size={36} /></div>}
        {isDuplicate && <div style={{ position: 'absolute', top: 8, left: 8 }}><Pill color="var(--amber)" bg="var(--amber-light)">{I.database()} In DB</Pill></div>}
        {(pushed || pipelineStatus) && !isDuplicate && <div style={{ position: 'absolute', top: 8, left: 8 }}><Pill color="white" bg="var(--sage)">{I.check()} {getPipelineLabel()}</Pill></div>}
      </div>

      <div style={{ padding: '0 16px 16px', cursor: 'pointer' }}>
        {/* Avatar overlapping cover */}
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, marginTop: -22, marginBottom: 10 }}>
          <div style={{ border: '3px solid var(--bg-card)', borderRadius: '50%', flexShrink: 0 }}>
            <Avatar name={c.name} size={44} src={avatarSrc} />
          </div>
          <div style={{ flex: 1, minWidth: 0, paddingBottom: 2, paddingTop: 24 }}>
            <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={c.name}>{c.name}</div>
            {platforms[0]?.h && (() => {
              const handle = platforms[0].h.replace('@', '');
              const pUrl = platforms[0].u || (platforms[0].n === 'tiktok' ? `https://www.tiktok.com/@${handle}` : platforms[0].n === 'instagram' ? `https://www.instagram.com/${handle}/` : platforms[0].n === 'youtube' ? `https://www.youtube.com/@${handle}` : c.profile_url || null);
              return pUrl
                ? <a href={pUrl} target="_blank" rel="noopener" onClick={e => e.stopPropagation()} style={{ fontSize: 11, color: 'var(--terracotta)', fontFamily: 'var(--font-mono)', textDecoration: 'none' }}>@{handle} {I.ext()}</a>
                : <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>@{handle}</div>;
            })()}
          </div>
        </div>

        {/* Type + Credentials + Niches */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
          {ai.credential_tier === 'physician' && <Pill color="white" bg="#2563eb" style={{ fontSize: 10, fontWeight: 700 }}>MD/DO</Pill>}
          {ai.credential_tier === 'allied' && <Pill color="white" bg="#7c3aed" style={{ fontSize: 10, fontWeight: 700 }}>Allied Health</Pill>}
          {ai.credential_tier === 'other_medical' && <Pill color="white" bg="#059669" style={{ fontSize: 10, fontWeight: 700 }}>Alt. Medical</Pill>}
          {ai.creator_type && !ai.credential_tier && <Pill color="var(--terracotta)" bg="var(--terracotta-light)" style={{ fontSize: 10, fontWeight: 700 }}>{ai.creator_type}</Pill>}
          {ai.creator_type && ai.credential_tier && <Pill color="var(--terracotta)" bg="var(--terracotta-light)" style={{ fontSize: 10 }}>{ai.creator_type}</Pill>}
          {ai.medical_specialty && <Pill color="var(--blue)" bg="var(--blue-light)" style={{ fontSize: 10 }}>{ai.medical_specialty}</Pill>}
          {!ai.medical_specialty && creds.slice(0, 2).map((cr, i) => <Pill key={i} color="var(--blue)" bg="var(--blue-light)" style={{ fontSize: 10 }}>{cr}</Pill>)}
          {(ai.content_niches || []).slice(0, 2).map(n => <Pill key={n} color="var(--sage)" bg="var(--sage-light)" style={{ fontSize: 10 }}>{n}</Pill>)}
          {!ai.creator_type && !ai.credential_tier && c.categories?.slice(0, 2).map(cat => <Pill key={cat} style={{ fontSize: 10 }}>{cat}</Pill>)}
          {ai.country && <Pill style={{ fontSize: 10 }}>{ai.country}</Pill>}
          {ai.language && ai.language !== 'English' && ai.language !== 'Spanish' && <Pill color="var(--red)" bg="var(--red-light)" style={{ fontSize: 10 }}>{ai.language}</Pill>}
          {ai.source_layer === 'deep' && <Pill color="var(--amber)" bg="var(--amber-light)" style={{ fontSize: 10 }}>Hidden find</Pill>}
          {ai.source_layer === 'brand_intel' && <Pill color="var(--purple)" bg="var(--purple-light)" style={{ fontSize: 10 }}>Brand tagged</Pill>}
          {ai.brand_associations?.length > 0 && ai.brand_associations.slice(0, 2).map((b, i) => <Pill key={i} color="var(--purple)" bg="var(--purple-light)" style={{ fontSize: 10 }}>{b}</Pill>)}
          {ai.estimated_rate && <Pill style={{ fontSize: 10 }}>{ai.estimated_rate}</Pill>}
          {!platforms.length && !c.handle && <Pill color="var(--red)" bg="var(--red-light)" style={{ fontSize: 10 }}>{I.alert()} No social</Pill>}
        </div>

        {/* Stats row */}
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(platforms.length + 1, 3)},1fr)`, gap: 6, paddingTop: 10, borderTop: '1px solid var(--border-light)' }}>
          {platforms.slice(0, 2).map((p, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ color: PLAT[p.n]?.c, fontWeight: 700, fontSize: 10 }}>{PLAT[p.n]?.a || '?'}</span>
                <span style={{ fontSize: 12, fontWeight: 700 }}>{fmtNum(p.f)}</span>
              </div>
              <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>followers</span>
            </div>
          ))}
          {c.engagement_rate && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
              <span style={{ fontSize: 12, fontWeight: 700 }}>{c.engagement_rate}%</span>
              <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>engage</span>
            </div>
          )}
        </div>

        {/* Add to Pipeline button */}
        {isDiscoveryResult && !pushed && !pipelineStatus && !isDuplicate && (
          <div style={{ marginTop: 10 }}>
            <button className="btn-terracotta" onClick={handleAddToPipeline} disabled={pushing} style={{ width: '100%', justifyContent: 'center', fontSize: 12, padding: '7px 12px' }}>
              {pushing ? I.loader() : I.zap()} {pushing ? 'Adding...' : 'Add to Pipeline'}
            </button>
            {err && <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 4, padding: '4px 8px', background: 'var(--red-light)', borderRadius: 4 }}>{err}</div>}
          </div>
        )}

        {/* Pipeline success state */}
        {(pushed || pipelineStatus) && !isDuplicate && (
          <div style={{ marginTop: 10, padding: '8px 12px', background: 'var(--sage-light)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--sage)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--sage)', display: 'flex', alignItems: 'center', gap: 4 }}>
              {I.check()} {getPipelineLabel()}
            </div>
            {(pushResult?.task_url || pipelineStatus?.task_url) && (
              <a
                href={pushResult?.task_url || pipelineStatus?.task_url}
                target="_blank"
                rel="noopener"
                onClick={e => e.stopPropagation()}
                style={{ fontSize: 10, color: 'var(--terracotta)', marginTop: 4, display: 'inline-block', textDecoration: 'none' }}
              >
                Open in ClickUp →
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
