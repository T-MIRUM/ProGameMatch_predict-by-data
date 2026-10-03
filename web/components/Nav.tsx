"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "승률 시뮬레이터" },
  { href: "/economy", label: "이코노미 매트릭스" },
  { href: "/replay", label: "경기 리플레이" },
  { href: "/model", label: "모델 성능" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav aria-label="주요 화면" className="flex flex-wrap gap-1 text-sm">
      {LINKS.map((l) => {
        const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
        return (
          <Link
            key={l.href}
            href={l.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 transition-colors ${
              active ? "bg-raised text-text" : "text-secondary hover:bg-raised/60 hover:text-text"
            }`}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
