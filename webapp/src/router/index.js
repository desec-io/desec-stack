import Vue from 'vue'
import Router from 'vue-router'
import SignUp from '@/components/SignUp'
import LogIn from '@/components/LogIn'
import Reset from '@/components/Reset'
import Authenticated from '@/components/authenticated/Authenticated'
import DomainList from '@/components/authenticated/DomainList/App'
import Domain from '@/components/authenticated/Domain/App'

Vue.use(Router)

export default new Router({
  mode: 'history',
  base: '/webapp/',
  routes: [
    {
      path: '/signup',
      name: 'SignUp',
      component: SignUp
    },
    {
      path: '/',
      name: 'LogIn',
      component: LogIn
    },
    {
      path: '/reset/:uid/:token',
      name: 'Reset',
      component: Reset
    },
    {
      path: '/auth',
      name: 'Authenticated',
      component: Authenticated,
      children: [
        { path: 'domains', name: 'DomainList', component: DomainList },
        { path: 'domains/:name', name: 'Domain', component: Domain }
      ]
    }
  ]
})
