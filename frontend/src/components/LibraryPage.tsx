import { useState, useEffect } from "react";
import { listBooks, getDownloadUrl } from "../api";
import type { Book } from "../api";

export default function LibraryPage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [formatFilter, setFormatFilter] = useState("");

  const fetchBooks = async () => {
    setLoading(true);
    try {
      const data = await listBooks(filter || undefined, formatFilter || undefined);
      setBooks(data);
    } catch (err) {
      console.error("Failed to load books:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBooks();
  }, []);

  useEffect(() => {
    const timeout = setTimeout(fetchBooks, 300);
    return () => clearTimeout(timeout);
  }, [filter, formatFilter]);

  // Auto-refresh every 10s to catch new downloads
  useEffect(() => {
    const interval = setInterval(fetchBooks, 10000);
    return () => clearInterval(interval);
  }, [filter, formatFilter]);

  const formats = [...new Set(books.map((b) => b.format))].sort();

  const formatSize = (bytes: number) => {
    if (bytes === 0) return "Unknown";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="library-page">
      <h2>Library ({books.length} books)</h2>

      <div className="library-filters">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by title or author..."
        />
        <select
          value={formatFilter}
          onChange={(e) => setFormatFilter(e.target.value)}
        >
          <option value="">All formats</option>
          {formats.map((f) => (
            <option key={f} value={f}>
              {f.toUpperCase()}
            </option>
          ))}
        </select>
        <button onClick={fetchBooks} className="btn-secondary">
          Refresh
        </button>
      </div>

      {loading && books.length === 0 ? (
        <div className="search-status">
          <div className="spinner" />
          <p>Loading library...</p>
        </div>
      ) : books.length === 0 ? (
        <p className="muted">
          No books yet. Search and download some books first!
        </p>
      ) : (
        <div className="books-grid">
          {books.map((book) => (
            <div key={book.id} className="book-card">
              <div className="book-format">{book.format.toUpperCase()}</div>
              <h3 className="book-title">{book.title}</h3>
              <p className="book-author">{book.author}</p>
              <div className="book-meta">
                <span>{formatSize(book.file_size)}</span>
                <span>{new Date(book.created_at).toLocaleDateString()}</span>
              </div>
              <a
                href={getDownloadUrl(book.id)}
                className="btn-download"
                download
              >
                Download
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
