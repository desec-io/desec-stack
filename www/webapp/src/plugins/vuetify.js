import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi-svg'
import { VDataTable, VOtpInput } from 'vuetify/components'
import { amber, lightBlue } from 'vuetify/util/colors'

export default createVuetify({
  components: {
    VDataTable,
    VOtpInput,
  },
  icons: {
    defaultSet: 'mdi',
    aliases,
    sets: {
      mdi,
    },
  },
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        colors: {
          primary: amber.base,
          primaryLight4: amber.lighten4,
          secondary: lightBlue.darken1,
          accent: amber.accent4,
          'on-primary': '#fff',
        },
      },
    },
  },
})
