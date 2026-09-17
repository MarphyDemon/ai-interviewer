/** @type {import('tailwindcss').Config} */
// primary / accent 色板走 CSS 变量（定义在 src/style.css），以支持运行时主色调切换。
// 变量为 rgb 三元组，配合 <alpha-value> 保留 /30 这类透明度写法。
const palette = (name) =>
  [50, 100, 200, 300, 400, 500, 600, 700, 800, 900].reduce((acc, shade) => {
    acc[shade] = `rgb(var(--${name}-${shade}) / <alpha-value>)`
    return acc
  }, {})

export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: palette('primary'),
        accent: palette('accent'),
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.25rem',
        '3xl': '1.75rem',
      },
      boxShadow: {
        soft: '0 2px 8px -2px rgb(var(--primary-600) / 0.08), 0 4px 16px -4px rgb(var(--primary-600) / 0.06)',
        card: '0 4px 24px -8px rgb(var(--primary-600) / 0.12), 0 2px 8px -2px rgb(var(--primary-600) / 0.08)',
        glow: '0 0 32px -8px rgb(var(--accent-500) / 0.45)',
      },
      backgroundImage: {
        'gradient-brand':
          'linear-gradient(135deg, rgb(var(--primary-500)) 0%, rgb(var(--accent-500)) 100%)',
        'gradient-brand-soft':
          'linear-gradient(135deg, rgb(var(--primary-50)) 0%, rgb(var(--accent-50)) 100%)',
        'gradient-text':
          'linear-gradient(120deg, rgb(var(--primary-600)) 0%, rgb(var(--accent-500)) 100%)',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'blob': {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '33%': { transform: 'translate(20px, -30px) scale(1.05)' },
          '66%': { transform: 'translate(-15px, 15px) scale(0.97)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.5s ease-out both',
        'blob': 'blob 12s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
