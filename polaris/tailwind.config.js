/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // 종이(실행 세계)
        paper: 'var(--paper)',
        'paper-raised': 'var(--paper-raised)',
        ink: 'var(--ink)',
        'ink-soft': 'var(--ink-soft)',
        line: 'var(--line)',
        // 밤하늘(비전 세계)
        night: 'var(--night)',
        'night-raised': 'var(--night-raised)',
        starlight: 'var(--starlight)',
        // 단 하나의 액션 색
        dawn: 'var(--dawn)',
        'dawn-soft': 'var(--dawn-soft)',
        // 삶의 영역 6색
        'area-career': 'var(--area-career)',
        'area-health': 'var(--area-health)',
        'area-relation': 'var(--area-relation)',
        'area-money': 'var(--area-money)',
        'area-growth': 'var(--area-growth)',
        'area-life': 'var(--area-life)',
      },
      fontFamily: {
        display: ['Gowun Batang', 'Noto Serif KR', 'serif'],
        body: ['Pretendard Variable', 'Pretendard', '-apple-system', 'sans-serif'],
        num: ['IBM Plex Mono', 'monospace'],
      },
      fontSize: {
        xs: '12px',
        sm: '14px',
        base: '16px',
        lg: '20px',
        xl: '25px',
        '2xl': '31px',
      },
      borderRadius: {
        card: '14px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(28,39,51,.06)',
      },
      transitionTimingFunction: {
        'ease-out-dawn': 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      transitionDuration: {
        fast: '180ms',
        base: '320ms',
        story: '600ms',
      },
    },
  },
  plugins: [],
}
