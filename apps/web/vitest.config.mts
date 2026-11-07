import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    globals: true,
    include: ['**/*.test.ts', '**/*.test.tsx'],
    exclude: ['node_modules/**', '.next/**', 'tests/**'],
    coverage: {
      provider: 'v8',
      // Report untested files too, matching what SonarQube counts as new code.
      include: ['components/**', 'lib/**', 'hooks/**', 'types/**', 'proxy.ts'],
      reporter: ['text', 'json', 'html', ['lcov', { projectRoot: path.resolve(__dirname, '../..') }]],
      exclude: [
        'node_modules/**',
        'components/ui/**', // Exclude shadcn/ui components as per request
        '.next/**',
        '**/*.config.*',
        'playwright.config.ts',
        'tests/**', // Exclude E2E tests from unit test coverage
      ],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './'),
    },
  },
})
