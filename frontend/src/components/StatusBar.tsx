import { useState, useEffect } from "react";
import { getBotStatus } from "../api";
import type { BotStatus } from "../api";

export default function StatusBar() {
  const [status, setStatus] = useState<BotStatus | null>(null);

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
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!status) return null;

  return (
    <div className="status-bar">
      <span
        className={`status-dot ${status.connected && status.joined ? "online" : "offline"}`}
      />
      <span className="status-text">
        {status.connected && status.joined
          ? `Connected to ${status.channel} as ${status.nick}`
          : status.connected
            ? "Connecting to channel..."
            : "Disconnected from IRC"}
      </span>
      {status.pending_search && <span className="status-badge">Searching...</span>}
      {status.pending_download && (
        <span className="status-badge">Downloading...</span>
      )}
    </div>
  );
}
