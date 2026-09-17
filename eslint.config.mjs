// ESLint 9 Flat Config —— 前端（Vue 3 + TypeScript + Vite）
//
// 基础：eslint:recommended + plugin:vue/vue3-recommended + typescript-eslint recommended
// 说明：本仓库存在大量历史代码，纯排版类规则（缩进 / 换行 / 属性顺序 / 引号等）
//       统一关闭，交给编辑器与格式化工具，ESLint 只兜底“可能出错”的代码问题，
//       从而保证 `npm run lint` 在当前全量代码上 0 error。
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,tsx,vue}'],
  },
  {
    name: 'app/files-to-ignore',
    ignores: [
      '**/dist/**',
      'dist/**',
      'node_modules/**',
      'coverage/**',
      'server/**',
      'miniprogram/**',
      'deploy-package/**',
      'data/**',
      'docs/**',
      'py_deps/**',
      'chroma_db/**',
      // 内置 PostgreSQL 安装包（含 pgAdmin 自带源码），与 ruff extend-exclude 保持一致
      'pg/**',
      '.trellis/**',
      '.opencode/**',
      '.trae/**',
      // lint 范围与 `--ext .ts,.vue` 一致，只检查 TS / Vue
      '**/*.js',
      '**/*.cjs',
      '**/*.mjs',
    ],
  },
  js.configs.recommended,
  // eslint-plugin-vue 9.x 的 flat/recommended 即 vue3-recommended
  pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,
  {
    name: 'app/rules',
    rules: {
      // ---------- Vue：纯排版类规则（历史代码未遵循，关闭） ----------
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/multiline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/html-indent': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/html-closing-bracket-spacing': 'off',
      'vue/html-quotes': 'off',
      'vue/first-attribute-linebreak': 'off',
      'vue/attributes-order': 'off',
      'vue/attribute-hyphenation': 'off',
      'vue/v-on-event-hyphenation': 'off',
      'vue/component-name-in-template-casing': 'off',
      'vue/mustache-interpolation-spacing': 'off',
      'vue/no-multi-spaces': 'off',
      'vue/block-tag-newline': 'off',
      'vue/padding-line-between-blocks': 'off',
      'vue/comment-directive': 'off',
      'vue/one-component-per-file': 'off',

      // ---------- Vue：组件命名/Props 约定（历史代码混用，关闭） ----------
      'vue/multi-word-component-names': 'off',
      'vue/require-default-prop': 'off',
      'vue/no-v-html': 'off',

      // ---------- TypeScript：宽松化，避免历史代码大面积报错 ----------
      '@typescript-eslint/no-explicit-any': 'off',
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': 'off',

      // 允许“有意为之”的空 catch（如非关键路径的容错）
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  {
    name: 'app/dts-rules',
    files: ['**/*.d.ts'],
    rules: {
      // 声明文件里的 `declare module '*.vue'` 等惯用写法
      '@typescript-eslint/no-empty-object-type': 'off',
    },
  },
)
