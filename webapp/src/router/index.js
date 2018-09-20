import Vue from 'vue'
import Router from 'vue-router'
import SignUp from '@/components/guest/SignUp'
import Login from '@/components/guest/Login'
import Reset from '@/components/guest/Reset'
import DomainList from '@/components/DomainList'
import Domain from '@/components/Domain'
import {logout, store} from '@/utils'

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
    // Log out if logged in unnecessarily
    if (store.state.authenticated) {
      logout()
    }
    next() // make sure to always call next()!
  }
})

export default router
