<template>
  <v-app id="inspire">
    <v-navigation-drawer
      v-model="drawer"
      app
      location="right"
      disable-resize-watcher
    >
      <v-list density="compact">
        <v-list-item
          v-for="(item, key) in menu"
          :key="key"
          :to="{name: item.name}"
          :exact="true"
        >
          <template #prepend>
            <v-icon :icon="item.icon" />
          </template>
          <v-list-item-title>
            {{ item.text }}
            <v-icon v-if="item.post_icon" :icon="item.post_icon" :color="item.post_icon_color" size="small" />
          </v-list-item-title>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-app-bar app color="white" :extended="authenticated">
      <v-app-bar-title><router-link :to="{name: 'home'}">
        <v-img
          src="./assets/logo.svg"
          alt="deSEC Logo"
          class="app-logo"
          height="32"
          eager
          contain
        ></v-img>
      </router-link></v-app-bar-title>
      <v-spacer/>
      <div class="d-none d-md-block">
        <span class="mx-2" v-for="(item, key) in menu" :key="key">
          <router-link
            class="text-primary"
            :to="{name: item.name}"
          >{{ item.text }}</router-link>
          <v-icon v-if="item.post_icon" :icon="item.post_icon" :color="item.post_icon_color" class="ml-1" size="small" />
        </span>
      </div>
      <v-btn class="mx-4" color="primary" variant="flat" :to="{name: 'signup', query: $route.query}" v-if="!authenticated">Create Account</v-btn>
      <v-btn class="mx-4 mr-0" color="primary" variant="flat" :to="{name: 'login'}" v-if="!authenticated">Log In</v-btn>
      <v-btn class="mx-4 mr-0" color="primary" variant="outlined" @click="logout" v-if="authenticated">Log Out</v-btn>
      <v-app-bar-nav-icon class="d-md-none" @click.stop="drawer = !drawer" />
      <template #extension v-if="authenticated">
        <div class="d-flex align-center w-100 bg-primary text-white">
          <v-tabs v-model="activeTab" class="flex-grow-1 text-white" bg-color="primary" color="white" slider-color="white" grow>
            <v-tab
              v-for="(item, key) in tabmenu"
              :key="key"
              :value="item.name"
              :to="{name: item.name}"
              class="text-white"
            >
              {{ item.text }}
            </v-tab>
          </v-tabs>
          <v-menu location="bottom">
            <template #activator="{ props }">
              <v-btn
                variant="text"
                color="white"
                class="align-self-center mr-4"
                v-bind="props"
              >
                more
                <v-icon :icon="mdiMenuDown" end />
              </v-btn>
            </template>

            <v-list class="bg-grey-lighten-3">
              <v-list-item
                v-for="(item, key) in tabmenumore"
                :key="key"
                :to="{name: item.name}"
              >
                {{ item.text }}
              </v-list-item>
            </v-list>
          </v-menu>
        </div>
      </template>
    </v-app-bar>

    <v-main>
      <v-banner v-for="alert in user.alerts" :key="alert.id">
        <template #icon>
          <v-icon
            color="warning"
            size="36"
            :icon="alert.icon"
          />
        </template>
        {{ alert.teaser }}
        <template #actions>
          <v-btn
            color="primary"
            variant="flat"
            :href="alert.href"
            v-if="alert.href"
          >
            {{ alert.button || 'More' }}
          </v-btn>
          <v-btn
            color="primary"
            variant="text"
            @click="user.unalert(alert.id)"
          >
            Hide
          </v-btn>
        </template>
      </v-banner>
      <v-progress-linear
              :active="user.working"
              :indeterminate="user.working"
              fixed
              color="secondary"
              style="z-index: 3"
      ></v-progress-linear>
      <router-view/>
    </v-main>
    <v-footer
      class="d-flex flex-column align-stretch pa-0 text-white elevation-12"
    >
      <div class="bg-grey-darken-3 d-sm-flex flex-row justify-space-between pa-4">
        <div class="pa-2">
          <b>deSEC e.V.</b>
        </div>
        <div class="d-sm-flex flex-row align-right py-2">
          <div class="px-2"><a href="https://desec-status.net/">Service Status</a></div>
          <div class="px-2"><a href="https://github.com/desec-io/desec-stack/">Source Code</a></div>
          <div class="px-2"><router-link :to="{name: 'terms'}">Terms of Use</router-link></div>
          <div class="px-2"><router-link :to="{name: 'privacy-policy'}">Privacy Policy (Datenschutzerklärung)</router-link></div>
          <div class="px-2"><router-link :to="{name: 'impressum'}">Legal Notice (Impressum)</router-link></div>
        </div>
      </div>
      <div class="bg-grey-darken-4 d-md-flex flex-row justify-space-between pa-6">
        <div>
          <p>{{ email }}</p>
          <p>
            Möckernstraße 74<br/>
            10965 Berlin<br/>
            Germany
          </p>
        </div>
        <div>
          <p>
            Please <router-link :to="{name: 'donate'}">donate</router-link>!
            <v-icon :icon="mdiHeart" color="red" />
          </p>
          <p>
            European Bank Account:<br>
            IBAN: DE91&nbsp;8306&nbsp;5408&nbsp;0004&nbsp;1580&nbsp;59<br>
            BIC: GENODEF1SLR
          </p>
        </div>
        <div>
          <p>deSEC e.V. is registered as</p>
          <p>VR37525 at AG Berlin (Charlottenburg)</p>
        </div>
        <div>
          <p>Vorstand</p>
          <p class="text-white">
            Nils Wisiol<br/>
            Peter Thomassen<br/>
            Wolfgang Studier<br/>
          </p>
        </div>
      </div>
    </v-footer>
  </v-app>
