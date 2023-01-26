<template>
  <code>{{ value }}</code>
</template>

<script>
// TODO still required? seems not used.
export default {
  name: 'GenericCode',
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
