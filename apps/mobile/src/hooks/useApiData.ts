import { useState, useEffect, useCallback, useRef } from 'react';
import type { ApiResponse } from '@api/client';

interface UseApiDataResult<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Fetches data from an API function when the component mounts.
 * Supports auto-refresh via the returned `refresh` callback.
 */
export function useApiData<T>(
  fetchFn: () => Promise<ApiResponse<T>>,
  deps: unknown[] = [],
): UseApiDataResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const fetchFnRef = useRef(fetchFn);
  fetchFnRef.current = fetchFn;

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetchFnRef.current();
      if (!mountedRef.current) return;
      if (response.ok) {
        setData(response.data);
      } else {
        setError(response.error?.message || 'Failed to load data');
      }
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    mountedRef.current = true;
    load();
    return () => {
      mountedRef.current = false;
    };
  }, [load]);

  return { data, isLoading, error, refresh: load };
}

export default useApiData;
