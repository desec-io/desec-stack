<template>
  <v-container>
    <h1>Impressum / Legal Notice</h1>

    <h2>Angaben gemäß § 5 TMG</h2>
    <p>deSEC e.V.</p>
    <h3>Postanschrift / Address</h3>
    <p>Möckernstraße 74<br/>10965 Berlin</p>
    <h3>E-Mail</h3>
    <p>{{ email }}</p>
    <h3>Vertreten durch / Represented by</h3>
    <p>
      Dr. Nils Wisiol<br>
      Dr. Peter Thomassen<br>
      Wolfgang Studier
    </p>
    <h3>Registration and Tax Information (Gemeinnützigkeit / Charitable Status)</h3>
    <p>
      Registergericht / Registration court: AG Berlin (Charlottenburg), VR 37525<br>
      Steuernummer / Tax number: 27/663/65101, UStID-Nr.: DE363934139
    </p>
    <p>
      Der Verein wurde vom Finanzamt für Körperschaften I, Berlin, als gemeinnützig anerkannt
      (Freistellungsbescheid vom 01.11.2019, seitdem aktualisiert).
    </p>
    <p>
      The organization has been recognized as charitable by the competent tax office
      (Finanzamt für Körperschaften I, Berlin; exemption notice dated November 1, 2019, since renewed).
    </p>
  </v-container>
</template>

<script>
  export default {
    name: 'ImpressumPage',
    data: () => ({
      email: import.meta.env.VITE_APP_EMAIL,
    }),
  }
</script>
