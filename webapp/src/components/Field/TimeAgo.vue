<template>
  <div
          class="my-1 py-5"
          :title="value"
  ><timeago v-if="value" :datetime="value"></timeago><span v-else>never</span></div>
</template>

<script>
export default {
  name: 'TimeAgo',
  props: {
    value: {
      default: '',
      type: String,
    },
  },
};
</script>

<style scoped>
</style>
