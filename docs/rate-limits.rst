.. _rate-limits:

Rate Limits
-----------

The API implements rate limits to prevent brute force attacks on passwords, to
ensure that the system load remains manageable, to avoid update rejections due
to concurrent DNS updates on the same domain etc.

Rate limits apply per account.  The following table summarizes the rate limits
pertaining to various parts of the API.  When several rates are given, all are
enforced at the same time.  For throttled requests, the server will respond
with ``429 Too Many Requests``.


+--------------------------------+----------+-------------------------------------------------------------------------------------------+
| Rate limit name                | Rate     | Affected operations                                                                       |
+================================+==========+===========================================================================================+
| ``account_management_active``  | 3/min    | Account activities with external effects (e.g. sending email)                             |
+--------------------------------+----------+-------------------------------------------------------------------------------------------+
| ``account_management_passive`` | 10/min   | Account activities with internal effects (e.g. viewing account details, creating a token) |
+--------------------------------+----------+-------------------------------------------------------------------------------------------+
| ``dyndns``                     | 1/min    | dynDNS updates                                                                            |
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
|                                | 100/day  |                                                                                           |
+--------------------------------+----------+-------------------------------------------------------------------------------------------+
| ``user``                       | 2000/day | Any activity of a) authenticated users, b) unauthenticated users (by IP)                  |
+--------------------------------+----------+-------------------------------------------------------------------------------------------+
