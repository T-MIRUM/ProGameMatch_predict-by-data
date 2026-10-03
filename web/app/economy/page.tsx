"use client";

import { useState } from "react";
import BuyMatrix, { BuyMatrixTable, DivergingLegend } from "@/components/BuyMatrix";
import Card, { ErrorNote } from "@/components/Card";
import MapBalance, { MapBalanceTable } from "@/components/MapBalance";
import ViewToggle from "@/components/ViewToggle";
import { query, type BuyMatrixResponse, type MapBalance as MapBalanceRow, type MapsResponse } from "@/lib/api";
import { int } from "@/lib/format";
import { useApi } from "@/lib/useApi";

const selectCls = "mt-1 block w-full rounded-md border border-border bg-raised px-2 py-1.5 text-sm text-text";

/**
 * 화면 2 — 이코노미 매트릭스.
 * 시즌 필터는 페이지 맨 위 한 줄에 두고 아래 두 차트를 모두 좁힌다.
 * 맵 필터는 매트릭스에만 적용되므로(맵 밸런스는 맵 전체를 비교하는 차트) 매트릭스 카드 안에 둔다.
 */
export default function EconomyPage() {
  const [season, setSeason] = useState<string>("");
  const [mapName, setMapName] = useState<string>("");
  const [matrixView, setMatrixView] = useState<"chart" | "table">("chart");
  const [balanceView, setBalanceView] = useState<"chart" | "table">("chart");

  const meta = useApi<MapsResponse>("/api/maps");
  const matrix = useApi<BuyMatrixResponse>(`/api/stats/buy-matrix${query({ map: mapName, season })}`);
  const balance = useApi<MapBalanceRow[]>(`/api/stats/map-balance${query({ season })}`);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">이코노미 매트릭스</h1>
        <p className="mt-1 text-sm text-muted">
          양 팀의 구매 유형 조합별 실제 라운드 승률과, 맵별 공격·수비 균형을 봅니다. 모델이 아니라 원본 기록의 집계입니다.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface px-4 py-3">
        <label className="w-40 text-xs text-muted">
          시즌
          <select value={season} onChange={(e) => setSeason(e.target.value)} className={selectCls}>
            <option value="">전체 (2021–2026)</option>
            {meta.data?.seasons.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <p className="pb-1.5 text-[11px] text-muted">아래 두 차트에 모두 적용됩니다.</p>
      </div>

      <Card
        title="구매 유형 매치업 승률"
        subtitle={
          <>
            행 팀이 그 라운드를 이긴 비율입니다. 한 라운드를 양 팀 시점에서 한 번씩 세므로 대각선은 항상 50%이고, 마주
            보는 칸의 합은 100%입니다.
          </>
        }
        actions={<ViewToggle value={matrixView} onChange={setMatrixView} chartLabel="히트맵" />}
      >
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <label className="w-40 text-xs text-muted">
            맵
            <select value={mapName} onChange={(e) => setMapName(e.target.value)} className={selectCls}>
              <option value="">전체 맵</option>
              {meta.data?.maps.map((m) => (
                <option key={m.name}>{m.name}</option>
              ))}
            </select>
          </label>
          {matrix.data && (
            <p className="pb-1.5 text-xs text-muted">
              이코노미 기록이 있는 라운드 {int(matrix.data.rounds)}개
            </p>
          )}
        </div>
        {matrix.error && <ErrorNote message={matrix.error} />}
        <div className={`transition-opacity ${matrix.loading && matrix.data ? "opacity-60" : ""}`}>
          {!matrix.data ? (
            !matrix.error && <p className="text-sm text-muted">불러오는 중…</p>
          ) : matrix.data.rounds === 0 ? (
            <p className="text-sm text-muted">이 맵·시즌 조합에는 이코노미 기록이 없습니다.</p>
          ) : matrixView === "chart" ? (
            <div className="space-y-4">
              <BuyMatrix data={matrix.data} />
              <DivergingLegend />
            </div>
          ) : (
            <BuyMatrixTable data={matrix.data} />
          )}
        </div>
      </Card>

      <Card
        title="맵별 공격 진영 승률"
        subtitle="50%에서 얼마나 벗어나는지로 그렸습니다. 진영은 승리 방식(설치 폭발·해체·시간 초과)으로 추정했고, 진영을 알 수 없는 라운드는 제외했습니다."
        actions={<ViewToggle value={balanceView} onChange={setBalanceView} />}
      >
        {balance.error && <ErrorNote message={balance.error} />}
        <div className={`transition-opacity ${balance.loading && balance.data ? "opacity-60" : ""}`}>
          {!balance.data ? (
            !balance.error && <p className="text-sm text-muted">불러오는 중…</p>
          ) : balance.data.length === 0 ? (
            <p className="text-sm text-muted">이 시즌에는 기록이 없습니다.</p>
          ) : balanceView === "chart" ? (
            <MapBalance rows={balance.data} />
          ) : (
            <MapBalanceTable rows={balance.data} />
          )}
        </div>
      </Card>
    </div>
  );
}
