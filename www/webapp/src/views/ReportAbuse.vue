<template>
  <div>
    <v-card outline tile class="pa-md-12 pa-8 elevation-4" style="overflow: hidden">
      <v-container class="pa-0">
        <v-row align="center">
          <v-col class="col-md-6 col-12 py-8 triangle-fg">
            <h1 class="display-1 font-weight-bold">Report Abuse</h1>
            <h3 class="subheading mt-2 py-8 font-weight-regular">
              <p>
                deSEC does not tolerate abuse of its services.
                Domains involved in illegal activity such as spam, scam, malware, phishing will be disabled immediately and
                permanently in accordance with our <router-link :to="{name: 'terms'}">Terms of Use</router-link>.
              </p>
              <p>
                Note that the burden of proof is on the reporter.
                Domains involved in abuse will only be disabled if sufficient proof is provided by the report.
                deSEC has only limited resources and may not be able to investigate reports that do not include sufficient proof of abuse.
              </p>
            </h3>
          </v-col>
        </v-row>
      </v-container>
    </v-card>
    <v-container>
      <v-row>
        <v-col cols="12" class="pt-5">
          <ReportAbuseForm/>
        </v-col>
      </v-row>
    </v-container>
  </div>
</template>

<script>
  import ReportAbuseForm from '@/components/ReportAbuseForm.vue';

  export default {
    name: 'Donate',
    components: {
      ReportAbuseForm,
    }
  }
</script>

<style lang="scss">
  .fixed-width {
    font-family: monospace;
  }
</style>
