import Vue from 'vue';
import Vuetify from 'vuetify/lib';
import colors from 'vuetify/lib/util/colors'


Vue.use(Vuetify);


export default new Vuetify({
  theme: {
    themes: {
      light: {
        primary: colors.amber,
        secondary: colors.lightBlue.darken1,
        accent: colors.amber.accent4,
      },
    },
  },
})
