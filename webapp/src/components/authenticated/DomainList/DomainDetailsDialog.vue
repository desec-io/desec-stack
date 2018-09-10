<template>
  <v-dialog v-model="value" max-width="700px" persistent @keydown.esc="close">
    <v-card>
      <v-card-title>
        <div class="title">Domain details for <b>{{ name }}</b></div>
        <v-spacer></v-spacer>
        <v-icon @click.stop="close">close</v-icon>
      </v-card-title>
      <v-divider></v-divider>
      <v-alert :value="isNew" type="success">Your domain <b>{{ name }}</b> has been successfully created!</v-alert>
      <v-card-text>
        <p>Please forward the following information to your domain registrar:</p>
        <div class="caption font-weight-medium">NS records</div>
        <pre class="mb-3 pa-3">
ns1.desec.io
ns2.desec.io
</pre>
        <v-layout flex align-end>
          <div class="caption font-weight-medium">DS records</div>
          <v-spacer></v-spacer>
          <div v-if="!copied">
            <v-icon
              small
              @click="true"
              v-clipboard:copy="ds.join('\n')"
              v-clipboard:success="() => (copied = true)"
              v-clipboard:error="() => (copied = false)"
            >content_copy</v-icon>
          </div>
          <div v-else>copied! <v-icon small>check</v-icon></div>
        </v-layout>
        <pre
          class="mb-3 pa-3"
          v-clipboard:copy="ds.join('\n')"
          v-clipboard:success="() => (copied = true)"
          v-clipboard:error="() => (copied = false)"
        >
{{ ds.join('\n') }}
</pre>
        <p>Once your domain registrar processes this information, your deSEC DNS setup will be ready to use.</p>
      </v-card-text>
      <v-card-actions class="pa-3">
        <v-spacer></v-spacer>
        <v-btn color="primary" outline v-if="isNew" @click.native="$emit('createAnotherDomain')">Create another domain</v-btn>
        <v-btn color="primary" dark depressed @click.native="close">{{ isNew ? 'Close and edit' : 'Close' }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
export default {
  name: 'DomainDetailsDialog',
  props: {
    name: {
      type: String,
      required: true
    },
    isNew: {
      type: Boolean,
      required: true
    },
    ds: {
      type: Array,
      required: true
    },
    value: Boolean
  },
  data: () => ({
    copied: false
  }),
  methods: {
    close () {
      this.$emit('input', false)
      this.copied = false
    }
  }
}
</script>

<style scoped>
  .caption {
    text-transform: uppercase;
  }
  pre {
    background: lightgray;
    overflow: auto;
  }
</style>
