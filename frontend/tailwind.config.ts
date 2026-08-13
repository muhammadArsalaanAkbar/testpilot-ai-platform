import type { Config } from "tailwindcss";

// Every color/radius/font-size utility below resolves to a CSS custom
// property defined in src/styles/tokens.css — this file has no literal
// color values of its own (UX-001[a]: no ad hoc values outside the token set).
const hsl = (variable: string) => `hsl(var(${variable}) / <alpha-value>)`;

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      fontSize: {
        display: "var(--text-display)",
        heading: "var(--text-heading)",
        subheading: "var(--text-subheading)",
        body: "var(--text-body)",
        caption: "var(--text-caption)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        full: "var(--radius-full)",
      },
      colors: {
        background: hsl("--color-background"),
        foreground: hsl("--color-foreground"),
        card: {
          DEFAULT: hsl("--color-card"),
          foreground: hsl("--color-card-foreground"),
        },
        border: hsl("--color-border"),
        muted: {
          DEFAULT: hsl("--color-muted"),
          foreground: hsl("--color-muted-foreground"),
        },
        primary: {
          DEFAULT: hsl("--color-primary"),
          foreground: hsl("--color-primary-foreground"),
        },
        secondary: {
          DEFAULT: hsl("--color-secondary"),
          foreground: hsl("--color-secondary-foreground"),
        },
        destructive: {
          DEFAULT: hsl("--color-destructive"),
          foreground: hsl("--color-destructive-foreground"),
        },
        ring: hsl("--color-ring"),
        status: {
          passed: hsl("--color-status-passed"),
          "passed-bg": hsl("--color-status-passed-bg"),
          failed: hsl("--color-status-failed"),
          "failed-bg": hsl("--color-status-failed-bg"),
          skipped: hsl("--color-status-skipped"),
          "skipped-bg": hsl("--color-status-skipped-bg"),
          running: hsl("--color-status-running"),
          "running-bg": hsl("--color-status-running-bg"),
          queued: hsl("--color-status-queued"),
          "queued-bg": hsl("--color-status-queued-bg"),
          error: hsl("--color-status-error"),
          "error-bg": hsl("--color-status-error-bg"),
          completed: hsl("--color-status-completed"),
          "completed-bg": hsl("--color-status-completed-bg"),
        },
        severity: {
          minor: hsl("--color-severity-minor"),
          "minor-bg": hsl("--color-severity-minor-bg"),
          major: hsl("--color-severity-major"),
          "major-bg": hsl("--color-severity-major-bg"),
          critical: hsl("--color-severity-critical"),
          "critical-bg": hsl("--color-severity-critical-bg"),
          blocker: hsl("--color-severity-blocker"),
          "blocker-bg": hsl("--color-severity-blocker-bg"),
        },
        priority: {
          low: hsl("--color-priority-low"),
          "low-bg": hsl("--color-priority-low-bg"),
          medium: hsl("--color-priority-medium"),
          "medium-bg": hsl("--color-priority-medium-bg"),
          high: hsl("--color-priority-high"),
          "high-bg": hsl("--color-priority-high-bg"),
          critical: hsl("--color-priority-critical"),
          "critical-bg": hsl("--color-priority-critical-bg"),
        },
      },
    },
  },
  plugins: [],
};

export default config;
