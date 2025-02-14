<template>
  <v-container>
    <v-row align="center">
      <v-col class="col-md-6 col-12 py-8">
        <h1 class="text-h4 font-weight-bold">Donate to Support our Mission</h1>
        <div class="text-subtitle-1 mt-6 font-weight-regular">
          <p>
            Like our community service? Your donation shows us we're on the right track.
            All donations are used in accordance with <router-link :to="{name: 'about'}">our statutes</router-link>.
          </p>
        </div>
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12" md="6">
        <v-card>
          <v-toolbar
                  color="primary"
                  dark
                  flat
          >
            <v-toolbar-title>Donate</v-toolbar-title>
          </v-toolbar>
          <v-card-text>
            <v-expansion-panels class="mb-4" focusable>
              <v-expansion-panel>
                <v-expansion-panel-header class="text-subtitle-1">
                  <v-layout>
                    <v-icon class="mr-2">{{ mdiBankTransferIn }}</v-icon> Direct Debit – Let us Take your Money (Europe)
                  </v-layout>
                </v-expansion-panel-header>
                <v-expansion-panel-content class="pt-4">
                  <p>
                    With your permission, we debit your donation directly from your European bank account.
                    To give us permission, use this form:
                  </p>
                  <DonateDirectDebitForm/>
                </v-expansion-panel-content>
              </v-expansion-panel>
              <v-expansion-panel>
                <v-expansion-panel-header class="text-subtitle-1">
                  <v-layout>
                    <v-icon class="mr-2">{{ mdiBankTransferOut }}</v-icon> Bank Transfer – Send us Money (Europe)
                  </v-layout>
                </v-expansion-panel-header>
                <v-expansion-panel-content class="pt-4">
                  <p>
                    We're happy to accept donations via bank transfer. Please use the following account details:
                  </p>
                  <v-simple-table>
                    <tbody>
                    <tr>
                      <td>Recipient</td>
                      <td>deSEC e.V.</td>
                    </tr>
                    <tr>
                      <td>IBAN</td>
                      <td>DE91 8306 5408 0004 1580 59</td>
                    </tr>
                    <tr>
                      <td>BIC</td>
                      <td>GENODEF1SLR</td>
                    </tr>
                    </tbody>
                  </v-simple-table>
                  <div class="text-center">
                    <qrcode-vue :value="bank_transfer_epc" size="300"/>
                  </div>
                </v-expansion-panel-content>
              </v-expansion-panel>
              <v-expansion-panel>
                <v-expansion-panel-header class="text-subtitle-1">
                  <v-layout>
                    <v-icon class="mr-2">{{ mdiCreditCardOutline }}</v-icon> Credit Card
                  </v-layout>
                </v-expansion-panel-header>
                <v-expansion-panel-content class="pt-4">
                  <p>
                    To donate by credit card, <strong>please use <a href="https://liberapay.com/deSEC/donate"
                    target="_blank">our account at Liberapay</a></strong>.
                  </p>
                  <p>
                    By default, Liberapay sets up a recurring donation. If you want to support us only once, simply stop
                    the automatic payment plan right after your first donation. However, as our costs are recurring, we
                    actually do appreciate recurring donations.
                  </p>
                </v-expansion-panel-content>
              </v-expansion-panel>
              <v-expansion-panel>
                <v-expansion-panel-header class="text-subtitle-1">
                  <v-layout>
                    <v-icon class="mr-2">{{ mdiGithub }}</v-icon> GitHub Sponsors
                  </v-layout>
                </v-expansion-panel-header>
                <v-expansion-panel-content class="pt-4">
                  <p>
                    <strong><a href="https://github.com/sponsors/desec-io" target="_blank">Click here</a> to donate via
                    GitHub.</strong>
                  </p>
                </v-expansion-panel-content>
              </v-expansion-panel>
              <v-expansion-panel>
                <v-expansion-panel-header class="text-subtitle-1">
                  <v-layout>
                    <v-icon class="mr-2">{{ mdiGiftOutline }}</v-icon> PayPal
                  </v-layout>
                </v-expansion-panel-header>
                <v-expansion-panel-content class="pt-4">
                  <p>
                    <strong><a href="https://www.paypal.com/donate?hosted_button_id=GPGXGLA4SU78W" target="_blank">Click
                    here</a> or use the below QR code to donate via PayPal.</strong>
                    Note that PayPal charges us the highest fees of all, so if
                    you can use one of the other methods, that would be appreciated!
                  </p>
                  <v-layout class="justify-center">
                    <v-img src="../assets/paypal-qrcode.png" alt="PayPal QR Code" style="max-width: 256px"></v-img>
                  </v-layout>
                </v-expansion-panel-content>
              </v-expansion-panel>
              <v-expansion-panel>
                <v-expansion-panel-header class="text-subtitle-1">
                  <v-layout>
                    <v-icon class="mr-2">{{ mdiBitcoin }}</v-icon> Crypto Currency (BTC, ETH, LTC)
                  </v-layout>
                </v-expansion-panel-header>
                <v-expansion-panel-content class="pt-4">
                  <p>If you prefer to donate in a crypto currency, you can use the following wallets:</p>
                  <table>
                    <tr>
                      <th>Bitcoin (BTC)</th>
                      <td><span class="fixed-width">1NMsTB3ML9t7QiEyiyXaU2oi72i2aDhVEK</span></td>
                    </tr>
                    <tr>
                      <th>Ethereum (ETH)</th>
                      <td><span class="fixed-width">0xb9594A8d1BF512eAC59069d9d5cbA457E0d35998</span></td>
                    </tr>
                    <tr>
                      <th>Litecoin (LTC)</th>
                      <td><strong>(No MWEB!)</strong> <span class="fixed-width">LeFYoRRcrMPiruRGQQknQBdjGdmsEpHzno</span></td>
                    </tr>
                  </table>
                  <p class="mt-4">Note that we cannot provide you a donation receipt for crypto donations.</p>
                </v-expansion-panel-content>
              </v-expansion-panel>
              <v-expansion-panel>
                <v-expansion-panel-header class="text-subtitle-1">
                  <v-layout>
                    <v-icon class="mr-2">{{ mdiHeartMultipleOutline }}</v-icon> Double-up with Your Employer
                  </v-layout>
                </v-expansion-panel-header>
                <v-expansion-panel-content class="pt-4">
                  <p>
                    Many employers <b>double donations</b> initiated by their employees. Donations often happen through
                    dedicated facilitation platforms such as
                    <a href="https://causes.benevity.org/causes/276-5650058387161_db64" target="_blank">Benevity</a>.
                  </p>
                  <p>
                    Make sure to <b>check with your company</b> if you're eligible for a co-donation, and double the
                    impact!
                  </p>
                </v-expansion-panel-content>
              </v-expansion-panel>
            </v-expansion-panels>
            <p>
              <strong>Based in Europe?</strong> You almost certainly can donate via direct debit or bank transfer (you
              only need your IBAN). <strong>No fees</strong> will be subtracted, so you can do more good!
            </p>
            <div class="text-h6">Donation Receipts</div>
            <p>
              deSEC e.V. is registered as a charitable organization in Germany. If you pay taxes here, your donation is
              tax-deductible, and we're happy to provide you with a donation receipt for that purpose. Note that for
              donations below 200 €, no receipt is needed to claim tax deduction.
            </p>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col col="12" md="6">
        <v-card>
          <v-toolbar
                  color="primary"
                  dark
                  flat
          >
            <v-toolbar-title>Support our Quest</v-toolbar-title>
          </v-toolbar>
          <v-card-text>
            <p>
              deSEC is dedicated to enhance the security of online data transmission, by spreading the seamless use of
              state-of-the art encryption technology. Sensitive data is stored in Germany only, safely protected from
              unauthorized access by criminals or government agencies.
            </p>
            <p>
              Reliable operation of our free DNS service incurs significant cost (several thousand euros each month!),
              both for the serious technical infrastructure that is required as well as for staff. Your donation is
              used to cover these expenses and ensures our service's smooth operation.
            </p>
            <p>
              We also need your donation to support the future development of our services to make the Internet more
              secure. If you would like to contribute to this, please support us with your donation and encourage
              others to do alike.
            </p>
            <p>
              Your donation also gives you a way to say “Thanks!”. If you are excited about our free community service,
              please consider expressing your gratitude with a small (or large) gift.
            </p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
  import DonateDirectDebitForm from '@/components/DonateDirectDebitForm.vue';
  import QrcodeVue from '../modules/qrcode.vue/dist/qrcode.vue.esm';
  import {mdiBankTransferIn, mdiBankTransferOut, mdiBitcoin, mdiCreditCardOutline, mdiGiftOutline, mdiGithub, mdiHeartMultipleOutline} from "@mdi/js";

  export default {
    name: 'DonatePage',
    components: {
      QrcodeVue,
      DonateDirectDebitForm,
    },
    data() {
      return {
        bank_transfer_epc: (
            "BCD\n001\n1\nSCT\n" +
            "GENODEF1SLR\n" +
            "deSEC e.V.\n" +
            "DE91830654080004158059\n" +
            "\n\n\n" +
            "Donation Spende deSEC e.V.\n"
        ),
        mdiBankTransferIn,
        mdiBankTransferOut,
        mdiBitcoin,
        mdiCreditCardOutline,
        mdiGithub,
        mdiGiftOutline,
        mdiHeartMultipleOutline
      }
    },
  }
</script>

<style scoped>
  th {
    padding-right: 1ch;
    text-align: left;
  }
  .fixed-width {
    font-family: monospace;
  }
</style>
