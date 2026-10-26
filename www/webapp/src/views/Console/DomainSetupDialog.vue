<template>
  <v-dialog
    v-model="show"
    max-width="900px"
    persistent
    scrollable
    @keydown.esc="close"
  >
    <v-card>
      <v-card-title class="domain-setup-title">
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

      <!-- What the delegation checks found, with the re-check button -->
      <v-alert
          v-if="showStatus"
          class="mb-0 delegation-status-block"
          :color="isChecking ? 'grey' : summary.color"
          :icon="isChecking ? false : summary.icon"
          variant="tonal"
          rounded="0"
      >
        <div class="d-flex flex-wrap align-center ga-2">
          <div class="text-subtitle-1 font-weight-bold">{{ isChecking ? 'Checking…' : summary.label }}</div>
          <v-spacer/>
          <v-btn
              v-if="recheckable"
              size="small"
              variant="text"
              :prepend-icon="mdiRefresh"
              :loading="isChecking"
              :disabled="isChecking"
              @click="$emit('recheck')"
          >
            Re-check
          </v-btn>
        </div>
        <template v-if="isChecking">
          <p class="my-2 text-high-emphasis">This usually takes a few seconds.</p>
          <v-progress-linear indeterminate/>
        </template>
        <div :class="{'delegation-status-previous': isChecking}">
          <!-- In the default text color: long text in the tonal color is hard to read -->
          <p v-for="(paragraph, i) in summary.details" :key="i" class="my-2 text-high-emphasis">{{ paragraph }}</p>
          <v-btn
              v-if="summary.state === 'insecure' && ds.length"
              size="small"
              variant="outlined"
              :prepend-icon="copied ? mdiCheck : mdiContentCopy"
              @click="copyRequest"
          >
            {{ copied ? 'Copied' : 'Copy request for your registrar' }}
          </v-btn>
          <div v-if="checkedAgo" class="text-caption mt-2 text-medium-emphasis">Checked {{ checkedAgo }}.</div>
        </div>
      </v-alert>

      <v-card-text>
        <domain-setup v-bind="$attrs" :domain="domain" :ds="ds"></domain-setup>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script>
import {formatDistanceToNow} from 'date-fns/formatDistanceToNow';
import DomainSetup from "@/views/DomainSetup.vue";
import {delegationSummary, isRecheckable, isUnderLocalPublicSuffix, registrarRequest} from "@/delegation";
import {mdiCheck, mdiClose, mdiContentCopy, mdiRefresh} from "@mdi/js";

export default {
  name: 'DomainSetupDialog',
  components: { DomainSetup },
  props: {
    domain: {
      type: String,
      required: true,
    },
    ds: {
      type: Array,
      default: () => [],
    },
    isNew: {
      type: Boolean,
      default: false,
    },
    // The domain as listed, whose status a re-check updates.
    item: {
      type: Object,
      default: null,
    },
    // Domain name -> true while a re-check is under way.
    checking: {
      type: Object,
      default: () => ({}),
    },
    modelValue: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['update:modelValue', 'input', 'recheck'],
  data: () => ({
    copied: false,
    mdiCheck,
    mdiClose,
    mdiContentCopy,
    mdiRefresh,
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
    showStatus() {
      // A domain just created has not been delegated yet, and domains under
      // our own suffixes are delegated and secured by us.
      return !!this.item && !this.isNew && !isUnderLocalPublicSuffix(this.domain);
    },
    summary() {
      return delegationSummary(this.item?.status, this.domain);
    },
    isChecking() {
      return !!this.checking[this.domain];
    },
    recheckable() {
      return !!this.item && isRecheckable(this.item);
    },
    checkedAgo() {
      const checked = this.item?.status?.checked;
      return checked ? formatDistanceToNow(new Date(checked), {addSuffix: true}) : '';
    },
  },
  methods: {
    close() {
      this.show = false;
    },
    async copyRequest() {
      try {
        await navigator.clipboard.writeText(registrarRequest(this.domain, this.ds));
        this.copied = true;
        setTimeout(() => { this.copied = false; }, 3000);
      } catch {
        // Clipboard access denied: the DS records below can still be copied.
      }
    },
  },
};
</script>

<style scoped>
.domain-setup-title {
  flex-wrap: nowrap;
}
.delegation-status-previous {
  opacity: 0.6;
}
</style>
