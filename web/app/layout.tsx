import type { Metadata } from "next";
import Nav from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Propredict — VCT 라운드 승률",
  description: "발로란트 VCT 라운드 시작 시점 상태로 라운드 승리 확률을 예측하고, 그 확률이 얼마나 믿을 만한지 보여 줍니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="flex min-h-screen flex-col antialiased">
        <header className="border-b border-border">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <span className="font-semibold">
              Propredict <span className="font-normal text-muted">· VCT 라운드 승률</span>
            </span>
            <Nav />
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>
        {/* 명세 §7: 모든 화면 공통 고지. 베팅을 권유하는 문구는 어디에도 넣지 않는다. */}
        <footer className="border-t border-border px-4 py-4 text-center text-xs text-muted">
          본 서비스는 교육·포트폴리오 목적이며 Riot Games와 무관합니다.
        </footer>
      </body>
    </html>
  );
}
