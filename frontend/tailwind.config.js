/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // OCG游戏王主题 - 蓝色系
        ocg: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        // DM数码宝贝主题 - 紫色系
        dm: {
          50: '#faf5ff',
          100: '#f3e8ff',
          200: '#e9d5ff',
          300: '#d8b4fe',
          400: '#c084fc',
          500: '#a855f7',
          600: '#9333ea',
          700: '#7c3aed',
          800: '#6b21a8',
          900: '#581c87',
          950: '#3b0764',
        },
        // DM点缀色 - 橙色/金色
        'dm-gold': {
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
        },
      },
      backgroundImage: {
        // DM深色背景渐变
        'dm-gradient': 'linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e1b4b 100%)',
        'dm-gradient-light': 'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)',
        // OCG蓝色渐变
        'ocg-gradient': 'linear-gradient(135deg, #1e3a8a 0%, #2563eb 50%, #1e3a8a 100%)',
        // 能量发光效果
        'energy-glow': 'radial-gradient(ellipse at center, rgba(168, 85, 247, 0.3) 0%, transparent 70%)',
      },
      boxShadow: {
        'dm-glow': '0 0 20px rgba(168, 85, 247, 0.3)',
        'dm-glow-strong': '0 0 30px rgba(168, 85, 247, 0.5)',
        'ocg-glow': '0 0 20px rgba(59, 130, 246, 0.3)',
      },
      animation: {
        'glow-pulse': 'glow 2s ease-in-out infinite',
        'float': 'float 3s ease-in-out infinite',
      },
      keyframes: {
        glow: {
          '0%, 100%': { filter: 'drop-shadow(0 0 4px rgba(168, 85, 247, 0.4))' },
          '50%': { filter: 'drop-shadow(0 0 12px rgba(168, 85, 247, 0.8))' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
      },
    },
  },
  plugins: [],
}