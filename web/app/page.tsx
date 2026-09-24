"use client";

import { useEffect, useState } from "react";
import { apiFetch, type Health } from "@/lib/api";

/**
 * Phase 1 임시 메인 화면: 웹 → API → DB 연결이 살아 있는지만 보여 준다.
 * Phase 5에서 승률 시뮬레이터로 교체한다.
 */
export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Health>("/api/health")
      .then(setHealth)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <section className="rounded-lg border border-border bg-surface p-6">
      <h1 className="text-xl font-semibold">VCT 라운드 승률 예측</h1>
      <p className="mt-2 text-muted">시뮬레이터는 Phase 5에서 추가됩니다.</p>
      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted">API</dt>
        <dd>{error ? `연결 실패 (${error})` : health ? `ok · v${health.version}` : "확인 중…"}</dd>
        <dt className="text-muted">DB</dt>
        <dd>{health?.database ?? "-"}</dd>
      </dl>
    </section>
  );
}
