<template>
  <v-app id="inspire">
    <v-navigation-drawer
            v-model="drawer"
            app
            right
            disable-resize-watcher
    >
      <v-list dense>
        <v-list-item
                v-for="(item, key) in menu"
                :key="key"
                link
                :to="{name: item.name}"
                :exact="true">
          <v-list-item-action>
            <v-icon>{{ item.icon }}</v-icon>
          </v-list-item-action>
          <v-list-item-content>
            <v-list-item-title>
              {{ item.text }}
              <v-icon :color="item.post_icon_color" class="text--darken-2" small v-if="item.post_icon">{{ item.post_icon }}</v-icon>
            </v-list-item-title>
          </v-list-item-content>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-app-bar app class="white">
      <v-toolbar-title><router-link :to="{name: 'home'}">
        <v-img
                src="./assets/logo.svg"
                alt="deSEC Logo"
                eager
                contain
        ></v-img>
      </router-link></v-toolbar-title>
      <v-spacer/>
      <div class="d-none d-md-block">
        <span class="mx-2" v-for="(item, key) in menu" :key="key">
          <router-link
                  class="primary--text text--darken-2"
                  :to="{name: item.name}"
          >{{ item.text }}</router-link>
          <v-icon :color="item.post_icon_color" class="ml-1 text--darken-1" small v-if="item.post_icon">{{ item.post_icon }}</v-icon>
        </span>
      </div>
      <v-btn class="mx-4" color="primary" depressed :to="{name: 'signup', query: $route.query}" v-if="!user.authenticated" aria-label="Create Account">Create Account</v-btn>
      <v-btn class="mx-4 mr-0" color="primary" depressed :to="{name: 'login'}" v-if="!user.authenticated" aria-label="Log In">Log In</v-btn>
      <v-btn class="mx-4 mr-0" color="primary" depressed outlined @click="logout" v-if="user.authenticated" aria-label="Log Out">Log Out</v-btn>
      <v-app-bar-nav-icon class="d-md-none" @click.stop="drawer = !drawer" />
      <template #extension v-if="user.authenticated">
        <v-tabs background-color="primary darken-1" fixed-tabs>
          <v-tab
            v-for="(item, key) in tabmenu"
            :key="key"
            :to="{name: item.name}"
          >
            {{ item.text }}
          </v-tab>
          <v-spacer></v-spacer>
          <v-menu
                  bottom
                  left
          >
            <template #activator="{ on }">
              <v-btn
                      text
                      class="align-self-center mr-4"
                      v-on="on"
                      aria-label="more"
              >
                more
                <v-icon right>{{ mdiMenuDown }}</v-icon>
              </v-btn>
            </template>

            <v-list class="grey lighten-3">
              <v-list-item
                      v-for="(item, key) in tabmenumore"
                      :key="key"
                      :to="{name: item.name}"
              >
                {{ item.text }}
              </v-list-item>
            </v-list>
          </v-menu>
        </v-tabs>
      </template>
    </v-app-bar>

    <v-main>
      <v-banner v-for="alert in user.alerts" :key="alert.id">
        <template #icon>
          <v-icon
            color="warning"
            size="36"
          >
            {{ alert.icon }}
          </v-icon>
        </template>
        {{ alert.teaser }}
        <template #actions>
          <v-btn
            color="primary"
            depressed
            :href="alert.href"
            v-if="alert.href"
            :aria-label="alert.button || 'More'"
          >
            {{ alert.button || 'More' }}
          </v-btn>
          <v-btn
            color="primary"
            text
            @click="user.unalert(alert.id)"
            aria-label="Hide"
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
      class="d-flex flex-column align-stretch pa-0 white--text text--darken-1 elevation-12"
    >
      <div class="grey darken-3 d-sm-flex flex-row justify-space-between pa-4">
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
      <div class="grey darken-4 d-md-flex flex-row justify-space-between pa-6">
        <div>
          <p>{{ email }}</p>
          <p>
            Kyffhäuserstraße 5<br/>
            10781 Berlin<br/>
            Germany
          </p>
        </div>
        <div>
          <p>
            Please <router-link :to="{name: 'donate'}">donate</router-link>!
            <v-icon color="red" class="text--darken-2" dense>{{ mdiHeart }}</v-icon>
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
          <p class="white--text text--darken-2">
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
  data: () => ({
    user: useUserStore(),
    drawer: false,
    email: import.meta.env.VITE_APP_EMAIL,
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
  computed: {
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
  methods: {
    async logout() {
      await logout();
      router.push({name: 'home'});
    }
  }
}
</script>
