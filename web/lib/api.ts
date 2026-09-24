/**
 * API 호출 헬퍼.
 * 모든 요청을 한 함수로 모아 base URL·에러 처리를 통일한다. 응답 타입은 제네릭으로 받아
 * 컴포넌트가 백엔드 Pydantic 모델과 같은 모양을 기대하도록 강제한다.
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
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return (await res.json()) as T;
}

export type Health = { status: "ok"; version: string; database: "ok" | "unavailable" };
