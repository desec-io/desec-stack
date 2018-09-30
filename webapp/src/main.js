import 'material-design-icons-iconfont/dist/material-design-icons.css' // Ensure you are using css-loader

// The Vue build version to load with the `import` command
// (runtime-only or standalone) has been set in webpack.base.conf with an alias.
import Vue from 'vue'
import App from './App'
import router from './router'

import Vuetify from 'vuetify'
import 'vuetify/dist/vuetify.min.css' // Ensure you are using css-loader
import VueClipboard from 'vue-clipboard2'
import {store} from './utils'
import Validations from 'vuelidate'

Vue.use(Vuetify)
Vue.use(Validations)
Vue.use(VueClipboard)

Vue.config.productionTip = false

function mergeValidationsFirstOrder (toVal, fromVal) {
  if (!toVal) return fromVal
  if (!fromVal) return toVal

  const toObj = typeof toVal === 'function' ? toVal.call(this) : toVal
  const fromObj = typeof fromVal === 'function' ? fromVal.call(this) : fromVal

  const fields = new Set([...Object.keys(toObj), ...Object.keys(fromObj)])

  const mergedObj = {}
  fields.forEach(field => {
    mergedObj[field] = Object.assign({}, toObj[field], fromObj[field])
  })

  return mergedObj
}

Vue.config.optionMergeStrategies.validations =
  Vue.config.optionMergeStrategies.validations || mergeValidationsFirstOrder

/* eslint-disable no-new */
new Vue({
  el: '#app',
  router,
  components: { App },
  template: '<App/>',
  store: store
})
