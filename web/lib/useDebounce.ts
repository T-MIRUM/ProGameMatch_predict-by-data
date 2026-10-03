import { useEffect, useState } from "react";

/**
 * 값이 delay(ms) 동안 바뀌지 않을 때만 갱신된 값을 돌려준다.
 * 슬라이더를 끄는 동안 매 픽셀마다 API를 부르지 않게 한다(명세: 디바운스 300ms).
 */
export function useDebounce<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}
