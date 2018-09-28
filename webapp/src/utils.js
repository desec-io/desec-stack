import axios from 'axios'
import TimeAgo from 'javascript-time-ago'
import en from 'javascript-time-ago/locale/en'
import Vue from 'vue'
import Vuex from 'vuex'

Vue.use(Vuex)

export const store = new Vuex.Store({
  state: {
    authenticated: false,
    token: ''
  },
  mutations: {
    login (state, token) {
      state.authenticated = true
      state.token = token
    },
    logout (state) {
      state.authenticated = false
      state.token = ''
    }
  }
})

export const HTTP = axios.create({
  baseURL: '/api/v1/',
  headers: {
  }
})

export async function logout () {
  try {
    await HTTP.post('auth/token/logout/')
  } catch (e) {
    console.log(e) // TODO improve error handling
  }
  store.commit('logout')
  HTTP.defaults.headers.common['Authorization'] = ''
  sessionStorage.removeItem('token')
}

TimeAgo.locale(en)
export const timeAgo = new TimeAgo()
