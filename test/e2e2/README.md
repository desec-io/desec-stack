# End-to-End Tests

A collection of tests against the stack written in python and pytest.

## Running

The tests can be run from the **CLI** using

    docker-compose -f docker-compose.yml -f docker-compose.test-e2e2.yml build test-e2e2
    docker-compose -f docker-compose.yml -f docker-compose.test-e2e2.yml up test-e2e2

If you had any changes to other containers (say `api`), then also rebuild them.

To run the test in **pycharm**, make sure that pytest is installed in the Python environment that pycharm is using.
Then add the docker-compose environment to your pycharm build configuration. Note that you need to update the pycharm
environment configuration when you update the corresponding variables in your `.env`.

When run from pycharm, the tests are not run inside a docker container and have no access to any self-signed 
certificates that www may be using. Hence, self-signed certificates cannot be verified when running the tests in 
pycharm. Make sure to use publicly valid certificate!

Note that tests running in pycharm currently have no access to the nslord dns query interface, hence some tests will
fail.

## Troubleshooting

**KeyError: 'content'.** If the content field of captchas is missing, make sure you started the API using the 
configuration of `docker-compose.test-e2e2.yml`.
