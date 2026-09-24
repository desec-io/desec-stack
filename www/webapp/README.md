# webapp

## Project setup
```
npm install
```

### Compiles and hot-reloads for development
```
npm run dev
```

The webapp is then served at http://localhost:8080/.

### Choosing an API

The webapp calls the API at a relative URL, so the dev server forwards `/api`
to a real API. By default this is the public one at `https://desec.io`, which
means the webapp can be worked on without running desec-stack. Bear in mind
that this is the production service: accounts you register and domains you
create there are real, and it enforces rate limits that a local stack does not.

To use a different API, including your own stack as set up in the top-level
[README](../../README.md), set `DESEC_API_ORIGIN`:
```
DESEC_API_ORIGIN=https://desec.example.dedyn.io npm run dev
```
Certificate verification is skipped for such an origin, since a local stack
usually serves a self-signed certificate. The public API is always verified.

The settings that the production build takes from the environment (nameserver
names, local public suffixes, ...) default to those of the public service, see
`.env.development`. Override them in `.env.local`, which is not tracked by git.

### Compiles and minifies for production
```
npm run build
```

### Lints and fixes files
```
npm run lint
```

### Customize configuration
See [Configuration Reference](https://vitejs.dev/config/).