</template>

<script>
import router from '@/router';
import {logout} from '@/utils';
import {useUserStore} from "@/store/user";
import {
    mdiBookOpenPageVariant,
    mdiForumOutline,
    mdiGiftOutline,
    mdiHeart,
    mdiHome,
    mdiLockReset,
    mdiMenuDown,
    mdiRoadVariant,
    mdiUmbrella
} from "@mdi/js";

export default {
  name: 'App',
  computed: {
    authenticated() {
      return this.user?.authenticated;
    },
    menu: () => {
      const user = useUserStore();
      const menu_perma = {
        'home': {
          'name': 'home',
          'icon': mdiHome,
          'text': 'Home',
        },
        'docs': {
          'name': 'docs',
          'icon': mdiBookOpenPageVariant,
          'text': 'Docs',
        },
        'roadmap': {
          'name': 'roadmap',
          'icon': mdiRoadVariant,
          'text': 'Roadmap',
        },
        'talk': {
          'name': 'talk',
          'icon': mdiForumOutline,
          'text': 'Talk',
        },
        'donate': {
          'name': 'donate',
          'icon': mdiGiftOutline,
          'text': 'Donate',
          'post_icon': mdiHeart,
          'post_icon_color': 'red',
        },
        'about': {
          'name': 'about',
          'icon': mdiUmbrella,
          'text': 'About',
        },
      };
      let menu_opt = {};
      if(!user.authenticated) {
        menu_opt = {
          'reset-password': {
            'name': 'reset-password',
            'icon': mdiLockReset,
            'text': 'Reset Account Password',
          },
        };
      }
      return {...menu_perma, ...menu_opt};
    },
  },
  data: () => ({
    user: useUserStore(),
    drawer: false,
    email: import.meta.env.VITE_APP_EMAIL,
    activeTab: null,
    mdiHeart,
    mdiMenuDown,
    tabmenu: {
      'domains': {
        'name': 'domains',
        'text': 'Domain Management',
      },
      'tokens': {
        'name': 'tokens',
        'text': 'Token Management',
      },
    },
    tabmenumore: {
      'totp': {
        'name': 'totp',
        'text': 'Manage 2-Factor Authentication',
      },
      'change-email': {
        'name': 'change-email',
        'text': 'Change Email Address',
      },
      'delete-account': {
        'name': 'delete-account',
        'text': 'Delete Account',
      },
    },
  }),
  watch: {
    $route: {
      immediate: true,
      handler(to) {
        this.activeTab = to?.name ?? null;
      },
    },
  },
  methods: {
    async logout() {
      await logout();
      router.push({name: 'home'});
    }
  }
}
</script>

<style>
.v-application a {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
}
.v-application a:hover,
.v-application a:focus {
  text-decoration: underline;
}
.v-application .bg-grey-darken-3 a,
.v-application .bg-grey-darken-4 a {
  color: rgb(var(--v-theme-secondary));
}
.app-logo {
  width: auto;
}
</style>
