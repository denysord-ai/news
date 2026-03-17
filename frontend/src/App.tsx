import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchNews, syncNews } from "./api";
import { NewsList } from "./components/NewsList";
import type { NewsItem } from "./types";

function App() {
  const PAGE_SIZE = 20;

  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  const loadFirstPage = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await fetchNews(PAGE_SIZE, 0);
      setItems(data);
      setOffset(data.length);
      setHasMore(data.length === PAGE_SIZE);
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Failed to load news.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [PAGE_SIZE]);

  useEffect(() => {
    void loadFirstPage();
  }, [loadFirstPage]);

  const loadMore = useCallback(async () => {
    if (loading || loadingMore || syncing || !hasMore) {
      return;
    }

    setLoadingMore(true);
    try {
      const data = await fetchNews(PAGE_SIZE, offset);
      if (data.length > 0) {
        setItems((current) => [...current, ...data]);
        setOffset((current) => current + data.length);
      }
      setHasMore(data.length === PAGE_SIZE);
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Failed to load more news.";
      setError(message);
    } finally {
      setLoadingMore(false);
    }
  }, [PAGE_SIZE, hasMore, loading, loadingMore, offset, syncing]);

  useEffect(() => {
    if (!loadMoreRef.current) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          void loadMore();
        }
      },
      { rootMargin: "400px" },
    );

    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [loadMore]);

  const loadNewPosts = useCallback(async () => {
    setSyncing(true);
    setError(null);

    try {
      await syncNews();
      await loadFirstPage();
    } catch (syncError) {
      const message = syncError instanceof Error ? syncError.message : "Failed to load new posts.";
      setError(message);
    } finally {
      setSyncing(false);
    }
  }, [loadFirstPage]);

  const sourceOptions = useMemo(() => {
    const unique = new Map<string, string>();
    for (const item of items) {
      unique.set(item.source_id, item.source_name);
    }

    return Array.from(unique.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [items]);

  const filteredItems = useMemo(() => {
    if (selectedSourceIds.length === 0) {
      return items;
    }

    const selected = new Set(selectedSourceIds);
    return items.filter((item) => selected.has(item.source_id));
  }, [items, selectedSourceIds]);

  function toggleSource(sourceId: string): void {
    setSelectedSourceIds((current) =>
      current.includes(sourceId) ? current.filter((id) => id !== sourceId) : [...current, sourceId],
    );
  }

  return (
    <div className="app-shell">
      <header className="top-bar">
        <h1>AI News Aggregator</h1>
        <button type="button" onClick={() => void loadNewPosts()} disabled={loading || syncing}>
          {syncing ? "Loading..." : "Load new posts"}
        </button>
      </header>

      <main className="content">
        {loading && <p className="state-message">Loading news...</p>}
        {!loading && error && <p className="state-message state-error">{error}</p>}
        {!loading && !error && (
          <>
            <section className="filters-panel" aria-label="Source filters">
              <div className="filters-header">
                <h2>Filter by source</h2>
                <button type="button" onClick={() => setSelectedSourceIds([])} disabled={selectedSourceIds.length === 0}>
                  All sources
                </button>
              </div>
              <div className="filters-list">
                {sourceOptions.map((source) => (
                  <label key={source.id} className="filter-option">
                    <input
                      type="checkbox"
                      checked={selectedSourceIds.includes(source.id)}
                      onChange={() => toggleSource(source.id)}
                    />
                    <span>{source.name}</span>
                  </label>
                ))}
              </div>
              <p className="filters-count">
                Showing {filteredItems.length} of {items.length}
              </p>
            </section>
            <NewsList items={filteredItems} />
            {loadingMore && <p className="state-message">Loading more...</p>}
            {!loadingMore && !hasMore && <p className="state-message">You reached the end of the list.</p>}
            <div ref={loadMoreRef} aria-hidden="true" style={{ height: 1 }} />
          </>
        )}
      </main>
    </div>
  );
}

export default App;
