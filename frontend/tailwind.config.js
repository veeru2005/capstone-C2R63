/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Utendo', 'sans-serif'],
        mono: ['Utendo', 'sans-serif'],
        serif: ['Utendo', 'sans-serif'],
      },
      colors: {
        finops: {
          bg: "#121214",           // Deep matte dark background
          sidebar: "#0f0f11",      // Sidebar background
          card: "#1a1a1e",         // Card and container background
          cardHover: "#222228",    // Card hover state
          border: "#28282e",       // Subtle border color
          borderInput: "#34343d",  // Dropdown / input border
          input: "#161619",        // Dropdown select background
          blue: "#2563eb",         // FinOps primary active blue
          blueActive: "#1d4ed8",
          purple: "#8b5cf6",
          emerald: "#10b981",
          teal: "#14b8a6",
          amber: "#f59e0b",
          rose: "#ef4444",
          text: "#f4f4f5",
          muted: "#71717a",
          mutedLight: "#a1a1aa",
        },
      },
    },
  },
  plugins: [],
};
