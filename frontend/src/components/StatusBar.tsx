import { useState, useEffect } from "react";
import { getBotStatus, isAdmin } from "../api";
import type { BotStatus } from "../api";

export default function StatusBar() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const admin = isAdmin();

  useEffect(() => {
    const poll = async () => {
      try {
        const s = await getBotStatus();
        setStatus(s);
      } catch {
        setStatus(null);
      }
    };

    poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, []);

  if (!status) return null;

  const fmtWait = (seconds: number | null) => {
    if (seconds === null) return "";
    if (seconds < 60) return `${seconds}s`;
    return `${Math.floor(seconds / 60)}m${seconds % 60}s`;
  };

  return (
    <div className="status-bar">
      <span
        className={`status-dot ${status.connected && status.joined ? "online" : "offline"}`}
      />
      <span className="status-text">
        {status.connected && status.joined
          ? `Connected as ${status.nick}`
          : status.connected
            ? "Connecting to channel..."
            : "Disconnected from IRC"}
      </span>
      {admin && status.proxy_enabled && status.proxy && (
        <span className="status-badge proxy-badge">
          via {status.proxy}
        </span>
      )}
      {status.pending_search && (
        <span className="status-badge">
          Searching... {fmtWait(status.pending_search_seconds)}
        </span>
      )}
      {status.pending_download && (
        <span className="status-badge">
          Downloading... {fmtWait(status.pending_download_seconds)}
        </span>
      )}
    </div>
  );
}
