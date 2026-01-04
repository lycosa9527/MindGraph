/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#409eff',
          light: '#66b1ff',
          dark: '#337ecc',
          50: '#ecf5ff',
          100: '#d9ecff',
          200: '#b3d8ff',
          300: '#8cc5ff',
          400: '#66b1ff',
          500: '#409eff',
          600: '#337ecc',
          700: '#265f99',
          800: '#1a3f66',
          900: '#0d2033',
        },
        success: '#67c23a',
        warning: '#e6a23c',
        danger: '#f56c6c',
        info: '#909399',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  corePlugins: {
    preflight: false,
  },
  plugins: [],
}
