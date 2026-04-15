import { useState, type FormEvent } from "react";
import { startSearch, requestDownload } from "../api";
import type { SearchResult } from "../api";
import { useSearchPoll } from "../hooks/useSearchPoll";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [searchId, setSearchId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [downloadStatus, setDownloadStatus] = useState<
    Record<string, string>
  >({});

  const { session } = useSearchPoll(searchId);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setError("");
    setSubmitting(true);
    setSearchId(null);

    try {
      const res = await startSearch(query.trim());
      setSearchId(res.id);
    } catch (err: any) {
      setError(err.message || "Search failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDownload = async (result: SearchResult) => {
    const key = result.full_command;
    setDownloadStatus((prev) => ({ ...prev, [key]: "requesting" }));

    try {
      const res = await requestDownload(result.full_command);
      if (res.status === "already_exists") {
        setDownloadStatus((prev) => ({
          ...prev,
          [key]: "Already in library!",
        }));
      } else {
        setDownloadStatus((prev) => ({
          ...prev,
          [key]: "Requested - check library soon",
        }));
      }
    } catch (err: any) {
      setDownloadStatus((prev) => ({
        ...prev,
        [key]: `Error: ${err.message}`,
      }));
    }
  };

  const isSearching =
    submitting || (session && ["pending", "searching"].includes(session.status));

  return (
    <div className="search-page">
      <h2>Search Books</h2>

      <form onSubmit={handleSearch} className="search-form">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for books... (e.g. tolkien, dune, neuromancer)"
          disabled={!!isSearching}
          autoFocus
        />
        <button type="submit" disabled={!!isSearching || !query.trim()}>
          {isSearching ? "Searching..." : "Search"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {isSearching && (
        <div className="search-status">
          <div className="spinner" />
          <p>Searching IRC... this can take 10-30 seconds</p>
        </div>
      )}

      {session?.status === "failed" && (
        <p className="error">
          Search failed: {session.error_message || "Unknown error"}
        </p>
      )}

      {session?.status === "complete" && (
        <div className="search-results">
          <h3>
            {session.result_count} results for "{session.query}"
          </h3>
          {session.results.length === 0 ? (
            <p className="muted">No books found. Try a different query.</p>
          ) : (
            <div className="results-list">
              {session.results.map((r, i) => (
                <div key={i} className="result-item">
                  <div className="result-info">
                    <span className="result-name">{r.display_name}</span>
                    <span className="result-meta">
                      <span className="badge">{r.file_format}</span>
                      <span className="size">{r.file_size}</span>
                      <span className="bot">{r.bot_name}</span>
                    </span>
                  </div>
                  <div className="result-action">
                    {downloadStatus[r.full_command] === "requesting" ? (
                      <button disabled>Requesting...</button>
                    ) : downloadStatus[r.full_command] ? (
                      <span className="download-msg">
                        {downloadStatus[r.full_command]}
                      </span>
                    ) : (
                      <button onClick={() => handleDownload(r)}>
                        Download
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
