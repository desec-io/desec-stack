Endpoint Reference
------------------

Endpoints related to `User Registration and Management`_ are described in the
`djoser endpoint documentation`_.  The following table summarizes basic
information about the deSEC API endpoints used for `Domain Management`_ and
`Retrieving and Manipulating DNS Information`_.

+------------------------------------------------+------------+---------------------------------------------+
| Endpoint ``/api/v1/domains``...                | Methods    | Use case                                    |
+================================================+============+=============================================+
| ...\ ``/``                                     | ``GET``    | Retrieve all domains you own                |
|                                                +------------+---------------------------------------------+
|                                                | ``POST``   | Create a domain                             |
+------------------------------------------------+------------+---------------------------------------------+
| ...\ ``/{domain}/``                            | ``GET``    | Retrieve a specific domain                  |
|                                                +------------+---------------------------------------------+
|                                                | ``PATCH``  | Modify a domain (deprecated)                |
|                                                +------------+---------------------------------------------+
|                                                | ``DELETE`` | Delete a domain                             |
+------------------------------------------------+------------+---------------------------------------------+
| ...\ ``/{domain}/rrsets/``                     | ``GET``    | Retrieve all RRsets from ``domain``, filter |
|                                                |            | by ``subname`` or ``type`` query parameter  |
|                                                +------------+---------------------------------------------+
|                                                | ``POST``   | Create one or more RRsets                   |
|                                                +------------+---------------------------------------------+
|                                                | ``PATCH``  | Create, modify or delete one or more RRsets |
|                                                +------------+---------------------------------------------+
|                                                | ``PUT``    | Create, modify or delete one or more RRsets |
+------------------------------------------------+------------+---------------------------------------------+
| ...\ ``/{domain}/rrsets/{subname}.../{type}/`` | ``GET``    | Retrieve a specific RRset                   |
|                                                +------------+---------------------------------------------+
|                                                | ``PATCH``  | Modify an RRset                             |
|                                                +------------+---------------------------------------------+
|                                                | ``PUT``    | Replace an RRset                            |
|                                                +------------+---------------------------------------------+
|                                                | ``DELETE`` | Delete an RRset                             |
+------------------------------------------------+------------+---------------------------------------------+
