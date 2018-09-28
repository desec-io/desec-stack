import Vue from 'vue'
import Router from 'vue-router'
import SignUp from '@/components/guest/SignUp'
import Login from '@/components/guest/Login'
import Reset from '@/components/guest/Reset'
import DomainList from '@/components/DomainList'
import Domain from '@/components/Domain'
import {logout, store, HTTP} from '@/utils'

Vue.use(Router)

const router = new Router({
  mode: 'history',
  base: '/webapp/',
  routes: [
    {
      path: '/',
      redirect: { name: 'DomainList' }
    },
    {
      path: '/signup',
      name: 'SignUp',
      component: SignUp,
      meta: { guest: true }
    },
    {
      path: '/login',
      name: 'Login',
      component: Login,
      meta: { guest: true }
    },
    {
      path: '/reset/:uid/:token',
      name: 'Reset',
      component: Reset,
      meta: { guest: true }
    },
    {
      path: '/domains',
      name: 'DomainList',
      component: DomainList
    },
    {
      path: '/domains/:name',
      name: 'Domain',
      component: Domain
    }
  ]
})

router.beforeEach((to, from, next) => {
  // see if there are credentials in the session store that we don't know of
  let recovered = false
  if (sessionStorage.getItem('token') && !store.state.authenticated) {
    HTTP.defaults.headers.common['Authorization'] = 'Token ' + sessionStorage.getItem('token')
    store.commit('login', sessionStorage.getItem('token'))
    recovered = true
  }

  if (!to.matched.every(record => record.meta.guest)) {
    // this route requires auth, check if logged in
    // if not, redirect to login page.
    if (!store.state.authenticated) {
      next({
        name: 'Login',
        query: { redirect: to.fullPath }
      })
    } else {
      next()
    }
  } else {
    if (store.state.authenticated) {
      // Log in state was present, but not needed for the current page
      if (recovered) {
        // user restored a previous session
        // redirect her to the home page for authorized users
        next({
          name: 'DomainList'
        })
      } else {
        // use nagivated to a page that doesn't require auth
        // from within the current session (without session restore)
        // to bias on the safe side we log out
        logout()
      }
    }
    next() // make sure to always call next()!
  }
})

export default router
