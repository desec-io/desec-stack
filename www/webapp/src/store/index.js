import Vue from 'vue'
import Vuex from 'vuex'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    authenticated: false,
    token: {},
    work_count: 0,
    alerts: [],
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
    alert(state, alert) {
      for (const known_alert of state.alerts) {
        if (alert.id === known_alert.id) {
          return;
        }
      }
      state.alerts.push(alert);
    },
    unalert(state, id) {
      let del_idx = undefined;
      for (const [idx, alert] of state.alerts.entries()) {
        if (alert.id === id) {
          del_idx = idx;
          break;
        }
      }
      if (del_idx !== undefined) {
        state.alerts.splice(del_idx, 1);
      }
    },
  },
  getters: {
    working: state => !!state.work_count,
    alerts: state => state.alerts,
  },
  actions: {
  },
  modules: {
  }
})
