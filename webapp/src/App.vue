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
            <v-icon>{{item.icon}}</v-icon>
          </v-list-item-action>
          <v-list-item-content>
            <v-list-item-title>{{item.text}}</v-list-item-title>
          </v-list-item-content>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-app-bar
            app
    >
      <v-toolbar-title><router-link :to="{name: 'home'}">
        <v-img
                :src="require('./assets/logo.svg')"
                alt="deSEC Logo"
                contain
        ></v-img>
      </router-link></v-toolbar-title>
      <v-spacer/>
      <div class="d-none d-md-block">
        <router-link
                v-for="(item, key) in menu"
                :key="key"
                class="mx-2 primary--text text--darken-2" :to="{name: item.name}"
        >{{item.text}}</router-link>
      </div>
      <v-btn class="mx-4 mr-0" color="primary" depressed :to="{name: 'signup'}">Create Account</v-btn>
      <v-app-bar-nav-icon class="d-md-none" @click.stop="drawer = !drawer" />
    </v-app-bar>

    <v-content>
      <router-view/>
    </v-content>
    <v-footer
      class="d-flex flex-column align-stretch pa-0 white--text text--darken-1 elevation-12"
    >
      <div class="grey darken-3 d-sm-flex flex-row justify-space-between pa-4">
        <div class="pa-2">
          <b>deSEC e.V.</b>
        </div>
        <div class="d-sm-flex flex-row align-right py-2">
          <div class="px-2"><a href="//github.com/desec-io/desec-stack/">Source Code</a></div>
          <div class="px-2"><router-link :to="{name: 'impressum'}">Impressum (Legal Notice)</router-link></div>
          <div class="px-2"><router-link :to="{name: 'privacy-policy'}">Datenschutzerklärung (Privacy Policy)</router-link></div>
        </div>
      </div>
      <div class="grey darken-4 d-md-flex flex-row justify-space-between pa-6">
        <div>
          <p>{{email}}</p>
          <p>
            Kyffhäuserstraße 5<br/>
            10781 Berlin<br/>
            Germany
          </p>
        </div>
        <div>
          <p>Please <router-link :to="{name: 'donate'}">donate</router-link>! 💛</p>
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
            Dr. Peter Thomassen<br/>
            Wolfgang Studier<br/>
          </p>
        </div>
      </div>
    </v-footer>
  </v-app>
</template>

<script>
import {EMAIL} from './env';
export default {
  name: 'App',
  data: () => ({
    drawer: false,
    email: EMAIL,
    menu: {
      'home': {
        'name': 'home',
        'icon': 'mdi-home',
        'text': 'Home',
      },
      'docs': {
        'name': 'docs',
        'icon': 'mdi-book-open-page-variant',
        'text': 'API Reference',
      },
      'donate': {
        'name': 'donate',
        'icon': 'mdi-gift-outline',
        'text': 'Donate',
      },
      'reset-password': {
        'name': 'reset-password',
        'icon': 'mdi-lock-reset',
        'text': 'Reset Account Password',
      },
    }
  }),
}
</script>
