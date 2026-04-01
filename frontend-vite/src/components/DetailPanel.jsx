import React, { useState, useContext } from 'react';
import { api, PLAT, fmtNum } from '../utils/api';
import { I } from './Icons';
import Pill from './Pill';
import Avatar from './Avatar';
import ScoreRing from './ScoreRing';
import EmailQuality from './EmailQuality';
import { DetailCtx } from './DetailContext';

export default function DetailPanel() {
  const { selected, setSelected } = useContext(DetailCtx);
  const [pushing, setPushing] = useState(false);
  const [pushed, setPushed] = useState(false);
  const [pushResult, setPushResult] = useState(null);
  const [pushErr, setPushErr] = useState(null);
  const [copied, setCopied] = useState(null);

  if (!selected) return null;

  const c = selected;
  const ai = c.ai_analysis || {};
  const strategy = ai.outreach_strategy;
  const creds = ai.credentials || [];
  const partnerships = ai.past_partnerships || [];

  // Detect if this is a discovery result (has search-result-like shape, not a saved creator)
  const isDiscoveryResult = !c._saved && !c.pipeline_stage && !c.created_at;

  const platforms = [];
  if (c.tiktok_handle || c.tiktok_url) platforms.push({ n: 'tiktok', h: c.tiktok_handle, u: c.tiktok_url, f: c.tiktok_followers });
  if (c.instagram_handle || c.instagram_url) platforms.push({ n: 'instagram', h: c.instagram_handle, u: c.instagram_url, f: c.instagram_followers });
  if (c.youtube_handle || c.youtube_url) platforms.push({ n: 'youtube', h: c.youtube_handle, u: c.youtube_url, f: c.youtube_subscribers });
  if (c.twitter_handle || c.twitter_url) platforms.push({ n: 'twitter', h: c.twitter_handle, u: c.twitter_url, f: c.twitter_followers });
  if (platforms.length === 0 && (c.handle || c.profile_url)) platforms.push({ n: c.platform || 'unknown', h: c.handle, u: c.profile_url, f: c.followers });

  const hasFollowers = platforms.some(p => p.f) || c.engagement_rate;

  const copy = (text, k) => { navigator.clipboard.writeText(text); setCopied(k); setTimeout(() => setCopied(null), 2000); };

  const handleAddToPipeline = async () => {
    setPushErr(null); setPushing(true);
    try {
      const resp = await api(`/discover/results/${c.id}/add-to-pipeline`, { method: 'POST' });
      setPushed(true);
      setPushResult(resp.clickup);
    } catch (error) {
      setPushErr(error.message);
    }
    setPushing(false);
  };

  return (
    <>
      <div className="backdrop" onClick={() => setSelected(null)} />
      <div className="detail-panel">
        {/* Cover area */}
        <div style={{ position: 'relative', height: 140, background: 'linear-gradient(135deg, var(--terracotta-light) 0%, var(--peach) 50%, var(--sage-light) 100%)', flexShrink: 0 }}>
          <button onClick={() => setSelected(null)} style={{ position: 'absolute', top: 12, right: 12, width: 32, height: 32, borderRadius: '50%', background: 'rgba(255,255,255,0.8)', backdropFilter: 'blur(8px)', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text)' }}>{I.x()}</button>
          <div style={{ position: 'absolute', bottom: -28, left: 24 }}>
            <div style={{ border: '4px solid var(--bg-card)', borderRadius: '50%' }}>
              <Avatar name={c.name} size={64} src={ai.avatar_url || ai.apify_profile?.avatar_url} />
            </div>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflow: 'auto', padding: '40px 24px 24px' }}>
          {/* Name + actions */}
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
            <div>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 26, color: 'var(--text)', margin: 0 }}>{c.name}</h2>
              {platforms[0]?.h && <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>@{platforms[0].h.replace('@', '')}</div>}
            </div>
            {c.relevance_score != null && <ScoreRing score={c.relevance_score} size={48} />}
          </div>

          {/* Tags row */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
            {ai.credential_tier === 'physician' && <Pill color="white" bg="#2563eb" style={{ fontWeight: 700 }}>{I.award()} MD/DO</Pill>}
            {ai.credential_tier === 'allied' && <Pill color="white" bg="#7c3aed" style={{ fontWeight: 700 }}>Allied Health</Pill>}
            {ai.credential_tier === 'other_medical' && <Pill color="white" bg="#059669" style={{ fontWeight: 700 }}>Alt. Medical</Pill>}
            {ai.creator_type && <Pill color="var(--terracotta)" bg="var(--terracotta-light)" style={{ fontWeight: 700 }}>{ai.creator_type}</Pill>}
            {ai.medical_specialty && <Pill color="var(--blue)" bg="var(--blue-light)">{ai.medical_specialty}</Pill>}
            {ai.country && <Pill color="var(--text-secondary)" bg="var(--bg-muted)">{I.mapPin()} {ai.country}</Pill>}
            {ai.language && ai.language !== 'English' && <Pill color="var(--amber)" bg="var(--amber-light)">{ai.language}</Pill>}
            {c.pipeline_stage && <Pill color="var(--text-secondary)" bg="var(--bg-muted)">{c.pipeline_stage}</Pill>}
            {c.quality_tier && <Pill color="var(--sage)" bg="var(--sage-light)">{c.quality_tier}</Pill>}
            {!ai.credential_tier && creds.map((cr, i) => <Pill key={i} color="var(--blue)" bg="var(--blue-light)">{I.award()} {cr}</Pill>)}
            {ai.estimated_rate && <Pill color="var(--text-secondary)" bg="var(--bg-muted)">{ai.estimated_rate}</Pill>}
            {ai.practice_affiliation && <Pill color="var(--text-secondary)" bg="var(--bg-muted)">{ai.practice_affiliation}</Pill>}
            {ai.source_layer === 'deep' && <Pill color="var(--amber)" bg="var(--amber-light)">Deep find</Pill>}
          </div>

          {/* Content niches */}
          {((ai.content_niches || []).length > 0 || (c.categories || []).length > 0) && (
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 12 }}>
              {(ai.content_niches || []).map(n => <Pill key={n} color="var(--sage)" bg="var(--sage-light)">{n}</Pill>)}
              {!ai.content_niches?.length && c.categories?.slice(0, 4).map(cat => <Pill key={cat}>{cat}</Pill>)}
            </div>
          )}

          {/* Email */}
          {c.email && <div style={{ marginBottom: 12 }}><EmailQuality email={c.email} /></div>}

          {/* Bio */}
          {c.bio && <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 16 }}>{c.bio}</p>}

          {/* Stats grid - only show if there are actual values */}
          {hasFollowers && (
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(platforms.filter(p=>p.f).length + (c.engagement_rate ? 1 : 0), 3)},1fr)`, gap: 8, marginBottom: 20 }}>
              {platforms.filter(p => p.f).map((p, i) => (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '12px 8px', background: 'var(--bg-muted)', borderRadius: 'var(--radius-sm)' }}>
                  <span style={{ color: PLAT[p.n]?.c || 'var(--text-secondary)', fontWeight: 700, fontSize: 12 }}>{PLAT[p.n]?.a || p.n.slice(0, 2).toUpperCase()}</span>
                  <span style={{ fontSize: 14, fontWeight: 700 }}>{fmtNum(p.f)}</span>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>followers</span>
                </div>
              ))}
              {c.engagement_rate && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '12px 8px', background: 'var(--bg-muted)', borderRadius: 'var(--radius-sm)' }}>
                  <span style={{ color: 'var(--sage)' }}>{I.trendUp()}</span>
                  <span style={{ fontSize: 14, fontWeight: 700 }}>{c.engagement_rate}%</span>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>engagement</span>
                </div>
              )}
            </div>
          )}

          {/* Platforms links */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
            {platforms.filter(p => p.u).map((p, i) => (
              <a key={i} href={p.u} target="_blank" rel="noopener" className="btn-ghost" style={{ fontSize: 11, padding: '5px 12px' }}>{PLAT[p.n]?.l || p.n} {I.ext()}</a>
            ))}
          </div>

          {/* Add to Pipeline button (discovery results only) */}
          {isDiscoveryResult && !pushed && (
            <div style={{ marginBottom: 16 }}>
              <button className="btn-terracotta" onClick={handleAddToPipeline} disabled={pushing} style={{ width: '100%', justifyContent: 'center', fontSize: 13, padding: '10px 16px' }}>
                {pushing ? I.loader() : I.zap()} {pushing ? 'Adding...' : 'Add to Pipeline'}
              </button>
              {pushErr && <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 4, padding: '4px 8px', background: 'var(--red-light)', borderRadius: 4 }}>{pushErr}</div>}
            </div>
          )}
          {pushed && pushResult && (
            <div style={{ marginBottom: 16, padding: '10px 14px', background: 'var(--sage-light)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--sage)' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--sage)', display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>{I.check()} Added to Pipeline</div>
              <a href={pushResult.task_url} target="_blank" rel="noopener" style={{ fontSize: 11, color: 'var(--terracotta)', textDecoration: 'none' }}>Open in ClickUp →</a>
            </div>
          )}

          {/* AI Analysis */}
          {(ai.content_fit || partnerships.length > 0 || ai.red_flags?.length > 0) && (
            <div style={{ padding: '14px 16px', background: 'var(--bg-inset)', borderRadius: 'var(--radius-sm)', marginBottom: 16, border: '1px solid var(--border-light)' }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', marginBottom: 8 }}>{I.zap()} AI Analysis</div>
              {partnerships.length > 0 && (
                <div style={{ marginBottom: 10, padding: '8px 10px', background: 'var(--purple-light)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--purple)' }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--purple)', marginBottom: 4 }}>Previous Brand Partnerships</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{partnerships.map((p, i) => <Pill key={i} color="var(--purple)" bg="white" style={{ fontSize: 11 }}>{p}</Pill>)}</div>
                </div>
              )}
              {partnerships.length === 0 && <div style={{ marginBottom: 8, padding: '6px 10px', background: 'var(--bg-muted)', borderRadius: 'var(--radius-xs)', fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>No known brand partnerships found — may need manual research</div>}
              {ai.content_fit && <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>{ai.content_fit}</p>}
              {ai.red_flags?.length > 0 && <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}><span style={{ fontSize: 11, color: 'var(--red)' }}>{I.alert()} Flags:</span>{ai.red_flags.map((f, i) => <Pill key={i} color="var(--red)" bg="var(--red-light)">{f}</Pill>)}</div>}
            </div>
          )}

          {/* Strategy */}
          {strategy && (
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', marginBottom: 12 }}>Outreach Strategy</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
                {strategy.recommended_product && <Pill color="var(--terracotta)" bg="var(--terracotta-light)">{strategy.recommended_product}</Pill>}
                {strategy.brand_fit_score && <Pill color="var(--sage)" bg="var(--sage-light)">{I.star()} Fit: {strategy.brand_fit_score}/10</Pill>}
                {strategy.estimated_rate_range && <Pill>{strategy.estimated_rate_range}</Pill>}
              </div>
              {strategy.creator_summary && <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 12 }}>{strategy.creator_summary}</p>}
              {strategy.outreach_angle && <div style={{ marginBottom: 12 }}><div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Outreach Angle</div><p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{strategy.outreach_angle}</p></div>}
              {strategy.personalization_hooks?.length > 0 && <div style={{ marginBottom: 12 }}><div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Personalization</div><ul style={{ paddingLeft: 16, margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.7 }}>{strategy.personalization_hooks.map((h, i) => <li key={i}>{h}</li>)}</ul></div>}
              {strategy.content_ideas?.length > 0 && <div style={{ marginBottom: 12 }}><div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Content Ideas</div><ul style={{ paddingLeft: 16, margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.7 }}>{strategy.content_ideas.map((c, i) => <li key={i}>{c}</li>)}</ul></div>}
              {strategy.suggested_email_body && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>{I.mail()} Draft Email</span>
                    <button onClick={() => copy(`Subject: ${strategy.suggested_subject_line}\n\n${strategy.suggested_email_body}`, 'email')} className="btn-ghost" style={{ padding: '3px 8px', fontSize: 10 }}>{copied === 'email' ? I.check() : I.clipboard()} {copied === 'email' ? 'Copied' : 'Copy'}</button>
                  </div>
                  <div style={{ padding: 12, background: 'var(--bg)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)', fontSize: 12, fontFamily: 'var(--font-mono)', lineHeight: 1.7, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
                    <div style={{ fontWeight: 600, color: 'var(--text)', marginBottom: 6 }}>Subject: {strategy.suggested_subject_line}</div>
                    {strategy.suggested_email_body}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
