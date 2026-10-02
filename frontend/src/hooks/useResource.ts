import { useCallback, useEffect, useState } from "react";

import { ApiError, type ApiClient } from "../api/client";

interface Resource<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/**
 * Loads one authenticated read and owns its loading and failure state.
 *
 * `load` must be memoized by the caller, since it is part of the effect's dependency list. A
 * session that has gone away is not retryable, so the caller ends the session and the app returns
 * to the profile chooser rather than showing an error the visitor cannot act on.
 */
export function useResource<T, C = ApiClient>(
  api: C,
  load: (api: C) => Promise<T>,
  onSessionGone: () => void,
): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    load(api)
      .then((value) => {
        if (active) {
          setData(value);
        }
      })
      .catch((caught: unknown) => {
        if (!active) {
          return;
        }
        if (caught instanceof ApiError && caught.isSessionGone) {
          onSessionGone();
          return;
        }
        setError(caught instanceof Error ? caught.message : "This could not be loaded.");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [api, load, attempt, onSessionGone]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);
  return { data, error, loading, reload };
}