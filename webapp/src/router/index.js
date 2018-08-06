import Vue from 'vue'
import Router from 'vue-router'
import SignUp from '@/components/SignUp'
import LogIn from '@/components/LogIn'
import DomainList from '@/components/DomainList'

Vue.use(Router)

export default new Router({
  routes: [
    {
      path: '/',
      name: 'SignUp',
      component: SignUp
    },
    {
      path: '/login',
      name: 'LogIn',
      component: LogIn
    },
    {
      path: '/domains',
      name: 'DomainList',
      component: DomainList
    }
  ]
})
