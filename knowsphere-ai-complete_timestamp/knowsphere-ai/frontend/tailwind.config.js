/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#16202B",
        "ink-soft": "#2B394A",
        paper: "#F6F3EC",
        "paper-dim": "#EDE9DD",
        rule: "#D8D2C2",
        gold: "#B8892B",
        "gold-soft": "#E9DCBE",
        teal: "#2F5F58",
        danger: "#A23B3B",
      },
      fontFamily: {
        display: ["Lora", "serif"],
        sans: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
