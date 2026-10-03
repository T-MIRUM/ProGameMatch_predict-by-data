"use client";

import { useState } from "react";
import CalibrationChart, { CalibrationLegend, CalibrationTable } from "@/components/CalibrationChart";
import Card, { ErrorNote } from "@/components/Card";
import ImportanceBars from "@/components/ImportanceBars";
import SignificancePlot from "@/components/SignificancePlot";
import StatTile from "@/components/StatTile";
import ViewToggle from "@/components/ViewToggle";
import type { ModelMetrics } from "@/lib/api";
import { int, pct, signed } from "@/lib/format";
import { useApi } from "@/lib/useApi";

const MODEL_LABELS: Record<string, string> = {
  "constant_0.5": "상수 50%",
  lookup_buy_matchup: "구매 유형 룩업표",
  logistic: "로지스틱 회귀",
  lightgbm: "LightGBM (보정 전)",
  lightgbm_calibrated: "LightGBM + 보정",
};
const MODEL_ORDER = ["constant_0.5", "lookup_buy_matchup", "logistic", "lightgbm", "lightgbm_calibrated"];
// valid_cal은 확률 보정을 '학습한' 데이터라 그 위의 보정 지표는 자기 평가가 된다. 화면에는 테스트 시즌만 둔다.
const SPLITS = [
  ["test_2025", "2025 테스트"],
  ["test_2026", "2026 테스트"],
] as const;
type Split = (typeof SPLITS)[number][0];

/**
 * 화면 4 — 모델 성능.
 * 질문 순서대로 배치한다: ① 단순 기준보다 나은가(타일·신뢰구간) ② 확률을 믿어도 되는가(신뢰도 곡선)
 * ③ 무엇을 보고 판단하는가(SHAP). 상단 시즌 탭은 ①②의 모든 숫자를 함께 바꾼다.
 */
