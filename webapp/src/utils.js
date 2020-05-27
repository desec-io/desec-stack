import axios from 'axios';
import TimeAgo from 'javascript-time-ago';
import en from 'javascript-time-ago/locale/en';
import store from './store';

export const HTTP = axios.create({
  baseURL: process.env.VUE_APP_API_BASE_URL,
  headers: {
  },
});

export async function logout() {
  await withWorking(undefined, () => HTTP
      .post('auth/logout/')
      .then(() => {
        store.commit('logout');
        HTTP.defaults.headers.common.Authorization = '';
        sessionStorage.removeItem('token');
      })
  );
}

export async function withWorking(errorHandler, action, ...params) {
  store.commit('working');
  try {
    return await action(...params);
  } catch (e) {
    if (typeof errorHandler == 'undefined') {
      throw e;
    } else {
      errorHandler(e);
    }
  } finally {
    store.commit('working', false);
  }
}

TimeAgo.locale(en);
export const timeAgo = new TimeAgo();
