<template>
  <span :title="value">{{ timeAgo.format(new Date(value)) }}</span>
</template>

<script>
import { timeAgo } from '@/utils'

export default {
  name: 'TimeAgo',
  props: {
    value: {
      type: String,
      required: true
    }
  },
  computed: {
    timeAgo () {
      return timeAgo
    }
  }
}
</script>

<style scoped>
</style>
