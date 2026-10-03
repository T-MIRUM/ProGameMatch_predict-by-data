"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Card, { ErrorNote } from "@/components/Card";
import FactorBars from "@/components/FactorBars";
import { ProbabilityBar, TeamLegend } from "@/components/ProbabilityBar";
import TeamEconomy, { LOADOUT_MEDIAN, type TeamEcon } from "@/components/TeamEconomy";
import { apiFetch, type MapsResponse, type PredictRequest, type PredictResponse, type Side } from "@/lib/api";
import { pct } from "@/lib/format";
import { useDebounce } from "@/lib/useDebounce";

/**
 * 화면 1 — 승률 시뮬레이터.
 * 라운드 번호는 입력받지 않고 스코어에서 계산한다(라운드 = A + B + 1).
 * 둘을 따로 받으면 '14라운드인데 스코어 9:6' 같은 불가능한 상태가 생기고, API가 422로 거부한다.
 */
export default function Simulator() {
  const [maps, setMaps] = useState<string[]>([]);
  const [mapName, setMapName] = useState("Ascent");
  const [scoreA, setScoreA] = useState(7);
  const [scoreB, setScoreB] = useState(6);
  const [side, setSide] = useState<Side | null>("atk");
  const [teamA, setTeamA] = useState<TeamEcon>({ buy: "Full buy: 20k+", loadout: 24500, credits: 2100 });
  const [teamB, setTeamB] = useState<TeamEcon>({ buy: "Eco: 0-5k", loadout: 3900, credits: 400 });

  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [latency, setLatency] = useState<number | null>(null);

  useEffect(() => {
    apiFetch<MapsResponse>("/api/maps")
      .then((r) => setMaps(r.maps.map((m) => m.name)))
      .catch(() => setMaps(["Ascent"]));
  }, []);

  const request: PredictRequest = useMemo(
    () => ({
      map_name: mapName,
      round_number: scoreA + scoreB + 1,
      score_a: scoreA,
      score_b: scoreB,
      team_a_buy_type: teamA.buy,
      team_b_buy_type: teamB.buy,
      team_a_loadout: teamA.loadout,
      team_b_loadout: teamB.loadout,
      team_a_credits: teamA.credits,
      team_b_credits: teamB.credits,
      team_a_side: side,
    }),
    [mapName, scoreA, scoreB, side, teamA, teamB],
  );
  const debounced = useDebounce(request, 300);
  const inflight = useRef<AbortController | null>(null);

  useEffect(() => {
    // 새 요청이 나가면 이전 요청은 취소한다: 늦게 도착한 옛 응답이 최신 결과를 덮어쓰는 것을 막는다
    inflight.current?.abort();
    const ctrl = new AbortController();
    inflight.current = ctrl;
    const t0 = performance.now();
    setLoading(true);
    apiFetch<PredictResponse>("/api/predict", { method: "POST", body: JSON.stringify(debounced), signal: ctrl.signal })
      .then((r) => {
        setResult(r);
        setError(null);
        setLatency(Math.round(performance.now() - t0));
      })
      .catch((e: Error) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (inflight.current === ctrl) setLoading(false);
      });
    return () => ctrl.abort();
  }, [debounced]);

  const round = scoreA + scoreB + 1;
  const phase = round <= 12 ? "전반" : round <= 24 ? "후반" : "연장";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">라운드 승률 시뮬레이터</h1>
        <p className="mt-1 text-sm text-muted">
          라운드가 시작되는 순간의 상태(맵·스코어·진영·이코노미)만으로 Team A가 이 라운드를 이길 확률을 계산합니다.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        {/* ---------------- 입력 ---------------- */}
        <Card title="라운드 상태">
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs text-muted">
                맵
                <select
                  value={mapName}
                  onChange={(e) => setMapName(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-border bg-raised px-2 py-1.5 text-sm text-text"
                >
                  {(maps.length ? maps : [mapName]).map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              </label>
              <div className="text-xs text-muted">
                Team A 진영
                <div role="radiogroup" aria-label="Team A 진영" className="mt-1 grid grid-cols-3 gap-1">
                  {([["atk", "공격"], ["def", "수비"], [null, "모름"]] as const).map(([v, l]) => (
                    <button
                      key={l}
                      type="button"
                      role="radio"
                      aria-checked={side === v}
                      onClick={() => setSide(v)}
                      className={`rounded-md border py-1.5 text-xs ${
                        side === v ? "border-secondary bg-raised font-semibold text-text" : "border-border text-secondary hover:bg-raised/60"
                      }`}
                    >
                      {l}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-end gap-4">
              <ScoreInput label="Team A 스코어" value={scoreA} onChange={setScoreA} />
              <span className="pb-2 text-muted">:</span>
              <ScoreInput label="Team B 스코어" value={scoreB} onChange={setScoreB} />
              <div className="pb-1.5 text-sm text-secondary">
                → <span className="font-semibold text-text">{round}라운드</span> <span className="text-muted">({phase})</span>
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <TeamEconomy team="a" value={teamA} onChange={setTeamA} />
              <TeamEconomy team="b" value={teamB} onChange={setTeamB} />
            </div>

            <button
              type="button"
              className="text-xs text-muted underline-offset-2 hover:text-secondary hover:underline"
              onClick={() => {
                setTeamA({ buy: "Full buy: 20k+", loadout: LOADOUT_MEDIAN["Full buy: 20k+"], credits: 4000 });
                setTeamB({ buy: "Full buy: 20k+", loadout: LOADOUT_MEDIAN["Full buy: 20k+"], credits: 4000 });
              }}
            >
              양 팀 풀바이로 초기화
            </button>
          </div>
        </Card>

        {/* ---------------- 결과 ---------------- */}
        <div className={`space-y-4 transition-opacity ${loading && result ? "opacity-60" : ""}`}>
          <Card>
            {error && <ErrorNote message={error} />}
            {result ? (
              <div className="space-y-5">
                <div>
                  <div className="text-sm text-muted">Team A 라운드 승리 확률</div>
                  <div className="mt-1 text-5xl font-semibold">{pct(result.win_probability_a)}</div>
                </div>
                <ProbabilityBar p={result.win_probability_a} height={16} />
                <TeamLegend />
                <div className="space-y-3 border-t border-border pt-4">
                  <div className="text-sm font-semibold">단순 기준과 비교</div>
                  <ProbabilityBar p={result.win_probability_a} label="모델 (LightGBM + 확률 보정)" height={10} />
                  {result.baseline_probability_a !== null && (
                    <ProbabilityBar
                      p={result.baseline_probability_a}
                      label="구매 유형 룩업표 (같은 조합의 과거 승률)"
                      height={10}
                    />
                  )}
                  <p className="text-xs text-muted">
                    룩업표는 구매 유형 조합만 봅니다. 모델은 장비 가치·크레딧·스코어·맵×진영까지 함께 봅니다.
                  </p>
                </div>
              </div>
            ) : (
              !error && <p className="text-sm text-muted">계산 중…</p>
            )}
          </Card>

          {result && (
            <Card title="예측에 크게 작용한 요인" subtitle="막대가 길수록 이 예측에 큰 영향을 준 입력입니다.">
              <FactorBars factors={result.top_factors} />
            </Card>
          )}
          <p className="text-[11px] text-muted">
            모멘텀(직전 라운드 결과)과 팀 강도는 이 화면에서 입력받지 않아 중립값으로 계산합니다.
            {latency !== null && <span className="ml-1">· 응답 {latency}ms</span>}
          </p>
        </div>
      </div>
    </div>
  );
}

function ScoreInput({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  const clamp = (v: number) => Math.max(0, Math.min(30, v));
  return (
    <label className="text-xs text-muted">
      {label}
      <div className="mt-1 flex items-center rounded-md border border-border bg-raised">
        <button type="button" aria-label={`${label} 감소`} className="px-2.5 py-1 text-secondary hover:text-text"
          onClick={() => onChange(clamp(value - 1))}>−</button>
        <input
          type="number"
          min={0}
          max={30}
          value={value}
          onChange={(e) => onChange(clamp(Number(e.target.value) || 0))}
          className="w-10 bg-transparent text-center text-sm text-text tabular [appearance:textfield]"
        />
        <button type="button" aria-label={`${label} 증가`} className="px-2.5 py-1 text-secondary hover:text-text"
          onClick={() => onChange(clamp(value + 1))}>+</button>
      </div>
    </label>
  );
}
