<template>
  <v-container>
    <h1>Impressum / Legal Notice</h1>

    <h2>Angaben gemäß § 5 TMG</h2>
    <p>deSEC e.V.</p>
    <h3>Postanschrift / Address</h3>
    <p>Kyffhäuserstr. 5<br>10781 Berlin</p>
    <h3>E-Mail</h3>
    <p>{{email}}</p>
    <h3>Vertreten durch / Represented by</h3>
    <p>Nils Wisiol
      <br>Wolfgang Studier
      <br>Dr. Peter Thomassen</p>
    <h3>Registergericht / Registration court</h3>
    <p>AG Berlin (Charlottenburg)<br>VR 37525<br></p>
  </v-container>
</template>

<script>
  import {EMAIL} from '../env';
  export default {
    name: 'Impressum',
    data: () => ({
      email: EMAIL,
    }),
  }
</script>
