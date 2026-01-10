<template>
  <div class="delegation-status">
    <v-chip
      :color="status.color"
      size="small"
      variant="flat"
      class="mb-1"
    >
      {{ status.label }}
    </v-chip>
    <div class="delegation-hint text-caption text-medium-emphasis">
      {{ status.hint }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'DelegationStatus',
  emits: ['update:modelValue'],
  props: {
    modelValue: {
      type: [String, Number, Date],
      default: null,
    },
    item: {
      type: Object,
      required: true,
    },
  },
  computed: {
    status() {
      const domain = this.item || {};
      if (!domain.delegation_checked) {
        return {
          label: 'Checking',
          color: 'grey-lighten-2',
          hint: 'We are checking how this domain is published on the Internet.',
        };
      }
      if (domain.is_registered === false) {
        return {
          label: 'Not visible in DNS',
          color: 'grey-lighten-1',
          hint: 'Your registrar has not published this domain yet.',
        };
      }
      if (domain.is_delegated == null) {
        return {
          label: 'Not delegated to deSEC',
          color: 'red-lighten-1',
          hint: 'Update the nameservers at your registrar to use deSEC.',
        };
      }
      if (domain.is_delegated === false) {
        return {
          label: 'Partially delegated',
          color: 'orange-lighten-1',
          hint: 'Some nameservers do not point to deSEC. Use only deSEC nameservers.',
        };
      }
      if (domain.is_secured === true) {
        return {
          label: 'Delegation secured',
          color: 'green-lighten-1',
          hint: 'DNSSEC is active and correctly configured.',
        };
      }
      if (domain.is_secured === false) {
        return {
          label: 'DNSSEC mismatch',
          color: 'orange-lighten-1',
          hint: 'Update the DS records at your registrar to match deSEC.',
        };
      }
      return {
        label: 'Delegated without DNSSEC',
        color: 'orange-lighten-1',
        hint: 'Add the DS records at your registrar to secure this domain.',
      };
    },
  },
};
</script>

<style scoped>
.delegation-status {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.delegation-hint {
  max-width: 320px;
}
</style>
