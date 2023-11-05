API Versions and Lifecycle
--------------------------

To enable users to build reliable tools on top of the deSEC API, we
maintain stable versions of the API for extended periods of time.

Each API version will advance through the API version lifecycle,
starting from *unstable* and proceeding to *stable*, *deprecated*,
and, finally, to *historical*.

Check out the `current status of the API versions`_ to make sure you
are using the latest stable API whenever using our service in
production.

.. _current status of the API versions: https://github.com/desec-io/desec-stack/#api-versions-and-roadmap

**Unstable API versions** are currently under development and may
change without prior notice, but we promise to keep an eye on users
affected by incompatible changes.

For all **stable API versions**, we guarantee that

1. it will be maintained at least until the end of the given support
   period,

2. there will be no incompatible changes made to the interface, unless
   security vulnerabilities make such changes inevitable,

3. users will be warned before the end of the support period.

**Deprecated API versions** are going to be disabled in the future.
Users will be notified via email and are encouraged to migrate to the
next stable version as soon as possible. For this purpose, a migration
advisory will be provided. After the support period is over, deprecated
API versions may be disabled without further warning and transition to
historical state.

**Historical API versions** are permanently disabled and cannot be used.

