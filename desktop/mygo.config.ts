import { defineConfig } from "mygo-cli";

export default defineConfig({
  name: "Humanaize2-Desktop",
  identifier: "com.humanaize.desktop",
  version: "2.5.0",
  // The frontend is a thin shell: the real UI is the Humanaize2 web dashboard
  // served by the Python backend. We still keep a frontend so `mygo build`
  // can embed a fallback page, but the window loads the live dashboard URL.
  devUrl: "http://localhost:5173",
  devCommand: "bun run dev:web",
  buildCommand: "bun run build:web",
  frontendDist: "dist",
  bindings: "src/mygo.ts",
  out: "build",
});
