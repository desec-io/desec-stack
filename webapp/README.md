# deSEC Webapp

This folder contains the Vue.js code for the desec.io domain management webapp.

## Development

To get the frontend up and running locally, all you have to do is:

1. Switch into the webapp folder: `cd webapp`
2. Install the javascript libraries: `npm install`
3. Create the file `.env`:
   ```.env
   VUE_APP_API_BASE_URL = "https://desec.io/api/v1/"
   VUE_APP_LOCAL_PUBLIC_SUFFIXES = dedyn.,
   ```
4. **Optional**: To have hot reload work correctly, comment out line 6 in `vue.config.js`: `// public: '...`
5. Run the dev server: `npm run serve`
