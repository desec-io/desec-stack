import js from '@eslint/js';
import globals from 'globals';
import pluginImport from 'eslint-plugin-import';
import pluginVue from 'eslint-plugin-vue';
import pluginVueScopedCss from 'eslint-plugin-vue-scoped-css';
import pluginVuetify from 'eslint-plugin-vuetify';

export default [
  {
    ignores: ['**/src/modules/**/*', 'dist/**', '.vite/**'],
  },
  ...pluginVue.configs['flat/essential'],
  // ...pluginVue.configs['flat/strongly-recommended'],
  // ...pluginVue.configs['flat/recommended'],
  ...pluginVuetify.configs['flat/base'],
  pluginImport.flatConfigs.recommended,
  ...pluginVueScopedCss.configs['flat/recommended'],
  js.configs.recommended,
  {
    files: ['**/*.{js,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: globals.browser,
    },
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
      'vue-scoped-css/enforce-style-type': 'off',
      'vue/match-component-file-name': ['error', {'extensions': ['vue'], 'shouldMatchCase': true}],
    },
  },
];
