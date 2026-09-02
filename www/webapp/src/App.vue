<template>
  <v-app id="inspire">
    <v-navigation-drawer
      v-model="drawer"
      location="right"
      disable-resize-watcher
    >
      <v-list density="compact" class="main-menu-drawer">
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

    <v-app-bar color="white" :extended="authenticated">
      <v-app-bar-title><router-link :to="{name: 'home'}">
        <v-img
          src="./assets/logo.svg"
          alt="deSEC Logo"
          class="app-logo"
          height="32"
          width="147"
          eager
        ></v-img>
      </router-link></v-app-bar-title>
      <v-spacer/>
      <div class="d-none d-md-block mr-4">
        <span class="mx-2" v-for="(item, key) in menu" :key="key">
          <router-link
            class="main-menu-link"
            :to="{name: item.name}"
          >{{ item.text }}</router-link>
          <v-icon v-if="item.post_icon" :icon="item.post_icon" :color="item.post_icon_color" class="ml-1" size="small" />
        </span>
      </div>
      <v-btn class="mx-4" color="primary" variant="flat" :to="{name: 'signup', query: $route.query}" v-if="!authenticated">Create Account</v-btn>
      <v-btn class="mx-4 ml-0" color="primary" variant="flat" :to="{name: 'login'}" v-if="!authenticated">Log In</v-btn>
      <v-btn class="mx-4 ml-0" color="primary" variant="outlined" @click="logout" v-if="authenticated">Log Out</v-btn>
      <v-app-bar-nav-icon class="d-md-none" @click.stop="drawer = !drawer" />
      <template #extension v-if="authenticated">
        <div class="authenticated-tabs d-flex align-center w-100 bg-primary text-white">
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

            <v-list>
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
              color="secondary"
              style="z-index: 3"
      ></v-progress-linear>
      <!-- key by path so that views are re-created when only route params change -->
      <router-view :key="$route.path"/>
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
      <div class="bg-grey-darken-4 d-md-flex flex-row justify-space-between pa-6 footer-details">
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
.v-application {
  color: rgba(0, 0, 0, 0.87);
}
.v-application p {
  margin-bottom: 16px;
}
.v-application ul,
.v-application ol {
  padding-left: 24px;
  margin-bottom: 16px;
}
.v-application li > ul,
.v-application li > ol {
  margin-top: 0;
  margin-bottom: 0;
}
.v-application a,
.v-overlay-container a {
  color: #ffc107 !important;
  text-decoration: underline;
}
.v-application a:hover,
.v-application a:focus,
.v-overlay-container a:hover,
.v-overlay-container a:focus {
  text-decoration: underline;
}
.v-application .main-menu-link {
  color: #ffa000 !important;
  text-decoration: none;
}
.v-application .main-menu-link:hover,
.v-application .main-menu-link:focus {
  color: #ffa000 !important;
}
.v-application .main-menu-drawer .v-list-item {
  color: rgba(0, 0, 0, 0.87) !important;
  text-decoration: none;
}
.v-application .main-menu-drawer .v-list-item--active {
  background-color: #e0e0e0;
}
.v-application .main-menu-drawer .v-list-item .v-icon {
  color: rgba(0, 0, 0, 0.54);
}
.v-application .v-btn.bg-primary {
  color: #fff !important;
  text-decoration: none;
}
.v-application .authenticated-tabs a {
  color: #fff !important;
}
.v-application .bg-grey-darken-3 a,
.v-application .bg-grey-darken-4 a {
  color: #ffa000 !important;
  text-decoration: underline;
}
.app-logo {
  width: auto;
}
.footer-details {
  row-gap: 24px;
}
.v-card-title {
  display: flex;
  align-items: center;
}
.v-card-text {
  letter-spacing: 0;
}
.v-alert .v-alert__content > :last-child,
.v-card-text > :last-child,
.v-expansion-panel-text__wrapper > :last-child {
  margin-bottom: 0;
}
/* Vuetify gives alerts `flex: 1 1 0`, so an alert sitting directly in a card is
   a shrinkable flex item: once a dialog is taller than the viewport, the alert
   is squeezed into its own padding, and the text ends up against the edge. */
.v-card > .v-alert {
  flex: none;
}
.v-application .text-primary {
  color: #ffa000 !important;
}
.v-application .v-field {
  background-color: #FFFFFF;
}
.v-application .v-field__overlay {
  background-color: transparent;
  opacity: 0;
}
.v-input--disabled {
  opacity: 1;
}
.v-application .v-field--variant-plain {
  background-color: #FFFFFF;
}
.v-application .v-field--variant-plain .v-field__outline,
.v-application .v-field--variant-plain .v-field__underlay {
  display: none;
}
.v-application .v-field--variant-plain input,
.v-application .v-field--variant-plain textarea {
  color: rgba(0, 0, 0, 0.87);
}
.v-application .v-input--disabled .v-field,
.v-application .v-field--disabled {
  background-color: #f5f5f5;
}
.v-application .v-input--disabled .v-field__outline,
.v-application .v-input--disabled .v-field__underlay,
.v-application .v-field--disabled .v-field__outline,
.v-application .v-field--disabled .v-field__underlay {
  display: none;
}
.v-application .v-input--disabled input,
.v-application .v-input--disabled textarea,
.v-application .v-field--disabled input,
.v-application .v-field--disabled textarea {
  color: rgba(0, 0, 0, 0.54);
}
.v-btn--disabled.v-btn--variant-flat {
  background-color: #e0e0e0 !important;
  color: rgba(0, 0, 0, 0.54) !important;
  opacity: 1;
}
</style>
