"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

/**
 * GET 요청 훅. 경로(path)가 바뀌면 이전 요청을 취소하고 새로 요청한다.
 * 새 응답이 올 때까지 이전 data를 그대로 돌려준다: 화면이 빈 상태로 깜빡이지 않고,
 * 호출하는 쪽은 loading을 보고 이전 결과를 흐리게 표시한다.
 * path가 null이면 요청하지 않는다(필수 선택이 아직 없을 때).
 */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!path) return;
    const ctrl = new AbortController();
    setLoading(true);
    apiFetch<T>(path, { signal: ctrl.signal })
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e: Error) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [path]);

  return { data, error, loading };
}
