import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        porcelain: "#fafafa",
        surface: "#FFFFFF",
        ink: "#111827",
        muted: "#6B7280",
        line: "#E5E7EB",
        // Brand color is orange — all components use "teal" class names so we
        // swap the values here rather than renaming across every file.
        teal: {
          DEFAULT: "#F97316",
          dark: "#EA580C",
          soft: "#FFF7ED"
        },
        accent: "#F97316",
        success: "#15803D",
        warning: "#B45309",
        danger: "#B91C1C"
      },
      boxShadow: {
        panel: "0 4px 24px -1px rgba(17, 24, 39, 0.07), 0 2px 6px -1px rgba(17, 24, 39, 0.04)"
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif"
        ]
      }
    }
  },
  plugins: []
} satisfies Config;
