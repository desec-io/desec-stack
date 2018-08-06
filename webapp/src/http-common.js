import axios from 'axios'

export const HTTP = axios.create({
  baseURL: '/api/v1/',
  headers: {
    Authorization: 'Token 0b4ea7ea0f05ead0baa0d5045cd165a269f4d870'
  }
})
