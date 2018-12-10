<template>
  <code>{{ value }}</code>
</template>

<script>
export default {
  name: 'Code',
  props: {
    value: {
      required: true
    }
  }
}
</script>

<style scoped>
</style>
