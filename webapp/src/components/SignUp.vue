<template>
  <v-card flat>
    <v-toolbar flat>
      <v-toolbar-title>Sign up for a new account</v-toolbar-title>
    </v-toolbar>
    <v-card-text>
      <v-form v-model="isvalid">
        <v-text-field
          v-model="email"
          :rules="emailRules"
          label="E-mail"
          required
        ></v-text-field>
        <v-text-field
          v-model="password"
          :append-icon="hide_password ? 'visibility' : 'visibility_off'"
          @click:append="() => (hide_password = !hide_password)"
          :type="hide_password ? 'password' : 'text'"
          label="Enter your password"
          hint="At least 8 characters"
          min="8"
          counter
          required
        ></v-text-field>
        <v-checkbox v-model="ack" required>
          <span slot="label">Yes, I agree to the <a href="/">Terms of Service</a> and <a
            href="/">Privacy Policy</a></span>
        </v-checkbox>
      </v-form>
    </v-card-text>
    <v-progress-linear :indeterminate="true"></v-progress-linear> <!-- if sending -->
    <v-card-actions>
      <v-btn color="primary" id="login-button" :disabled="!isvalid" v-on:click="signup">Sign up</v-btn>
    </v-card-actions>
    <v-card-actions>
      <p style="text-align: center; width: 100%">Already registered?
        <router-link to="/LogIn">Sign in here</router-link>
      </p>
    </v-card-actions>
  </v-card>
</template>

<script>
export default {
  name: 'SignUp',
  data: () => ({
    ack: false,
    email: '',
    emailRules: [
      v => !!v || 'E-mail is required',
      v => /^\w+([.-]?\w+)*@\w+([.-]?\w+)*(\.\w{2,3})+$/.test(v) || 'E-mail must be valid'
    ],
    hide_password: true,
    password: '',
    passwordRules: [
      v => !!v || 'Password is required'
    ],
    isvalid: false
  }),
  methods: {
    signup: function (event) {
      alert('signup')
    }
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
  #login-button {
    width: 100%;
  }
</style>
