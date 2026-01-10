/* eslint-env node */
import {defineConfig} from 'vite'
import {resolve} from 'node:path';
import legacy from '@vitejs/plugin-legacy'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'

export default defineConfig({
    cacheDir: '.vite',
    css: {
        preprocessorOptions: {
            sass: {
                api: 'modern-compiler',
                /** @type {import('sass').Options.silenceDeprecations } */
                silenceDeprecations: ['global-builtin', 'import', 'slash-div'],
            },
        },
    },
    plugins: [
        vue({
            template: {
                transformAssetUrls: {
                    img: ['src'],
                    image: ['xlink:href', 'href'],
                    source: ['src', 'srcset'],
                    video: ['src', 'poster'],
                    audio: ['src'],
                    use: ['xlink:href', 'href'],
                    'v-img': ['src'],
                    'v-video': ['src', 'poster'],
                },
            },
        }),
        vuetify({ autoImport: true }),
        legacy(), // Build for old browser.
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
