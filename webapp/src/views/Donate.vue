<template>
  <v-container>
    <h1>Donate to deSEC</h1>
    <h2>You like deSEC? Donate now to support us in our mission. Your donation shows us we're on the right track.</h2>
    <v-row>
      <v-col col="12" lg="4">
        <v-card>
          <v-toolbar
                  color="primary"
                  dark
                  flat
          >
            <v-toolbar-title>Support deSEC's quest to make the Internet more secure!</v-toolbar-title>
          </v-toolbar>
          <v-card-text>
            <p>
              deSEC is dedicated to enhance the security of data transmission via the Internet, by introducing
              state-of-the art encryption technology. Sensitive client data is stored only in Germany, and safely
              protected from unauthorized access by criminals or government agencies. Your donation is used to improve
              our technical infrastructure for our free dynDNS service and ensures its smooth operation.
            </p>
            <p>
              Your donation gives you a way to say "Thanks!". It also supports the future developments of our services
              which make the Internet more secure. If you would like to contribute to this, or if you are simpliy
              excited about our free dynDNS service, please support us with your donation and encourage others to do
              alike!
            </p>
            <p>
              deSEC e.V. is registered as charity organization, so if you pay taxes in Germany, you may be able to use
              your donation in your tax declaration. We automatically issue donations receipts for donations over 200€;
              for donations below that the receipt is not needed to claim the tax deduction.
            </p>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="6" lg="4">
        <v-card>
          <v-toolbar
                  color="primary"
                  dark
                  flat
          >
            <v-toolbar-title>Donate via Bank Transfer (SEPA)</v-toolbar-title>
          </v-toolbar>
          <v-card-text>
            <p>We happily accept donations via bank transfer. Please use the following account details.</p>
            <v-simple-table>
              <tbody>
              <tr>
                <td>Recipient</td>
                <td class="fixed-width">deSEC e.V.</td>
              </tr>
              <tr>
                <td>IBAN</td>
                <td class="fixed-width">DE91 8306 5408 0004 1580 59</td>
              </tr>
              <tr>
                <td>BIC</td>
                <td class="fixed-width">GENODEF1SLR</td>
              </tr>
              </tbody>
            </v-simple-table>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="6" lg="4">
        <v-card>
          <v-toolbar
                  color="primary"
                  dark
                  flat
          >
            <v-toolbar-title>Donate in Some Other Way</v-toolbar-title>
          </v-toolbar>
          <v-card-text>
            <p></p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<style lang="scss">
  .fixed-width {
    font-family: monospace;
  }
</style>
