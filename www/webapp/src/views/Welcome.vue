<template>
  <v-container
          class="fill-height"
          fluid
  >
    <v-row
            align="center"
            justify="center"
    >
      <v-col
              cols="12"
              sm="8"
              md="6"
      >
        <v-form @submit.prevent="signup" ref="form">
        <v-card class="elevation-12">
          <v-toolbar
                  color="primary"
                  dark
                  flat
          >
            <v-toolbar-title>Welcome to deSEC</v-toolbar-title>
          </v-toolbar>
          <v-card-text>
            <v-alert type="success">
              Thank you for your interest in deSEC.
              To create your deSEC account, please click the verification link in the email that we sent you.
              If you did not receive an email, please check your spam folder or if you already have an account
              by using the <router-link :to="{name: 'reset-password'}">password reset form</router-link>.
            </v-alert>
          </v-card-text>
          <v-card-actions>
            <v-spacer/>
            <v-btn variant="outlined" variant="text" variant="flat" :to="{name: 'home'}">Home</v-btn>
          </v-card-actions>
        </v-card>
        </v-form>
      </v-col>
    </v-row>
  </v-container>
</template>
