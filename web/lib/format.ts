/** 숫자 표기 — 한 곳에서 관리해 화면마다 자릿수가 달라지지 않게 한다. */
export const pct = (p: number | null | undefined, digits = 1): string =>
  p === null || p === undefined ? "–" : `${(p * 100).toFixed(digits)}%`;

export const int = (n: number | null | undefined): string =>
  n === null || n === undefined ? "–" : n.toLocaleString("ko-KR");

/** 크레딧: 24,500 → "24.5k" (원본 데이터 표기와 같게) */
export const credits = (n: number | null | undefined): string =>
  n === null || n === undefined ? "모름" : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);

export const signed = (x: number, digits = 3): string => `${x > 0 ? "+" : ""}${x.toFixed(digits)}`;
