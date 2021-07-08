.. _rate-limits:

Rate Limits
-----------

The API implements rate limits to prevent brute force attacks on passwords, to
ensure that the system load remains manageable, to avoid update rejections due
to concurrent DNS updates on the same domain etc.

Rate limits apply per account and are enforced in a sliding-window fashion.
For throttled requests, the server will return status ``429 Too Many
Requests`` and give a human-readable explanation in the response body,
including how long to wait before making another request.  The number of
seconds after which the next request will be allowed is also given by the
``Retry-After`` header.

**Example:** If the rate is 10/min and you make a request every second, the
11th request will be rejected.  You will then have to wait for 50 seconds,
until the first request's age reaches one minute.  At that time, it will be
dropped from the calculation, and you can make another request.  One second
later, and generally every time an old request's age falls out of the
counting interval, you can make another request.

The following table summarizes the rate limits pertaining to various parts of
the API.  When several rates are given, all are enforced at the same time.

+--------------------------------+----------+-------------------------------------------------------------------------------------------+
| Rate limit name                | Rate     | Affected operations                                                                       |
+================================+==========+===========================================================================================+
| ``account_management_active``  | 3/min    | Account activities with external effects (e.g. sending email)                             |
+--------------------------------+----------+-------------------------------------------------------------------------------------------+
| ``account_management_passive`` | 10/min   | Account activities with internal effects (e.g. viewing account details, creating a token) |
+--------------------------------+----------+-------------------------------------------------------------------------------------------+
| ``dyndns``                     | 1/min    | dynDNS updates (per domain).  If you need to keep subdomains in sync, consider setting up |
|                                |          | a ``CNAME`` redirect in our web interface.                                                |
+--------------------------------+----------+-------------------------------------------------------------------------------------------+
| ``dns_api_read``               | 10/s     | DNS read operations (e.g. fetching an RRset)                                              |
|                                |          |                                                                                           |
|                                | 50/min   |                                                                                           |
+--------------------------------+----------+-------------------------------------------------------------------------------------------+
| ``dns_api_write_domains``      | 10/s     | DNS write operations: domain creation/deletion                                            |
|                                |          |                                                                                           |
|                                | 300/min  |                                                                                           |
|                                |          |                                                                                           |
|                                | 1000/h   |                                                                                           |
+--------------------------------+----------+-------------------------------------------------------------------------------------------+
| ``dns_api_write_rrsets``       | 2/s      | DNS write operations: RRset creation/deletion/modification (per domain).  If you require  |
|                                |          | more requests, consider using bulk requests.                                              |
|                                | 15/min   |                                                                                           |
|                                |          |                                                                                           |
|                                | 30/h     |                                                                                           |
|                                |          |                                                                                           |
|                                | 300/day  |                                                                                           |
+--------------------------------+----------+-------------------------------------------------------------------------------------------+
| ``user``                       | 2000/day | Any activity of a) authenticated users, b) unauthenticated users (by IP)                  |
+--------------------------------+----------+-------------------------------------------------------------------------------------------+
