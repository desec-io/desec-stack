<template>
  <v-dialog v-model="value" max-width="500px" persistent @keydown.esc="close">
    <v-card>
      <v-form @submit.prevent="$emit('createNewDomain', domainName)">
        <v-card-title>
          <span class="title">Create a New Domain</span>
          <v-spacer></v-spacer>
          <v-icon @click.stop="close">close</v-icon>
        </v-card-title>
        <v-divider></v-divider>
        <v-alert :value="error.length" type="error">{{ error }}</v-alert>
        <v-card-text>
          <p>You have {{ left }} of {{ limit }} domains left in your plan. <a>Upgrade now!</a></p>
          <v-text-field :disabled="left <= 0" v-model="domainName" label="Enter domain name" hint="example.com" required></v-text-field>
        </v-card-text>
        <v-card-actions>
          <v-btn color="primary" class="grow" outline @click.native="close">Cancel</v-btn>
          <v-btn color="primary" class="grow" depressed type="submit" :disabled="left <= 0">Create</v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>

<script>
export default {
  name: 'NewDomainDialog',
  props: {
    current: {
      type: Function,
      required: true
    },
    limit: {
      type: Number,
      required: true
    },
    error: {
      default: ''
    },
    value: Boolean
  },
  data: () => ({
    /* TODO
    - We could clear this upon the parent component emitting a domainCreated event.
      I guess we'd need an event bus though in order to hear this event.
     */
    domainName: ''
  }),
  methods: {
    close () {
      this.$emit('input', false)
    }
  },
  computed: {
    left () {
      return this.limit - this.current()
    }
  }
}
</script>

<style>
</style>
