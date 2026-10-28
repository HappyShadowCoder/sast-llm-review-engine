/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ground: "var(--dp-color-ground)",
        "ground-muted": "var(--dp-color-ground-muted)",
        panel: "var(--dp-color-panel)",
        ink: "var(--dp-color-ink)",
        "ink-secondary": "var(--dp-color-ink-secondary)",
        rule: "var(--dp-color-rule)",
        accent: {
          DEFAULT: "var(--dp-color-accent)",
          hover: "#063ec0",
          pressed: "#0534a0",
        },
        field: "var(--dp-color-field)",
        "on-field": "var(--dp-color-on-field)",
        "on-field-secondary": "var(--dp-color-on-field-secondary)",
      },
      fontFamily: {
        display: ['"Host Grotesk"', "sans-serif"],
        sans: ['"Instrument Sans"', "sans-serif"],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      borderRadius: {
        panel: "var(--dp-radius-panel)",
      },
      boxShadow: {
        card: "0 1px 3px rgba(22, 25, 31, 0.05), 0 4px 12px rgba(22, 25, 31, 0.04)",
        lifted: "0 4px 12px rgba(22, 25, 31, 0.08), 0 1px 3px rgba(22, 25, 31, 0.04)",
      },
      transitionDuration: {
        interaction: "var(--dp-motion-interaction)",
      },
      transitionTimingFunction: {
        standard: "var(--dp-motion-easing)",
      },
    },
  },
  plugins: [],
};

