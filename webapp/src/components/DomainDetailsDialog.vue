<template>
  <v-dialog
    v-model="value"
    max-width="700px"
    persistent
    @keydown.esc="close"
  >
    <v-card>
      <v-card-title>
        <div class="title">
          Domain details for <b>{{ name }}</b>
        </div>
        <v-spacer />
        <v-icon @click.stop="close">
          mdi-close
        </v-icon>
      </v-card-title>
      <v-divider />
      <v-alert
        :value="isNew"
        type="success"
      >
        Your domain <b>{{ name }}</b> has been successfully created!
      </v-alert>
      <v-card-text>
        <p>Please forward the following information to your domain registrar:</p>
        <div class="caption font-weight-medium">
          NS records
        </div>
        <pre class="mb-3 pa-3">
ns1.desec.io
ns2.desec.io
</pre>
        <v-layout
          flex
          align-end
        >
          <div class="caption font-weight-medium">
            DS records
          </div>
          <v-spacer />
          <div v-if="!copied">
            <v-icon
              v-clipboard:copy="ds.join('\n')"
              v-clipboard:success="() => (copied = true)"
              v-clipboard:error="() => (copied = false)"
              small
              @click="true"
            >
              mdi-content_copy
            </v-icon>
          </div>
          <div v-else>
            copied! <v-icon small>
              mdi-check
            </v-icon>
          </div>
        </v-layout>
        <pre
          v-clipboard:copy="ds.join('\n')"
          v-clipboard:success="() => (copied = true)"
          v-clipboard:error="() => (copied = false)"
          class="mb-3 pa-3"
        >
{{ ds.join('\n') }}
</pre>
        <p>Once your domain registrar processes this information, your deSEC DNS setup will be ready to use.</p>
      </v-card-text>
      <v-card-actions class="pa-3">
        <v-spacer />
        <v-btn
          v-if="isNew"
          color="primary"
          outline
          @click.native="$emit('createAnotherDomain')"
        >
          Create another domain
        </v-btn>
        <v-btn
          color="primary"
          dark
          depressed
          @click.native="close"
        >
          {{ isNew ? 'Close and edit' : 'Close' }}
        </v-btn>
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
      required: true,
    },
    isNew: {
      type: Boolean,
      default: false,
    },
    ds: {
      type: Array,
      required: true,
    },
    value: Boolean,
  },
  data: () => ({
    copied: false,
  }),
  methods: {
    close() {
      this.$emit('input', false);
      this.copied = false;
    },
  },
};
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
