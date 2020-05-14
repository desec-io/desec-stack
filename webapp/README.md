# deSEC Frontend

This folder contains the vuejs code for the desec.io domain management frontend.

## Development

To get the frontend up and running locally, all you have to do is:

1. Switch into the webapp folder: `cd webapp`
2. Install the javascript libraries: `npm install`
3. Create the file `.env`:
   ```.env
   VUE_APP_API_BASE_URL = "https://desec.io/api/v1/"
   VUE_APP_LOCAL_PUBLIC_SUFFIXES = dedyn.,
   ```
3. Comment out line 6 in `vue.config.js`: `// public: '...`
4. Run the dev server: `npm run serve`
