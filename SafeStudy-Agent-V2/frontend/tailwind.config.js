/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)", surface: "var(--surface)", line: "var(--line)",
        ink: "var(--ink)", mute: "var(--mute)", brand: "var(--brand)", brandsoft: "var(--brand-soft)",
        ok: "var(--ok)", warn: "var(--warn)", bad: "var(--bad)",
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "ui-sans-serif", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
