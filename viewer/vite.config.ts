import { defineConfig } from "vite";

export default defineConfig(({ command, isPreview }) => ({
  // GitHub Pages のプロジェクトサイト(https://shiwaku.github.io/japan-legal-speed-30kmh-map/)。
  // preview(dist の確認)でも同じ base にしないと assets が見つからず index.html が返る
  base: command === "build" || isPreview ? "/japan-legal-speed-30kmh-map/" : "/",
  server: {
    port: 5175,
    strictPort: true,
    // WSL から /mnt/c を見る構成では inotify が届かないのでポーリングで検知する
    watch: { usePolling: true, interval: 300 },
  },
  // main.ts が最上位 await で背景スタイルを読む
  build: { target: "es2022" },
  define: {
    __BUILD_TIME__: JSON.stringify(new Date().toISOString().replace("T", " ").slice(0, 16) + " UTC"),
  },
}));
