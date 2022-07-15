<template>
  <code>{{ value }}</code>
</template>

<script>
export default {
  name: 'Code',
  props: {
    value: {
      type: String,
      required: true,
    },
  },
};
</script>

<style scoped>
</style>
