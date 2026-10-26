<template>
  <div class="delegation-status my-1 py-4">
    <v-chip
        v-if="!isLocal"
        :color="checking ? 'grey' : summary.color"
        :prepend-icon="checking || compact ? undefined : summary.icon"
        :aria-label="text"
        size="small"
        variant="tonal"
        label
    >
      <v-progress-circular v-if="checking" :class="{'me-2': !compact}" indeterminate size="14" width="2" />
      <v-icon v-else-if="compact" :icon="summary.icon" size="small" />
      <template v-if="!compact">{{ text }}</template>
      <v-tooltip activator="parent" location="top" max-width="400">
        <span v-if="checking">{{ compact ? 'Checking… ' : '' }}Before: {{ summary.label }}<template v-if="checkedAgo">, checked {{ checkedAgo }}</template></span>
        <template v-else>
          <div v-if="compact" class="font-weight-bold">{{ summary.label }}</div>
          <div>{{ summary.hint }}</div>
          <div v-if="checkedAgo" class="text-caption">Checked {{ checkedAgo }}.</div>
        </template>
      </v-tooltip>
    </v-chip>
  </div>
</template>

<script>
import {formatDistanceToNow} from 'date-fns/formatDistanceToNow';
import {delegationSummary, isUnderLocalPublicSuffix} from '@/delegation';

export default {
  name: 'DelegationStatus',
  // The domain list hands every cell field-like attributes (readonly, disabled,
  // listeners); a disabled chip would grey out whenever the app is busy.
  inheritAttrs: false,
  props: {
    modelValue: {
      type: Object,
      default: null,
    },
    domain: {
      type: String,
      required: true,
    },
    checking: {
      type: Boolean,
      default: false,
    },
    suffixes: {
      type: Array,
      default: undefined,  // from the environment
    },
  },
  computed: {
    // Icon only on phones, so that the row's actions stay in view; the label
    // moves into the tooltip.
    compact() {
      return this.$vuetify.display.xs;
    },
    text() {
      return this.checking ? 'Checking…' : this.summary.label;
    },
    isLocal() {
      return isUnderLocalPublicSuffix(this.domain, ...(this.suffixes ? [this.suffixes] : []));
    },
    summary() {
      return delegationSummary(this.modelValue, this.domain);
    },
    checkedAgo() {
      const checked = this.modelValue?.checked;
      return checked ? formatDistanceToNow(new Date(checked), {addSuffix: true}) : '';
    },
  },
};
</script>
