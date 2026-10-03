import type { ReactNode } from "react";

/** 화면의 기본 블록. 제목은 무엇을 보여 주는지, subtitle은 어떻게 읽는지를 적는다. */
export default function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-border bg-surface p-4 sm:p-5 ${className}`}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div>
            {title && <h2 className="text-base font-semibold">{title}</h2>}
            {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-md border border-critical/50 bg-critical/10 px-3 py-2 text-sm text-secondary">
      <span className="mr-1 font-semibold text-text">⚠ 오류</span>
      {message}
    </p>
  );
}
