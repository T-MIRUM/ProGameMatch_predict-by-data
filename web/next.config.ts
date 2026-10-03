import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // standalone: 실행에 필요한 파일만 .next/standalone에 모아 Docker 이미지를 작게 유지한다
  output: "standalone",
  // Next 16은 dev 서버 시작 시 AGENTS.md / CLAUDE.md를 web/에 자동 생성한다.
  // 팀원마다 추적되지 않는 파일이 생기지 않도록 끈다.
  agentRules: false,
};

export default nextConfig;
