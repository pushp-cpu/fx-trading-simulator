import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: { extend: { colors: { ink: "#0b1220", panel: "#111c2e", line: "#25344a", mint: "#4de2b1" } } },
  plugins: []
};
export default config;
