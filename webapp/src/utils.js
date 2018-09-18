import axios from 'axios'
import TimeAgo from 'javascript-time-ago'
import en from 'javascript-time-ago/locale/en'

export const HTTP = axios.create({
  baseURL: '/api/v1/',
  headers: {
  }
})

TimeAgo.locale(en)
export const timeAgo = new TimeAgo()
