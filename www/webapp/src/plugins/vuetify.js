import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi-svg'
import { VDataTable, VOtpInput } from 'vuetify/components'
import colors from 'vuetify/util/colors'

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
          primary: colors.amber.base,
          secondary: colors.lightBlue.darken1,
          accent: colors.amber.accent4,
        },
      },
    },
  },
})
