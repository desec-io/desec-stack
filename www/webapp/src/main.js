import { createApp } from 'vue'
import App from '@/App.vue'

// Vuetify
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

import "@fontsource/roboto/300.css" /* light */
import "@fontsource/roboto/400.css" /* regular */
import "@fontsource/roboto/400-italic.css" /* regular-italic */
import "@fontsource/roboto/500.css" /* medium */
import "@fontsource/roboto/700.css" /* bold */
import '@mdi/font/css/materialdesignicons.css'

import { createPinia } from "pinia"

import router from '@/router'

const vuetify = createVuetify({
  components,
  directives,
})

const pinia = createPinia()

createApp(App)
.use(vuetify)
.use(pinia)
.use(router)
.mount('#app')
