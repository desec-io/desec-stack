<template>
  <div
          class="my-1 py-5"
          :title="value"
  >{{ value ? timeAgo.format(new Date(value)) : 'never' }}</div>
</template>

<script>
import { timeAgo } from '@/utils';

export default {
  name: 'TimeAgo',
  props: {
    value: {
      default: '',
      type: String,
    },
  },
  computed: {
    timeAgo() {
      return timeAgo;
    },
  },
};
</script>

<style scoped>
</style>
