/**
 * 발산 색 척도: 승률 50%는 중립 회색, 100%로 갈수록 파랑, 0%로 갈수록 빨강.
 * 단계를 미리 나누지 않고 CSS color-mix(OKLab)로 연속 보간한다:
 * OKLab은 지각적으로 균일해서 '40%→30%'와 '60%→70%'의 색 변화가 같은 크기로 보인다.
 * 색 값은 globals.css 토큰을 참조하므로 팔레트를 바꿀 때 여기는 고치지 않아도 된다.
 */
export function divergingColor(p: number): string {
  const t = Math.min(Math.abs(p - 0.5) / 0.5, 1);
  const pole = p >= 0.5 ? "var(--color-div-pos)" : "var(--color-div-neg)";
  return `color-mix(in oklab, ${pole} ${Math.round(t * 100)}%, var(--color-div-mid))`;
}
