import Vue from 'vue'
import Vuex from 'vuex'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    authenticated: false,
    token: {},
    work_count: 0,
  },
  mutations: {
    login(state, token) {
      state.authenticated = true;
      state.token = token;
    },
    logout(state) {
      state.authenticated = false;
      state.token = {};
    },
    working(state, working = true) {
      state.work_count += working ? 1 : -1;
    },
  },
  getters: {
    working: state => !!state.work_count
  },
  actions: {
  },
  modules: {
  }
})
