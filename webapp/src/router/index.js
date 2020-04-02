import Vue from 'vue'
import VueRouter from 'vue-router'
import Home from '../views/Home.vue'

Vue.use(VueRouter)

const routes = [
  {
    path: '/',
    name: 'home',
    component: Home
  },
  {
    path: '/signup/:email?',
    name: 'signup',
    // route level code-splitting
    // this generates a separate chunk (about.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: () => import(/* webpackChunkName: "signup" */ '../views/SignUp.vue')
  },
  {
    path: '/dynsetup/:domain',
    name: 'dynsetup',
    component: () => import(/* webpackChunkName: "signup" */ '../views/DynSetup.vue')
  },
  {
    path: '/welcome/:domain?',
    name: 'welcome',
    component: () => import(/* webpackChunkName: "signup" */ '../views/Welcome.vue')
  },
  {
    path: '//desec.readthedocs.io/',
    name: 'docs',
    beforeEnter(to) { location.href = to.path },
  },
  {
    path: '//talk.desec.io/',
    name: 'talk',
    beforeEnter(to) { location.href = to.path },
  },
  {
    path: '/confirm/:action/:code',
    name: 'confirmation',
    component: () => import(/* webpackChunkName: "signup" */ '../views/Confirmation.vue')
  },
  {
    path: '/reset-password/:email?',
    name: 'reset-password',
    component: () => import(/* webpackChunkName: "signup" */ '../views/ResetPassword.vue')
  },
  {
    path: '/donate/',
    name: 'donate',
    component: () => import('../views/Donate.vue')
  },
  {
    path: '/impressum/',
    name: 'impressum',
    component: () => import('../views/Impressum.vue')
  },
  {
    path: '/privacy-policy/',
    name: 'privacy-policy',
    component: () => import('../views/PrivacyPolicy.vue')
  },
  {
    path: '/terms/',
    name: 'terms',
    component: () => import('../views/Terms.vue')
  },
  {
    path: '/about/',
    name: 'about',
    component: () => import('../views/About.vue')
  },
]

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  scrollBehavior (to, from) {
    // Skip if destination full path has query parameters and differs in no other way from previous
    if (from && Object.keys(to.query).length) {
      if (to.fullPath.split('?')[0] == from.fullPath.split('?')[0]) return;
    }
    return { x: 0, y: 0 }
  },
  routes
})

export default router
