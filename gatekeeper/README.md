gatekeeper
==========

The `api` asks this service what to do about requests it does not want to decide on its own,
currently account registrations. The service runs outside the API's trust boundary: it is reachable
from `api` only, has no access to the database or to any other part of the stack, and the API takes
nothing from it but a verdict. It does reach the internet, through the NAT of the bridge network it
shares with `api`, so that an arbiter can consult outside data sources; mind that the facts it is
given include the prospective user's email address, IP address and user agent.

Interface
---------

The API sends a `POST` request to `http://gatekeeper:8000/`, carrying a JSON object that describes
the request it has received:

    {
      "event": "account_create",
      "email": "youremailaddress@example.com",
      "ip": "203.0.113.7",
      "user_agent": "curl/8.5.0",
      "domain": "example.org",
      "captcha_solved": true
    }

`event` is always present; the remaining facts depend on the event, and more may be added over
time. `ip` is the client address as seen by `www` (it cannot be spoofed through headers), `domain`
is the domain name requested along with the account, if any, and `captcha_solved` says whether the
registration came with a valid captcha solution.

The response is a JSON object with a `verdict`:

    {"verdict": "allow", "reason": "..."}

- `allow`: the API processes the request as usual.
- `drop`: the API discards the request. The client receives the response it would have received
  otherwise, so that a registration attempt reveals nothing about the address it used.
- `reject`: the API denies the request and tells the client so.

The optional `reason` is logged by the API, but never disclosed to the client.

Failure to obtain a verdict — service down, timeout, or an answer the API cannot make sense of —
allows the request. Gatekeeping is an abuse control, not an authorization mechanism, and an arbiter
that is unavailable must not take registrations down with it.

Replacing this arbiter
----------------------

The interface above is the contract; everything behind it is up to the operator. Point the
`gatekeeper` service in `docker-compose.yml` at your own image to apply your own rules, using
whatever data sources you like — the API neither knows nor cares.

Tests
-----

    python3 -m unittest discover -s gatekeeper -v
