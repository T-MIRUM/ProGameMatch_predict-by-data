"use client";

import { useLayoutEffect, useRef, useState, type FocusEvent, type PointerEvent, type ReactNode } from "react";

type Tip = { x: number; y: number; content: ReactNode } | null;

/**
 * 차트 공용 툴팁. 마크(셀·막대)에 마우스를 올리거나 키보드로 포커스하면 값을 띄운다.
 * 툴팁 폭은 내용마다 달라서 렌더 후 실제 폭을 재고(useLayoutEffect: 화면에 그려지기 전에 실행)
 * 컨테이너 좌우 끝을 넘지 않게 위치를 당긴다. 그래서 오른쪽 끝 칸에서도 잘리지 않는다.
 * pointer-events: none이라 툴팁이 아래 마크의 hover를 가로채지 않는다.
 */
export function useHoverTip() {
  const ref = useRef<HTMLDivElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<Tip>(null);

  const place = (clientX: number, clientY: number, content: ReactNode) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    setTip({ x: clientX - box.left, y: clientY - box.top, content });
  };

  useLayoutEffect(() => {
    const el = tipRef.current;
    const box = ref.current;
    if (!tip || !el || !box) return;
    const w = el.offsetWidth;
    el.style.left = `${Math.min(Math.max(tip.x - w / 2, 0), Math.max(box.clientWidth - w, 0))}px`;
  }, [tip]);

  const bind = (content: ReactNode) => ({
    onPointerMove: (e: PointerEvent) => place(e.clientX, e.clientY, content),
    onPointerLeave: () => setTip(null),
    onFocus: (e: FocusEvent) => {
      const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
      place(r.left + r.width / 2, r.top, content);
    },
    onBlur: () => setTip(null),
  });

  const layer = tip && (
    <div
      ref={tipRef}
      role="tooltip"
      className="pointer-events-none absolute z-20 w-max max-w-full -translate-y-[calc(100%+10px)] rounded-md border border-border bg-raised px-2.5 py-1.5 text-xs text-secondary shadow-lg shadow-black/40"
      style={{ left: tip.x, top: tip.y }}
    >
      {tip.content}
    </div>
  );

  return { ref, bind, layer };
}
