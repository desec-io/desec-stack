/* eslint-env node */

/** @type {import('eslint').Linter.Config} */
module.exports = {
  root: true,
  env: {
    browser: true,
    es2024: true,
  },
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  extends: [
    'plugin:vue/essential',
    // 'plugin:vue/strongly-recommended',
    // 'plugin:vue/recommended',
    'plugin:vuetify/base',
    'plugin:import/recommended',
    'plugin:vue-scoped-css/recommended', // vue2
    'eslint:recommended',
  ],
  settings: {
    'import/resolver': {
      alias: {
        map: [['@', './src']],
      },
    },
  },
  rules: {
    'no-console': process.env.NODE_ENV === 'production' ? 'error' : 'off',
    'no-debugger': process.env.NODE_ENV === 'production' ? 'error' : 'off',
    'vue/v-bind-style': 'warn',
    'vue/v-on-style': 'warn',
    'vue/v-slot-style': 'warn',
    'vue/mustache-interpolation-spacing': ['warn', 'always'],
    'vue/no-multi-spaces': 'warn',
    'vue/no-deprecated-filter': 'warn', // Preparation for vue3
    'vue/no-deprecated-v-on-number-modifiers': 'warn', // Preparation for vue3
    'vue/no-deprecated-html-element-is': 'warn', // Preparation for vue3
    'vue-scoped-css/enforce-style-type': 'off',
    'vue-scoped-css/no-deprecated-deep-combinator': 'warn', // Preparation for vue3
    'vue/match-component-file-name': ['error', {'extensions': ['vue'], 'shouldMatchCase': true}],
  },
  ignorePatterns: ['**/src/modules/**/*'],
}
