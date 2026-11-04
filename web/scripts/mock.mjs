// Runs a Next command against constructed data, on any shell: `npm run dev:mock`.
import { spawn } from "node:child_process";

const child = spawn("npx", ["next", ...process.argv.slice(2)], {
  stdio: "inherit",
  shell: true,
  env: { ...process.env, NEXT_PUBLIC_DFU_MOCK: "1" },
});
child.on("exit", (code) => process.exit(code ?? 1));
