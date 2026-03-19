/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        nce: {
          dark: "#0a0e1a",
          panel: "#111827",
          border: "#1f2937",
          accent: "#3b82f6",
          green: "#10b981",
          red: "#ef4444",
          yellow: "#f59e0b",
          purple: "#8b5cf6",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};
