import axios from 'axios'

export const HTTP = axios.create({
  baseURL: '/api/v1/',
  headers: {
  }
})
