import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#FAFBFC',
        surface: '#FFFFFF',
        border: '#EAECF0',
        'text-primary': '#0F172A',
        'text-secondary': '#475467',
        'text-muted': '#98A2B3',
        accent: {
          DEFAULT: '#0EA5E9',
          hover: '#0284C7',
          light: '#E0F2FE',
        },
        water: {
          permanent: '#3B82F6',
          pre: '#60A5FA',
          peak: '#06B6D4',
          flood: '#F97316',
          receded: '#A78BFA',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(16, 24, 40, 0.04)',
        floating: '0 4px 12px rgba(16, 24, 40, 0.08)',
      },
    },
  },
  plugins: [],
};

export default config;
