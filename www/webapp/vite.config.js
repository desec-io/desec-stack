/* eslint-env node */
import {defineConfig} from 'vite'
import {resolve} from 'node:path';
import Components from 'unplugin-vue-components/vite'
import {VuetifyResolver} from 'unplugin-vue-components/resolvers'
import vue from '@vitejs/plugin-vue2'

export default defineConfig({
    define: {
        'process.env.BUILD': '"web"' // fix for vuelidate@0.7.7
    },
    plugins: [
        vue(),
        Components({
            resolvers: [VuetifyResolver()],
        }),
    ],
    server: {
        port: 8080,
    },
    resolve: {
        alias: [{
            find: '@', replacement: resolve(__dirname, 'src')
        }],
        extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json', '.vue'],
    },
})
