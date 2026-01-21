<template>
  <v-dialog
    v-model="show"
    max-width="900px"
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
        <v-icon :icon="mdiClose" @click.stop="close" />
      </v-card-title>
      <v-divider/>

      <v-alert
          class="mb-0"
          :model-value="isNew"
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
import DomainSetup from "@/views/DomainSetup.vue";
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
    modelValue: {
      type: Boolean,
      default: true,
    },
  },
  data: () => ({
    mdiClose,
  }),
  computed: {
    show: {
      get() {
        return this.modelValue
      },
      set(value) {
         this.$emit('update:modelValue', value)
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
