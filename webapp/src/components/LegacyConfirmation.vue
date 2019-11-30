<template>
  <v-dialog
    v-model="value"
    max-width="500px"
    persistent
    @keydown.esc="close"
  >
    <v-card>
      <v-card-title>
        <div class="title">
          {{ title }}
        </div>
        <v-spacer />
        <v-icon @click.stop="close">
          mdi-close
        </v-icon>
      </v-card-title>
      <v-divider />
      <v-alert
        :value="warning.length"
        type="warning"
      >
        {{ warning }}
      </v-alert>
      <v-alert
        :value="info.length"
        type="info"
      >
        {{ info }}
      </v-alert>
      <v-card-text>
        <slot />
      </v-card-text>
      <v-card-actions class="pa-3">
        <v-btn
          color="primary"
          class="grow"
          outline
          @click.native="close"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          class="grow"
          dark
          depressed
          @click.native="run"
        >
          Yes, please
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
export default {
  name: 'Confirmation',
  props: {
    callback: undefined,
    args: undefined,
    value: Boolean,
    title: {
      type: String,
      required: true,
    },
    info: {
      type: String,
      default: '',
    },
    warning: {
      type: String,
      default: '',
    },
  },
  methods: {
    close() {
      this.$emit('input', false);
    },
    run() {
      this.callback.apply(undefined, this.args);
      this.close();
    },
  },
};
</script>

<style>
</style>
