import VueRouter from 'vue-router'
import HomePage from '@/views/HomePage.vue'
import {HTTP} from '@/utils';
import {useUserStore} from "@/store/user";

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomePage
  },
  {
    path: '/signup/:email?',
    name: 'signup',
    // route level code-splitting
    // this generates a separate chunk (about.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: () => import(/* webpackChunkName: "signup" */ '@/views/SignUp.vue')
  },
  {
    path: '/custom-setup/:domain',
    name: 'customSetup',
    component: () => import(/* webpackChunkName: "signup" */ '@/views/DomainSetupPage.vue'),
    props: true,
  },
  {
    path: '/dyn-setup/:domain',
    alias: '/dynsetup/:domain',
    name: 'dynSetup',
    component: () => import(/* webpackChunkName: "signup" */ '@/views/DynSetup.vue')
  },
  {
    path: '/welcome/:domain?',
    name: 'welcome',
    component: () => import(/* webpackChunkName: "signup" */ '@/views/WelcomePage.vue'),
  },
  {
    path: 'https://desec.readthedocs.io/',
    name: 'docs',
    beforeEnter(to) { location.href = to.path },
  },
  {
    path: 'https://talk.desec.io/',
    name: 'talk',
    beforeEnter(to) { location.href = to.path },
  },
  {
    path: '/confirm/:action/:code',
    name: 'confirmation',
    component: () => import(/* webpackChunkName: "account" */ '@/views/ConfirmationPage.vue'),
  },
  {
    path: '/reset-password/:email?',
    name: 'reset-password',
    component: () => import(/* webpackChunkName: "account" */ '@/views/ResetPassword.vue')
  },
  {
    path: '/totp/',
    name: 'totp',
    component: () => import(/* webpackChunkName: "account" */ '@/views/CrudListTOTP.vue'),
    meta: {guest: false},
  },
  {
    path: '/totp-verify/',
    name: 'TOTPVerify',
    component: () => import(/* webpackChunkName: "login" */ '@/views/Console/TOTPVerifyDialog.vue'),
    props: (route) => ({...route.params}),
  },
  {
    path: '/mfa/',
    name: 'mfa',
    component: () => import(/* webpackChunkName: "account" */ '@/views/MFA.vue'),
    meta: {guest: false},
  },
  {
    path: '/change-email/:email?',
    name: 'change-email',
    component: () => import(/* webpackChunkName: "account" */ '@/views/ChangeEmail.vue'),
    meta: {guest: false},
  },
  {
    path: '/delete-account/',
    name: 'delete-account',
    component: () => import(/* webpackChunkName: "account" */ '@/views/DeleteAccount.vue'),
    meta: {guest: false},
  },
  {
    path: '/donate/',
    name: 'donate',
    component: () => import(/* webpackChunkName: "extra" */ '@/views/DonatePage.vue'),
  },
  {
    path: 'https://github.com/desec-io/desec-stack/projects?query=is%3Aopen+sort%3Aname-asc&type=classic',
    name: 'roadmap',
    beforeEnter(to) { location.href = to.path },
  },
  {
    path: '/impressum/',
    name: 'impressum',
    component: () => import(/* webpackChunkName: "extra" */ '@/views/ImpressumPage.vue'),
  },
  {
    path: '/privacy-policy/',
    name: 'privacy-policy',
    component: () => import(/* webpackChunkName: "extra" */ '@/views/PrivacyPolicy.vue')
  },
  {
    path: '/terms/',
    name: 'terms',
    component: () => import(/* webpackChunkName: "extra" */ '@/views/TermsPage.vue'),
  },
  {
    path: '/about/',
    name: 'about',
    component: () => import(/* webpackChunkName: "extra" */ '@/views/AboutPage.vue'),
  },
  {
    path: '/login',
    name: 'login',
    component: () => import(/* webpackChunkName: "login" */ '@/views/LoginPage.vue'),
  },
  {
    path: '/tokens',
    name: 'tokens',
    component: () => import(/* webpackChunkName: "gui" */ '@/views/CrudListToken.vue'),
    meta: {guest: false},
  },
  {
    path: '/domains',
    name: 'domains',
    component: () => import(/* webpackChunkName: "gui" */ '@/views/CrudListDomain.vue'),
    meta: {guest: false},
  },
  {
    path: '/domains/:domain',
    name: 'domain',
    component: () => import(/* webpackChunkName: "gui" */ '@/views/CrudListRecord.vue'),
    meta: {guest: false},
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

router.beforeEach((to, from, next) => {
  // see if there are credentials in the session store that we don't know of
  let recovered = false;
  const user = useUserStore();
  if (sessionStorage.getItem('token') && !user.authenticated) {
    const token = JSON.parse(sessionStorage.getItem('token'));
    HTTP.defaults.headers.common['Authorization'] = 'Token ' + token.token;
    user.login(token);
    recovered = true
  }

  if (to.matched.some(record => 'guest' in record.meta && record.meta.guest === false)) {
    // this route requires auth, check if logged in
    // if not, redirect to login page.
    if (!user.authenticated) {
      next({
        name: 'login',
        query: { redirect: to.fullPath }
      })
    } else {
      next()
    }
  } else {
    if (user.authenticated) {
      // Log in state was present, but not needed for the current page
      if (recovered && to.name === 'home') {
        // User restored a previous session. If navigation to home, divert to home page for authorized users
        next({name: 'domains'})
      }
    }
    next() // make sure to always call next()!
  }
});

export default router
