import React, { useState, useRef } from 'react';
import { api } from '../utils/api';
import { I } from './Icons';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export default function ImportTab() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  const doUpload = async (file) => {
    setUploading(true); setError(null); setResult(null);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await fetch(`${API_BASE}/import`, { method: 'POST', body: fd });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || 'Upload failed'); }
      setResult(await res.json());
    } catch (e) { setError(e.message); }
    setUploading(false);
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '40px 24px' }}>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 32, marginBottom: 4 }}>Import Creators</h1>
      <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 24 }}>Upload your existing creator spreadsheet</p>
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer?.files?.[0]; if (f) doUpload(f); }}
        onClick={() => fileRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? 'var(--terracotta)' : 'var(--border)'}`,
          borderRadius: 'var(--radius)', padding: '60px 40px', textAlign: 'center', cursor: 'pointer',
          background: dragging ? 'var(--terracotta-light)' : 'var(--bg-card)', transition: 'all 0.2s',
        }}
      >
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" style={{ display: 'none' }} onChange={e => e.target.files?.[0] && doUpload(e.target.files[0])} />
        <div style={{ marginBottom: 12, color: 'var(--text-muted)' }}>{I.upload(40)}</div>
        {uploading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, color: 'var(--terracotta)' }}>{I.loader()} Importing...</div>
        ) : (
          <>
            <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 4 }}>Drop a CSV or Excel file here</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Supports the 37-column Luma creator spreadsheet</div>
          </>
        )}
      </div>
      {error && <div style={{ marginTop: 16, padding: '12px 16px', background: 'var(--red-light)', borderRadius: 'var(--radius-xs)', color: 'var(--red)', fontSize: 13 }}>{error}</div>}
      {result && (
        <div className="fade-up" style={{ marginTop: 20, padding: '16px 20px', background: 'var(--sage-light)', borderRadius: 'var(--radius)', border: '1px solid var(--sage)' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--sage)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>{I.check()} Import Complete</div>
          <div style={{ display: 'flex', gap: 20, fontSize: 13, color: 'var(--text-secondary)' }}>
            <span><strong>{result.imported}</strong> imported</span>
            <span><strong>{result.duplicates_skipped}</strong> skipped</span>
            {result.errors?.length > 0 && <span style={{ color: 'var(--red)' }}><strong>{result.errors.length}</strong> errors</span>}
          </div>
        </div>
      )}
    </div>
  );
}
