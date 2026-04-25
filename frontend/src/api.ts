const API_BASE = import.meta.env.DEV ? "http://localhost:8000" : "";

function getToken(): string | null {
  return localStorage.getItem("token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

// Auth
export async function login(password: string): Promise<{ token: string; admin: boolean }> {
  const data = await request<{ token: string; admin: boolean }>("/api/login", {
    method: "POST",
    body: JSON.stringify({ password }),
  });
  localStorage.setItem("token", data.token);
  localStorage.setItem("admin", data.admin ? "1" : "0");
  return data;
}

export function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("admin");
  window.location.href = "/";
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

export function isAdmin(): boolean {
  return localStorage.getItem("admin") === "1";
}

// Search
export interface SearchResult {
  bot_name: string;
  full_command: string;
  display_name: string;
  file_format: string;
  file_size: string;
}

export interface SearchSession {
  id: number;
  query: string;
  status: "pending" | "searching" | "complete" | "failed";
  results: SearchResult[];
  error_message: string | null;
  result_count: number;
  created_at: string;
}

export async function startSearch(query: string): Promise<{ id: number }> {
  return request("/api/search", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export async function getSearchStatus(id: number): Promise<SearchSession> {
  return request(`/api/search/${id}`);
}

export async function listSearches(): Promise<SearchSession[]> {
  return request("/api/searches");
}

// Books
export interface Book {
  id: number;
  title: string;
  author: string;
  filename: string;
  file_size: number;
  format: string;
  source_bot: string | null;
  created_at: string;
}

export async function requestDownload(
  command: string
): Promise<{ status: string; book?: Book; message: string }> {
  return request("/api/download", {
    method: "POST",
    body: JSON.stringify({ command }),
  });
}

export async function listBooks(q?: string, format?: string): Promise<Book[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (format) params.set("format", format);
  const qs = params.toString();
  return request(`/api/books${qs ? `?${qs}` : ""}`);
}

export function getDownloadUrl(bookId: number): string {
  const token = getToken();
  return `${API_BASE}/api/books/${bookId}/download?token=${token}`;
}

// Admin
export interface DownloadRecord {
  id: number;
  book_id: number;
  book_title: string | null;
  book_author: string | null;
  ip_address: string;
  user_agent: string | null;
  downloaded_at: string;
  ip_tag: IPTag | null;
}

export interface IPTag {
  id: number;
  ip_address: string;
  tag_name: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DownloadStat {
  ip_address: string;
  download_count: number;
  last_download: string | null;
  ip_tag: IPTag | null;
}

export async function listDownloads(ip?: string): Promise<DownloadRecord[]> {
  const qs = ip ? `?ip=${encodeURIComponent(ip)}` : "";
  return request(`/api/admin/downloads${qs}`);
}

export async function getDownloadStats(): Promise<DownloadStat[]> {
  return request("/api/admin/downloads/stats");
}

export async function listIPTags(): Promise<IPTag[]> {
  return request("/api/admin/ip-tags");
}

export async function createIPTag(
  ip_address: string,
  tag_name: string,
  notes?: string
): Promise<IPTag> {
  return request("/api/admin/ip-tags", {
    method: "POST",
    body: JSON.stringify({ ip_address, tag_name, notes }),
  });
}

export async function deleteIPTag(id: number): Promise<void> {
  await request(`/api/admin/ip-tags/${id}`, { method: "DELETE" });
}

// Status
export interface BotStatus {
  connected: boolean;
  joined: boolean;
  server: string;
  channel: string;
  nick: string;
  proxy: string | null;
  proxy_enabled: boolean;
  pending_search: boolean;
  pending_search_seconds: number | null;
  pending_download: boolean;
  pending_download_seconds: number | null;
}

export async function getBotStatus(): Promise<BotStatus> {
  return request("/api/status");
}

// Search Preferences (admin)
export interface WeightRule {
  tag: string;
  pattern: string;
  weight: number;
  label: string;
}

export interface SearchPrefs {
  allowed_formats: string[];
  weight_rules: WeightRule[];
  updated_at: string | null;
}

export async function getSearchPrefs(): Promise<SearchPrefs> {
  return request("/api/admin/search-prefs");
}

export async function updateSearchPrefs(
  prefs: { allowed_formats: string[]; weight_rules: WeightRule[] }
): Promise<SearchPrefs> {
  return request("/api/admin/search-prefs", {
    method: "PUT",
    body: JSON.stringify(prefs),
  });
}
