<template>
  <v-container
          class="fill-height"
  >
    <v-timeline :dense="$vuetify.breakpoint.smAndDown">
      <v-timeline-item
              color="primary"
              fill-dot
              right
      >
        <v-card>
          <v-card-title class="accent">
            <v-icon
                    dark
                    size="42"
                    class="mr-4"
            >
              mdi-account
            </v-icon>
            <h2 class="display-1 white--text font-weight-light">Create an Account</h2>
          </v-card-title>
          <v-container>
            <v-row>
              <v-col cols="12" md="10">
                Lorem ipsum dolor sit amet, no nam oblique veritus. Commune scaevola imperdiet nec ut, sed euismod convenire principes at. Est et nobis iisque percipit.
              </v-col>
              <v-col
                      class="hidden-sm-and-down text-right"
                      md="2"
              >
                <v-icon size="64">mdi-calendar-text</v-icon>
              </v-col>
            </v-row>
          </v-container>
        </v-card>
      </v-timeline-item>

      <v-timeline-item
              color="primary"
              fill-dot
              left
      >
        <v-card>
          <v-card-title class="accent justify-end">
            <h2 class="display-1 mr-4 white--text font-weight-light">Confirm Email Address</h2>
            <v-icon
                    dark
                    size="42"
            >mdi-home-outline</v-icon>
          </v-card-title>
          <v-container>
            <v-row>
              <v-col cols="12" md="8">
                Lorem ipsum dolor sit amet, no nam oblique veritus. Commune scaevola imperdiet nec ut, sed euismod convenire principes at. Est et nobis iisque percipit.
              </v-col>
              <v-col cols="12" md="4">
                Lorem ipsum dolor sit amet, no nam oblique veritus.
              </v-col>
            </v-row>
          </v-container>
        </v-card>
      </v-timeline-item>

      <v-timeline-item
              color="primary"
              fill-dot
              right
      >
        <v-card>
          <v-card-title class="accent">
            <v-icon
                    class="mr-4"
                    dark
                    size="42"
            >
              mdi-router-wireless
            </v-icon>
            <h2 class="display-1 white--text font-weight-light">Configure your Client</h2>
          </v-card-title>
          <v-container>
            <v-row>
              <v-col
                      v-for="n in 3"
                      :key="n"
                      cols="12"
                      md="4"
              >
                Lorem ipsum dolor sit amet, no nam oblique veritus no nam oblique.
              </v-col>
            </v-row>
          </v-container>
        </v-card>
      </v-timeline-item>

      <v-timeline-item
              color="primary"
              fill-dot
              left
      >
        <v-card>
          <v-card-title class="accent justify-end">
            <h2 class="display-1 mr-4 white--text font-weight-light">Check your Setup</h2>
            <v-icon
                    dark
                    size="42"
            >
              mdi-cloud-check
            </v-icon>
          </v-card-title>
          <v-container>
            <v-row>
              <v-col class="hidden-sm-and-down" md="2">
                <v-icon size="64">mdi-server-network</v-icon>
              </v-col>
              <v-col cols="12" md="10">
                Lorem ipsum dolor sit amet, no nam oblique veritus. Commune scaevola imperdiet nec ut, sed euismod convenire principes at. Est et nobis iisque percipit, an vim zril disputando voluptatibus.
              </v-col>
            </v-row>
          </v-container>
        </v-card>
      </v-timeline-item>

      <v-timeline-item
              color="primary"
              fill-dot
              right
      >
        <v-card>
          <v-card-title class="accent">
            <v-icon
                    class="mr-4"
                    dark
                    size="42"
            >
              mdi-thumb-up
            </v-icon>
            <h2 class="display-1 white--text font-weight-light">Finish</h2>
          </v-card-title>
          <v-container>
            <v-row>
              <v-col>
                Lorem ipsum dolor sit amet, no nam oblique veritus. Commune scaevola imperdiet nec ut, sed euismod convenire principes at. Est et nobis iisque percipit, an vim zril disputando voluptatibus, vix an salutandi sententiae.
              </v-col>
            </v-row>
          </v-container>
        </v-card>
      </v-timeline-item>
    </v-timeline>
  </v-container>
</template>
