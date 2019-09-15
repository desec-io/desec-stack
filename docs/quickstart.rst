Quickstart
----------

To use our domain management API, you need to register an account with deSEC.
Here's a quick intro how to get started:

#. `Obtain a captcha`_ and solve it::

    curl -X POST https://desec.io/api/v1/captcha/

   Note down the captcha ID from the response body, and figure out the
   solution from the ``challenge`` field. It's a base64-encoded PNG image
   which you can display by directing your browser to the URL
   ``data:image/png;base64,<challenge>``, after replacing ``<challenge>`` with
   the value of the ``challenge`` response field

#. `Register account`_::

    curl -X POST https://desec.io/api/v1/auth/ \
        --header "Content-Type: application/json" --data @- <<EOF
        {
          "email": "youremailaddress@example.com",
          "password": "yourpassword",
          "captcha": {
            "id": "00010203-0405-0607-0809-0a0b0c0d0e0f",
            "solution": "12H45"
          }
        }
    EOF

   Before activating your account, we need to verify your email address. To
   that end, we will send you an email, containing a validation link of the
   form ``https://desec.io/api/v1/v/activate-account/<code>/``. To confirm
   your address and activate your account, simply click the link.


#. `Log in`_::

    curl -X POST https://desec.io/api/v1/auth/login/ \
        --header "Content-Type: application/json" --data @- <<< \
        '{"email": "youremailaddress@example.com", "password": "yourpassword"}'

   The response body will contain an ``auth_token`` which is used to
   authenticate requests to the DNS management endpoints as demonstrated in
   the next step.

#. Create a DNS zone::

    curl -X POST https://desec.io/api/v1/domains/ \
        --header "Authorization: Token {token}" \
        --header "Content-Type: application/json" --data @- <<< \
        '{"name": "example.com"}'

#. Yay! Keep browsing the `Domain Management`_ section of the docs to see how
   to continue.
