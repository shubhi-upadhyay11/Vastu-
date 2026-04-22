/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",              // ✅ include index.html
    "./src/**/*.{js,ts,jsx,tsx}" // ✅ include all source files
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
