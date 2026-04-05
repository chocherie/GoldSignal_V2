import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiPort = env.VITE_API_PORT || "8000";
  const target = `http://127.0.0.1:${apiPort}`;
  // Walk-forward JSON is large and the API can take 30–60s+; default proxy timeouts show as empty wf / ECONNRESET.
  const apiProxy = {
    target,
    changeOrigin: true,
    timeout: 300_000,
    proxyTimeout: 300_000,
  };

  return {
    plugins: [react()],
    server: {
      // Bind IPv4 so http://127.0.0.1:5173 works (Node may otherwise listen on [::1] only).
      host: "127.0.0.1",
      port: 5173,
      proxy: {
        "/health": apiProxy,
        "/api": apiProxy,
      },
    },
    preview: {
      host: "127.0.0.1",
      port: 4173,
      proxy: {
        "/health": apiProxy,
        "/api": apiProxy,
      },
    },
  };
});
