import axios from 'axios';
import store from './store';

export const HTTP = axios.create({
  baseURL: '/api/v1/',
  headers: {
  },
});

function clearToken() {
  store.commit('logout');
  HTTP.defaults.headers.common.Authorization = '';
  sessionStorage.removeItem('token');
}

export async function logout() {
  await withWorking(undefined, () => HTTP
      .post('auth/logout/')
      .then(clearToken)
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

function _digestError(error) {
  if (error.response) {
    // The request was made and the server responded with a status code
    // that falls out of the range of 2xx
    if (error.response.status < 500) {
      // 3xx or 4xx
      if (error.response.status === 401) {
        if (sessionStorage.getItem('token')) {
          setTimeout(() => clearToken());
          return ['Session expired. Please login again.']
        } else {
          return ['You are not logged in.'];
        }
      } else if (error.response.status === 413) {
        return ['Too much data. Try to reduce the length of your inputs.'];
      } else if ('data' in error.response) {
        let data = error.response.data;
        if (typeof data === 'object') {
          if ('detail' in data) {
            return [data.detail];
          } else if ('non_field_errors' in data) {
            return data.non_field_errors;
          } else {
            return data;
          }
        } else {
          return [data];
        }
      } else {
        return ["Server returned an empty response."];
      }
    } else {
      // 5xx
      if (error.response.status === 500) {
        return ['Something went wrong at the server, but we currently do not know why. The support was already notified.'];
      } else {
        return ['Something went wrong at the server, but we currently do not know why. Please try again later, and contact us if the problem persists for a longer time.'];
      }
    }
  } else if (error.request) {
    return [`Cannot contact servers at ${HTTP.baseURL ? HTTP.baseURL : window.location.hostname}. Are you offline?`];
  } else {
    return [error.message];
  }
}

export function digestError(error) {
  let e = _digestError(error);
  if (e.constructor === Array) {
    return {undefined: e};
  } else {
    return e;
  }
}