export default function ModelPage() {
  const [split, setSplit] = useState<Split>("test_2025");
  const [calView, setCalView] = useState<"chart" | "table">("chart");
  const { data: m, error } = useApi<ModelMetrics>("/api/model/metrics");

  if (error) return <ErrorNote message={error} />;
  if (!m) return <p className="text-sm text-muted">불러오는 중…</p>;

  const serving = m.models[m.serving_model]?.[split];
  const lookup = m.models.lookup_buy_matchup?.[split];
  const constant = m.models["constant_0.5"]?.[split];
  const sig = m.significance[split] ?? {};
  const servSig = sig[`${m.serving_model}_vs_lookup`];
  const cal = m.calibration[split];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">모델 성능</h1>
        <p className="mt-1 text-sm text-muted">
          {m.splits.train.join("·")} 시즌으로 학습하고 {m.splits.valid.join("·")} 시즌으로 조기 종료·확률 보정을 한 뒤, 학습에 전혀
          쓰지 않은 {m.splits.test.join("·")} 시즌에서 평가했습니다.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3">
        <div role="tablist" aria-label="평가 시즌" className="flex rounded-md border border-border p-0.5 text-sm">
          {SPLITS.map(([k, l]) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={split === k}
              onClick={() => setSplit(k)}
              className={`rounded px-3 py-1 ${split === k ? "bg-raised font-semibold text-text" : "text-muted hover:text-secondary"}`}
            >
              {l}
            </button>
          ))}
        </div>
        <p className="text-[11px] text-muted">
          아래 지표·신뢰구간·신뢰도 곡선에 모두 적용됩니다. 평가 라운드 {int(m.rows[split])}개.
        </p>
      </div>

      {serving && lookup && constant && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            label="Brier 점수 (서비스 모델)"
            value={serving.brier.toFixed(4)}
            note={`낮을수록 좋음 · 룩업표 ${lookup.brier.toFixed(4)} · 상수 50% ${constant.brier.toFixed(4)}`}
          />
          <StatTile
            label="룩업표 대비 Brier 차이"
            value={servSig ? signed(servSig.diff, 4) : "–"}
            note={servSig && `95% 구간 [${signed(servSig.ci_low, 4)}, ${signed(servSig.ci_high, 4)}] · 경기 ${servSig.n_groups}개 부트스트랩`}
          />
          <StatTile label="보정 오차 (ECE)" value={pct(serving.ece)} note="예측 확률과 실제 승률의 평균 차이 (10구간)" />
          <StatTile label="AUC" value={serving.auc?.toFixed(3) ?? "–"} note={`룩업표 ${lookup.auc?.toFixed(3) ?? "–"} · 0.5 = 무작위`} />
        </div>
      )}

      <Card
        title="단순 기준보다 나은가"
        subtitle="Brier 점수 하락의 대부분은 '구매 유형'만 봐도 얻어집니다(상수 0.250 → 룩업표). 모델의 추가 개선은 작지만, 구간이 0을 넘지 않으면 우연이 아니라고 볼 수 있습니다."
      >
        <SignificancePlot
          rows={["logistic", "lightgbm", "lightgbm_calibrated"]
            .filter((k) => sig[`${k}_vs_lookup`])
            .map((k) => ({ label: MODEL_LABELS[k], s: sig[`${k}_vs_lookup`] }))}
        />
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[34rem] text-sm">
            <thead className="text-xs text-muted">
              <tr className="border-b border-border">
                <th className="py-1.5 text-left font-normal">모델</th>
                <th className="py-1.5 text-right font-normal">Brier ↓</th>
                <th className="py-1.5 text-right font-normal">Log loss ↓</th>
                <th className="py-1.5 text-right font-normal">AUC ↑</th>
                <th className="py-1.5 text-right font-normal">ECE ↓</th>
              </tr>
            </thead>
            <tbody className="tabular">
              {MODEL_ORDER.filter((k) => m.models[k]?.[split]).map((k) => {
                const s = m.models[k][split];
                const isServing = k === m.serving_model;
                return (
                  <tr key={k} className={`border-b border-border/60 ${isServing ? "bg-raised" : ""}`}>
                    <td className={`py-1.5 pl-1 ${isServing ? "font-semibold text-text" : "text-secondary"}`}>
                      {MODEL_LABELS[k] ?? k}
                      {isServing && <span className="ml-1.5 text-[11px] font-normal text-muted">서비스 중</span>}
                    </td>
                    <td className="py-1.5 text-right">{s.brier.toFixed(4)}</td>
                    <td className="py-1.5 text-right text-secondary">{s.log_loss.toFixed(4)}</td>
                    <td className="py-1.5 text-right text-secondary">{s.auc?.toFixed(3) ?? "–"}</td>
                    <td className="py-1.5 pr-1 text-right text-secondary">{pct(s.ece)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card
          title="확률을 믿어도 되는가"
          subtitle="예측을 10% 구간으로 묶어 실제 승률과 비교합니다. 점선(대각선)에 붙을수록 확률이 정직합니다."
          actions={<ViewToggle value={calView} onChange={setCalView} />}
        >
          {cal ? (
            calView === "chart" ? (
              <div className="space-y-3">
                <CalibrationLegend />
                <CalibrationChart raw={cal.raw} calibrated={cal.calibrated} />
              </div>
            ) : (
              <CalibrationTable raw={cal.raw} calibrated={cal.calibrated} />
            )
          ) : (
            <p className="text-sm text-muted">이 시즌의 보정 데이터가 없습니다.</p>
          )}
        </Card>

        <Card
          title="무엇을 보고 판단하는가"
          subtitle="2025 테스트 표본에서 각 입력이 예측을 평균적으로 얼마나 움직였는지(평균 |SHAP|, 로그오즈)입니다. 시즌 탭과 무관합니다."
        >
          <ImportanceBars items={m.feature_importance} />
        </Card>
      </div>

      <p className="text-[11px] text-muted">
        학습 시각 {new Date(m.trained_at).toLocaleString("ko-KR")} · LightGBM 최적 반복 {m.best_iteration}회 · 학습 행{" "}
        {int(m.rows.train_augmented)}개(좌우 반전 증강 포함)
      </p>
    </div>
  );
}
