/**
 * API 클라이언트와 응답 타입.
 * 타입은 백엔드 Pydantic 스키마(src/propredict/api/schemas.py)와 같은 모양으로 둔다.
 * 모든 요청을 apiFetch 하나로 모아 base URL·에러 처리·요청 취소(AbortSignal)를 통일한다.
 */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* 본문이 JSON이 아니면 상태 문구를 그대로 쓴다 */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export function query(params: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------- 도메인 상수
export const BUY_TYPES = ["Eco: 0-5k", "Semi-eco: 5-10k", "Semi-buy: 10-20k", "Full buy: 20k+"] as const;
export type BuyType = (typeof BUY_TYPES)[number];
export const BUY_LABELS: Record<BuyType, string> = {
  "Eco: 0-5k": "Eco",
  "Semi-eco: 5-10k": "Semi-eco",
  "Semi-buy: 10-20k": "Semi-buy",
  "Full buy: 20k+": "Full buy",
};
export type Side = "atk" | "def";

// ---------------------------------------------------------------- 응답 타입
export type Health = { status: "ok"; version: string; database: "ok" | "unavailable"; model_loaded: boolean };
export type MapInfo = { name: string; map_games: number; rounds: number; last_season: number };
export type MapsResponse = { maps: MapInfo[]; seasons: number[] };

export type PredictRequest = {
  map_name: string;
  round_number: number;
  score_a: number;
  score_b: number;
  team_a_buy_type: BuyType;
  team_b_buy_type: BuyType;
  team_a_loadout: number | null;
  team_b_loadout: number | null;
  team_a_credits: number | null;
  team_b_credits: number | null;
  team_a_side: Side | null;
};
export type Factor = { feature: string; label: string; contribution: number };
export type PredictResponse = {
  win_probability_a: number;
  win_probability_b: number;
  baseline_probability_a: number | null;
  top_factors: Factor[];
};

export type BuyCell = { team_buy: BuyType; opponent_buy: BuyType; win_rate: number | null; count: number };
export type BuyMatrixResponse = {
  buy_types: BuyType[];
  cells: BuyCell[];
  rounds: number;
  map: string | null;
  season: number | null;
};
export type MapBalance = {
  map_name: string;
  map_games: number;
  rounds: number;
  side_known_rounds: number;
  attacker_win_rate: number | null;
  avg_rounds_per_map: number;
};

export type MatchSummary = {
  match_id: number;
  season: number;
  tournament: string;
  stage: string;
  match_type: string;
  team_a: string;
  team_b: string;
  score_a: number | null;
  score_b: number | null;
  maps: number;
  economy_rounds: number;
};
export type ReplayRound = {
  round_number: number;
  score_a: number;
  score_b: number;
  team_a_side: Side | null;
  team_a_buy_type: BuyType | null;
  team_b_buy_type: BuyType | null;
  team_a_loadout: number | null;
  team_b_loadout: number | null;
  winner: "A" | "B";
  win_probability_a: number | null;
  baseline_probability_a: number | null;
  upset: boolean;
};
export type ReplayMap = {
  map_game_id: number;
  map_name: string;
  map_order: number | null;
  score_a: number | null;
  score_b: number | null;
  rounds: ReplayRound[];
};
export type MatchRoundsResponse = {
  match: MatchSummary;
  team_a_strength: number;
  team_b_strength: number;
  maps: ReplayMap[];
};

export type MetricSet = { n: number; brier: number; log_loss: number; auc: number | null; ece: number };
export type CalibrationBin = {
  bin_lower: number;
  bin_upper: number;
  mean_predicted: number;
  observed_rate: number;
  count: number;
};
export type Significance = { diff: number; ci_low: number; ci_high: number; n_groups: number };
export type ModelMetrics = {
  trained_at: string;
  best_iteration: number;
  splits: Record<string, number[]>;
  rows: Record<string, number>;
  serving_model: string;
  models: Record<string, Record<string, MetricSet>>;
  calibration: Record<string, { raw: CalibrationBin[]; calibrated: CalibrationBin[] }>;
  significance: Record<string, Record<string, Significance>>;
  feature_importance: { feature: string; label: string; mean_abs_shap: number }[];
  calibration_method: string;
  calibration_cv: CalibrationCandidate[];
};
export type CalibrationCandidate = {
  method: string;
  cv_brier: number;
  cv_log_loss: number;
  cv_ece: number;
  selected: boolean;
};
