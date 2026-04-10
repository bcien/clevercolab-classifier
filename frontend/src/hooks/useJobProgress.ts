"use client";

/**
 * Polls the backend for job status every 2 seconds.
 * Stops automatically when the job reaches "complete" or "failed".
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { getJobStatus } from "@/lib/api";
import type { JobStatus } from "@/lib/types";

const POLL_INTERVAL = 2000;

export function useJobProgress(jobId: string | null) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;

    const poll = async () => {
      try {
        const data = await getJobStatus(jobId);
        if (cancelled) return;
        setStatus(data);

        if (data.stage === "complete" || data.stage === "failed") {
          stop();
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Error desconocido");
        stop();
      }
    };

    // Initial fetch
    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL);

    return () => {
      cancelled = true;
      stop();
    };
  }, [jobId, stop]);

  return { status, error };
}
