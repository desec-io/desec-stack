<template>
  <v-dialog
    v-model="show"
    max-width="900px"
    persistent
    scrollable
    @keydown.esc="close"
  >
    <v-card>
      <v-toolbar flat>
        <v-toolbar-title>
          Setup Instructions for <b>{{ domain }}</b>
        </v-toolbar-title>
        <v-spacer/>
        <v-btn
          icon
          variant="text"
          @click.stop="close"
        >
          <v-icon :icon="mdiClose" />
        </v-btn>
      </v-toolbar>
      <v-divider/>

      <v-alert
          class="mb-0"
          :model-value="isNew"
          type="success"
      >
        Your domain <b>{{ domain }}</b> has been successfully created!
      </v-alert>

      <v-card-text>
        <error-alert v-if="errors.length" :errors="errors" class="mb-4" />
        <delegation-status
          v-if="delegation"
          :item="delegation"
          class="mb-4"
        />
        <domain-setup
          v-bind="$attrs"
          :domain="domain"
          :delegation="delegation"
        ></domain-setup>
      </v-card-text>

      <v-card-actions class="pb-4">
        <v-spacer />
        <v-btn
          color="primary"
          variant="outlined"
          :loading="working"
          :disabled="working || !delegation"
          @click="runDelegationCheck"
        >
          <v-icon :icon="mdiRefresh" class="mr-1" />
          Run check now
        </v-btn>
        <v-btn color="primary" variant="text" @click="close">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import DomainSetup from "@/views/DomainSetup.vue";
import {mdiClose, mdiRefresh} from "@mdi/js";
import DelegationStatus from "@/components/Field/DelegationStatus.vue";
import ErrorAlert from "@/components/ErrorAlert.vue";
import {HTTP, digestError} from "@/utils";

export default {
  name: 'DomainSetupDialog',
  components: { DomainSetup, DelegationStatus, ErrorAlert },
  props: {
    domain: {
      type: String,
      required: true,
    },
    delegation: {
      type: Object,
      default: null,
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
    mdiRefresh,
    working: false,
    errors: [],
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
    },
  },
  methods: {
    async runDelegationCheck() {
      if (!this.delegation || this.working) {
        return;
      }
      this.errors = [];
      this.working = true;
      try {
        const response = await HTTP.post(
          `domains/${this.domain}/delegation-check/`
        );
        Object.assign(this.delegation, response.data);
      } catch (ex) {
        const errors = await digestError(ex, this);
        for (const key in errors) {
          this.errors.push(...errors[key]);
        }
      } finally {
        this.working = false;
      }
    },
    close() {
      this.show = false;
    }
  },
};
</script>

<style scoped>
</style>
