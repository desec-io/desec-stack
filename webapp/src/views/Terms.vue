<template>
  <div>
  <v-card outline tile class="pa-md-12 pa-8 elevation-4" style="overflow: hidden">
    <div class="d-none d-md-block triangle-bg">§§</div>
    <v-container class="pa-0">
      <v-row align="center">
        <v-col class="col-md-6 col-12 py-8 triangle-fg">
          <h1 class="display-1 font-weight-bold">Terms of Use</h1>
          <h3 class="subheading mt-2 py-8 font-weight-regular">
            <p>
              We collect as little data as possible and restrict the usage of our DNS service only where necessary to
              meet legal requirements or to ensure the smooth operation of our services. In turn, we rely on the
              community to use the service responsibly, and exercise care when configuring e.g. bulk operations.
            </p>
            <p>
              Our <router-link :to="{name: 'privacy-policy'}">Privacy Policy</router-link> is also part of the
              agreement between deSEC and its users.
            </p>
          </h3>
        </v-col>
      </v-row>
    </v-container>
  </v-card>
  <v-container fluid class="grey lighten-4">
    <v-container>
      <v-row class="pt-8">
        <v-col class="text-center">
          <h1>Terms of Use</h1>
        </v-col>
      </v-row>
      <v-row class="pb-8">
        <v-col class="col-12 col-sm-6 d-flex" v-for="t in terms_of_use" :key="t.title">
          <v-card>
            <v-card-title v-text="t.title"></v-card-title>
            <v-card-text>{{t.text}}</v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
  </v-container>
  </div>
</template>

<style scoped>
  div.triangle-bg {
    position: absolute;
    bottom: 0;
    width: 100%;
    z-index: 1;
    right: -.3em;
    height: 100%;
    text-align: right;
    font-size: 33em;
    font-weight: bold;
    color: #eee;
  }
  .triangle-fg {
    z-index: 2;
  }
</style>

<script>
export default {
  name: 'terms',
  data: () => ({
    terms_of_use: [
      {
        title: 'Keep Server Load Low',
        text: 'Only send update requests when there is something to update, and use reasonable TTLs. Accounts ' +
                'that cause extraordinarily high load or cost may be disabled or throttled. Account ' +
                'holders will be asked for cooperation to resolve the issue.',
      },
      {
        title: 'Users Must be Responsive',
        text: 'Users are required to register with an email address and are obliged to read and react to our ' +
                'emails. For users who do not react or are uncooperative, deSEC reserves the right to disable the ' +
                'account and/or zone, and/or modify or disable DNS records or zones in order to ensure smooth ' +
                'operation of deSEC services.',
      },
      {
        title: 'Expiration of Inactive dynDNS Domains',
        text: 'Dynamic DNS domains that are not updated for six months or longer will be ' +
                'deleted after a warning with 4 weeks notice. Owners can prevent deletion by updating DNS ' +
                'information. Deleted domains will undergo retention until associated certificates as recorded in ' +
                'the transparency log have expired, to make sure no valid certificates exist when another user ' +
                'registers the name again.',
      },
      {
        title: 'Domains with Illegal Activity',
        text: 'Domains that are used for illegal activity such as spam, scam, malware, phishing, etc. will be ' +
                'disabled immediately and permanently, and owners will be held liable. deSEC will cooperate with ' +
                'law enforcement to assist prosecution of illegal activity. In most cases, German and European Union ' +
                'legislation will apply.',
      },
      {
        title: 'Clients Will Need Updates',
        text: 'In order to ensure surpassing security and usability, deSEC will keep the provided services up to ' +
                'date as technology evolves. We explicitly do not guarantee that old client software keeps on ' +
                'working forever. Breaking changes will usually be announced weeks ahead, but time-critical changes ' +
                'may come with a shorter or even no grace period.',
      },
      {
        title: 'No Warranty',
        text: 'deSEC does not guarantee availability for its free services. Functionality of all services is ' +
                'provided on a best-effort basis. In particular, Quality of Service, even on a low level, and ' +
                'fitness for a particular purpose are not assured.',
      },
    ],
  })
}
</script>
