import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // standalone: 실행에 필요한 파일만 .next/standalone에 모아 Docker 이미지를 작게 유지한다
  output: "standalone",
};

export default nextConfig;
