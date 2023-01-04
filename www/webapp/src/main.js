import Vue from 'vue'
import App from '@/App.vue'
import router from '@/router'
import store from '@/store'
import vuetify from '@/plugins/vuetify'
import VueClipboard from 'vue-clipboard2'
import Vuelidate from 'vuelidate'
import "@fontsource/roboto/300.css" /* light */
import "@fontsource/roboto/400.css" /* regular */
import "@fontsource/roboto/400-italic.css" /* regular-italic */
import "@fontsource/roboto/500.css" /* medium */
import "@fontsource/roboto/700.css" /* bold */
import '@mdi/font/css/materialdesignicons.css'
import VueTimeago from 'vue-timeago'


Vue.config.productionTip = false
VueClipboard.config.autoSetContainer = true
Vue.use(VueClipboard)
Vue.use(Vuelidate)
Vue.use(VueTimeago, {})

new Vue({
  router,
  store,
  vuetify,
  render: h => h(App)
}).$mount('#app')
