const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const CSRF_COOKIE_NAME = import.meta.env.VITE_CSRF_COOKIE_NAME ?? "rythm_csrf";

export type User = {
  id: number;
  email: string;
  username: string;
  locale: string;
  role: string;
  status: string;
  points_balance: number;
  is_email_verified: boolean;
  email_verified_at: string | null;
  last_login_at: string | null;
  created_at: string;
};

export type AuthResponse = {
  user: User;
  daily_bonus_awarded: number;
};

export type Message = {
  message: string;
};

export type BrowserSession = {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  last_seen_at: string;
  created_at: string;
  current: boolean;
};

export type Analysis = {
  id: number;
  original_filename: string;
  file_format: string;
  file_size: number;
  duration_sec: number | string | null;
  sample_rate: number | null;
  channels: number | null;
  bpm: number | string | null;
  musical_key: string | null;
  lufs: number | string | null;
  rms: number | string | null;
  waveform: number[] | null;
  spectrogram: number[][] | null;
  genre: string | null;
  genre_confidence: number | string | null;
  genre_model_status: string;
  genre_model_version: string | null;
  lyrics: string | null;
  lyrics_status: string;
  ai_summary: string | null;
  ai_summary_source: string;
  status: string;
  points_cost: number;
  created_at: string;
};

export type Generation = {
  id: number;
  title: string;
  prompt: string;
  instrumental: boolean;
  duration_sec: number;
  provider: string;
  status: string;
  audio_url: string | null;
  points_cost: number;
  error_message: string | null;
  created_at: string;
};

export type Work = {
  id: number;
  generation_id: number;
  title: string;
  description: string;
  cover_gradient: "violet" | "cyan" | "sunset" | "midnight";
  likes_count: number;
  audio_url: string | null;
  creator_name: string;
  created_at: string;
};

export type Founder = {
  artist_name: string;
  tagline: string;
  bio: string;
  styles: string[];
};

function cookie(name: string): string {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie.split("; ").find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : "";
}

function csrfHeaders(headers: Headers, method: string): void {
  if (["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) return;
  const token = cookie(CSRF_COOKIE_NAME);
  if (token) headers.set("X-CSRF-Token", token);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = init.method ?? "GET";
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  csrfHeaders(headers, method);

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    method,
    headers,
    credentials: "include"
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ error: { message: "Request failed." } }));
    throw new Error(detail.error?.message ?? "Request failed.");
  }
  return response.json() as Promise<T>;
}

async function requestBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ error: { message: "Request failed." } }));
    throw new Error(detail.error?.message ?? "Request failed.");
  }
  return response.blob();
}

export const api = {
  register: (
    email: string,
    username: string,
    password: string,
    locale: string,
    termsVersion: string,
    turnstileToken: string
  ) =>
    request<Message>("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        username,
        password,
        password_confirmation: password,
        locale,
        terms_version: termsVersion,
        terms_accepted: true,
        turnstile_token: turnstileToken
      })
    }),
  verifyEmail: (token: string) =>
    request<Message>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token })
    }),
  login: (email: string, password: string, turnstileToken: string) =>
    request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, turnstile_token: turnstileToken })
    }),
  resendVerification: (email: string, turnstileToken: string) =>
    request<Message>("/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ email, turnstile_token: turnstileToken })
    }),
  forgotPassword: (email: string, turnstileToken: string) =>
    request<Message>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email, turnstile_token: turnstileToken })
    }),
  resetPassword: (token: string, password: string) =>
    request<Message>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({
        token,
        password,
        password_confirmation: password
      })
    }),
  logout: () => request<Message>("/auth/logout", { method: "POST" }),
  logoutAll: () => request<Message>("/auth/logout-all", { method: "POST" }),
  sessions: () => request<BrowserSession[]>("/auth/sessions"),
  revokeSession: (id: string) =>
    request<Message>(`/auth/sessions/${encodeURIComponent(id)}`, { method: "DELETE" }),
  me: () => request<User>("/auth/me"),
  analyze: (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<Analysis>("/songs/analyze", { method: "POST", body: data });
  },
  history: () => request<{ items: Analysis[]; total: number }>("/songs/history"),
  report: (id: number) => requestBlob(`/songs/history/${id}/report`),
  generate: (prompt: string, title: string, instrumental: boolean, durationSec: number) =>
    request<Generation>("/music/generations", {
      method: "POST",
      body: JSON.stringify({ prompt, title: title || null, instrumental, duration_sec: durationSec })
    }),
  generations: () => request<Generation[]>("/music/generations"),
  refreshGeneration: (id: number) =>
    request<Generation>(`/music/generations/${id}/refresh`, { method: "POST" }),
  publish: (
    generationId: number,
    title: string,
    description: string,
    coverGradient: Work["cover_gradient"]
  ) =>
    request<Work>("/music/works", {
      method: "POST",
      body: JSON.stringify({
        generation_id: generationId,
        title: title || null,
        description,
        cover_gradient: coverGradient
      })
    }),
  works: () => request<Work[]>("/music/works"),
  like: (id: number) => request<Work>(`/music/works/${id}/like`, { method: "POST" }),
  founder: () => request<Founder>("/music/founder")
};
