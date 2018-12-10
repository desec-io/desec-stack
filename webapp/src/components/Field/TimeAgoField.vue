<template>
  <span :title="value">{{ timeAgo.format(new Date(value)) }}</span>
</template>

<script>
import { timeAgo } from '@/utils'

export default {
  name: 'TimeAgoField',
  computed: {
    timeAgo () {
      return timeAgo
    }
  }
}
</script>

<style scoped>
</style>
