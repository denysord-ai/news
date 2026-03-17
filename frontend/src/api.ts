import type { NewsItem } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type SyncResponse = {
  status: string;
  total_fetched: number;
  inserted: number;
  updated: number;
  failed_sources: number;
};

export async function fetchNews(limit = 20, offset = 0): Promise<NewsItem[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  const response = await fetch(`${API_BASE_URL}/api/news?${params.toString()}`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch news: ${response.status}`);
  }

  const payload = (await response.json()) as NewsItem[];
  return payload;
}

export async function syncNews(): Promise<SyncResponse> {
  const response = await fetch(`${API_BASE_URL}/api/sync`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to sync news: ${response.status}`);
  }

  return (await response.json()) as SyncResponse;
}
