const API = import.meta.env.VITE_API_URL || '/api';

export async function api(path, opts = {}) {
  const { method = 'GET', body, params } = opts;
  let url = `${API}${path}`;
  if (params) {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v != null && v !== '') sp.append(k, v);
    });
    const qs = sp.toString();
    if (qs) url += `?${qs}`;
  }
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

export function fmtNum(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toLocaleString();
}

export const PLAT = {
  tiktok: { a: 'TT', c: '#000', l: 'TikTok' },
  instagram: { a: 'IG', c: '#E1306C', l: 'Instagram' },
  youtube: { a: 'YT', c: '#FF0000', l: 'YouTube' },
  twitter: { a: 'X', c: '#1DA1F2', l: 'X' },
  linkedin: { a: 'LI', c: '#0A66C2', l: 'LinkedIn' },
};

export const CREATOR_TYPES = [
  'Doctor/Medical', 'UGC Creator', 'Health Influencer', 'Fitness Creator',
  'Mom/Parenting', 'Wellness/Lifestyle', 'Nutritionist/Dietitian', 'Podcaster',
];

export const CONTENT_NICHES = [
  'Heart Health', 'Gut Health', 'Longevity', 'Supplements', 'Nutrition',
  'Fitness', 'General Wellness', 'Weight Loss', 'Mental Health', 'Biohacking',
  "Women's Health", "Men's Health",
];
