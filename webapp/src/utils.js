import axios from 'axios';
import store from './store';

export const HTTP = axios.create({
  baseURL: '/api/v1/',
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
