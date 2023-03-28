<template>
  <v-dialog
    v-model="show"
    max-width="700px"
    persistent
    scrollable
    @keydown.esc="close"
  >
    <v-card>
      <v-card-title>
        <div class="text-h6">
          Setup Instructions for <b>{{ domain }}</b>
        </div>
        <v-spacer/>
        <v-icon @click.stop="close">
          {{ mdiClose }}
        </v-icon>
      </v-card-title>
      <v-divider/>

      <v-alert
          class="mb-0"
          :value="isNew"
          type="success"
      >
        Your domain <b>{{ domain }}</b> has been successfully created!
      </v-alert>

      <v-card-text>
        <domain-setup v-bind="$attrs" :domain="domain"></domain-setup>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script>
import DomainSetup from "@/views/DomainSetup";
import {mdiClose} from "@mdi/js";

export default {
  name: 'DomainSetupDialog',
  components: { DomainSetup },
  props: {
    domain: {
      type: String,
      required: true,
    },
    isNew: {
      type: Boolean,
      default: false,
    },
  },
  data: () => ({
    mdiClose,
    value: {
      type: Boolean,
      default: true,
    },
  }),
  computed: {
    show: {
      get() {
        return this.value
      },
      set(value) {
         this.$emit('input', value)
      }
    }
  },
  methods: {
    close() {
      this.show = false;
    }
  },
};
</script>
