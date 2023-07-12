import Vue from 'vue'
import App from '@/App.vue'
import router from '@/router'
import vuetify from '@/plugins/vuetify'
import VueRouter from 'vue-router'
import Vuelidate from 'vuelidate'
import "@fontsource/roboto/300.css" /* light */
import "@fontsource/roboto/400.css" /* regular */
import "@fontsource/roboto/400-italic.css" /* regular-italic */
import "@fontsource/roboto/500.css" /* medium */
import "@fontsource/roboto/700.css" /* bold */
import '@mdi/font/css/materialdesignicons.css'
import {createPinia, PiniaVuePlugin} from "pinia";


Vue.config.productionTip = false
Vue.use(Vuelidate)
// `Pinia` replaces `vuex` as store.
Vue.use(PiniaVuePlugin)
const pinia = createPinia()
// Must be after `pinia` initialisation to be accessible.
Vue.use(VueRouter)

new Vue({
  router,
  pinia,
  vuetify,
  render: h => h(App)
}).$mount('#app')
