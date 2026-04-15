import { useState, useEffect } from "react";
import { getSearchStatus } from "../api";
import type { SearchSession } from "../api";

/**
 * Hook that polls a search session until it's complete or failed.
 */
export function useSearchPoll(sessionId: number | null) {
  const [session, setSession] = useState<SearchSession | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (sessionId === null) {
      setSession(null);
      return;
    }

    setLoading(true);
    let cancelled = false;
    let timeout: ReturnType<typeof setTimeout>;

    const poll = async () => {
      if (cancelled) return;
      try {
        const data = await getSearchStatus(sessionId);
        if (cancelled) return;
        setSession(data);
        setLoading(false);

        if (data.status === "pending" || data.status === "searching") {
          timeout = setTimeout(poll, 1500);
        }
      } catch (err) {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    poll();

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [sessionId]);

  return { session, loading };
}
