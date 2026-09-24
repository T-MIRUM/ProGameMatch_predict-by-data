import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Propredict — VCT 라운드 승률",
  description: "발로란트 VCT 라운드 시작 시점 상태로 라운드 승리 확률을 예측합니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen flex flex-col antialiased">
        <header className="border-b border-border">
          <div className="mx-auto max-w-6xl px-4 py-3 font-semibold">Propredict</div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>
        {/* 명세 §7: 모든 화면에 공통 고지. 베팅 관련 문구는 어디에도 넣지 않는다. */}
        <footer className="border-t border-border px-4 py-4 text-center text-sm text-muted">
          본 서비스는 교육·포트폴리오 목적이며 Riot Games와 무관합니다.
        </footer>
      </body>
    </html>
  );
}
