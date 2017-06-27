Endpoint Reference
------------------

Endpoints related to `User Registration and Management`_ are described in the
`djoser endpoint documentation`_.  The following table summarizes basic
information about the deSEC API endpoints used for `Domain Management`_ and
`Retrieving and Manipulating DNS Information`_.

+------------------------------------------------+------------+---------------------------------------------+
| Endpoint ``/api/v1/domains``...                | Methods    | Use case                                    |
+================================================+============+=============================================+
| ...\ ``/``                                     | ``GET``    | Retrieve all domains owned by you           |
|                                                +------------+---------------------------------------------+
|                                                | ``POST``   | Create a domain                             |
+------------------------------------------------+------------+---------------------------------------------+
| ...\ ``/{domain}/``                            | ``GET``    | Retrieve a specific domain                  |
|                                                +------------+---------------------------------------------+
|                                                | ``PATCH``  | Modify a domain (deprecated)                |
|                                                +------------+---------------------------------------------+
|                                                | ``DELETE`` | Delete a domain                             |
+------------------------------------------------+------------+---------------------------------------------+
| ...\ ``/{domain}/rrsets/``                     | ``GET``    | Retrieve all RRsets from zone               |
|                                                +------------+---------------------------------------------+
|                                                | ``POST``   | Create an RRset                             |
+------------------------------------------------+------------+---------------------------------------------+
| ...\ ``/{domain}/rrsets/{type}/``              | ``GET``    | Retrieve all RRsets of a specific type      |
+------------------------------------------------+------------+---------------------------------------------+
| ...\ ``/{domain}/rrsets/{subname}.../``        | ``GET``    | Retrieve all RRsets with a specific subname |
+------------------------------------------------+------------+---------------------------------------------+
| ...\ ``/{domain}/rrsets/{subname}.../{type}/`` | ``GET``    | Retrieve a specific RRset                   |
|                                                +------------+---------------------------------------------+
|                                                | ``PATCH``  | Modify an RRset                             |
|                                                +------------+---------------------------------------------+
|                                                | ``PUT``    | Replace an RRset                            |
|                                                +------------+---------------------------------------------+
|                                                | ``DELETE`` | Delete an RRset                             |
+------------------------------------------------+------------+---------------------------------------------+
