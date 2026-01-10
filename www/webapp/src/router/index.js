import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '@/views/HomePage.vue'
import {HTTP} from '@/utils';
import {useUserStore} from "@/store/user";

const lazy = (loader) => () => loader().catch((error) => {
  const message = error?.message || '';
  if (
    message.includes('Failed to fetch dynamically imported module') ||
    message.includes('Importing a module script failed') ||
    message.includes('error loading dynamically imported module')
  ) {
    window.location.reload();
  }
  throw error;
});

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomePage
  },
  {
    path: '/signup/:email?',
    name: 'signup',
    component: lazy(() => import('@/views/SignUp.vue')),
  },
  {
    path: '/custom-setup/:domain',
    name: 'customSetup',
    component: lazy(() => import('@/views/DomainSetupPage.vue')),
    props: true,
  },
  {
    path: '/dyn-setup/:domain',
    alias: '/dynsetup/:domain',
    name: 'dynSetup',
    component: lazy(() => import('@/views/DynSetup.vue')),
  },
  {
    path: '/welcome/:domain?',
    name: 'welcome',
    component: lazy(() => import('@/views/WelcomePage.vue')),
  },
  {
    path: '/docs',
    name: 'docs',
    beforeEnter() { location.href = 'https://desec.readthedocs.io/' },
  },
  {
    path: '/talk',
    name: 'talk',
    beforeEnter() { location.href = 'https://talk.desec.io/' },
  },
  {
    path: '/confirm/:action/:code',
    name: 'confirmation',
    component: lazy(() => import('@/views/ConfirmationPage.vue'))
  },
  {
    path: '/reset-password/:email?',
    name: 'reset-password',
    component: lazy(() => import('@/views/ResetPassword.vue')),
  },
  {
    path: '/totp/',
    name: 'totp',
    component: lazy(() => import('@/views/CrudListTOTP.vue')),
    meta: {guest: false},
  },
  {
    path: '/totp-verify/',
    name: 'TOTPVerify',
    component: lazy(() => import('@/views/Console/TOTPVerifyDialog.vue')),
    props: (route) => ({...route.params}),
  },
  {
    path: '/mfa/',
    name: 'mfa',
    component: lazy(() => import('@/views/MFA.vue')),
    meta: {guest: false},
  },
  {
    path: '/change-email/:email?',
    name: 'change-email',
    component: lazy(() => import('@/views/ChangeEmail.vue')),
    meta: {guest: false},
  },
  {
    path: '/delete-account/',
    name: 'delete-account',
    component: lazy(() => import('@/views/DeleteAccount.vue')),
    meta: {guest: false},
  },
  {
    path: '/donate/',
    name: 'donate',
    component: lazy(() => import('@/views/DonatePage.vue')),
  },
  {
    path: '/roadmap',
    name: 'roadmap',
    beforeEnter() { location.href = 'https://github.com/desec-io/desec-stack/milestones?direction=asc&sort=title&state=open' },
  },
  {
    path: '/impressum/',
    name: 'impressum',
    component: lazy(() => import('@/views/ImpressumPage.vue')),
  },
  {
    path: '/privacy-policy/',
    name: 'privacy-policy',
    component: lazy(() => import('@/views/PrivacyPolicy.vue')),
  },
  {
    path: '/terms/',
    name: 'terms',
    component: lazy(() => import('@/views/TermsPage.vue')),
  },
  {
    path: '/about/',
    name: 'about',
    component: lazy(() => import('@/views/AboutPage.vue')),
  },
  {
    path: '/login',
    name: 'login',
    component: lazy(() => import('@/views/LoginPage.vue')),
  },
  {
    path: '/tokens',
    name: 'tokens',
    component: lazy(() => import('@/views/CrudListToken.vue')),
    meta: {guest: false},
  },
  {
    path: '/domains',
    name: 'domains',
    component: lazy(() => import('@/views/CrudListDomain.vue')),
    meta: {guest: false},
  },
  {
    path: '/domains/:domain',
    name: 'domain',
    component: lazy(() => import('@/views/CrudListRecord.vue')),
    meta: {guest: false},
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
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
    HTTP.defaults.headers.Authorization = 'Token ' + token.token;
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
