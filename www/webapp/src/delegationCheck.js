// Asking for a domain's delegation to be re-checked, and waiting for the
// result. See docs/design-plans/PLAN-delegation_status.md §4.4.

// Seconds between polls, then every POLL_INTERVAL, for at most POLL_TIMEOUT.
// A check usually takes a few seconds; one stuck behind slow parent
// nameservers can take half a minute.
export const POLL_DELAYS = [2, 3, 5, 8, 13];
export const POLL_INTERVAL = 15;
export const POLL_TIMEOUT = 90;

const defaultSleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function* delays() {
  let elapsed = 0;
  for (const delay of POLL_DELAYS) {
    elapsed += delay;
    if (elapsed > POLL_TIMEOUT) {
      return;
    }
    yield delay;
  }
  while (elapsed + POLL_INTERVAL <= POLL_TIMEOUT) {
    elapsed += POLL_INTERVAL;
    yield POLL_INTERVAL;
  }
}

/**
 * Asks for the domain to be re-checked, and waits for the result.
 *
 * Resolves to {status, done}: done is true when status holds the result (or,
 * for a 200, when the API answered from what it already knew), and false when
 * the check is still outstanding after POLL_TIMEOUT, or when shouldStop()
 * returned true. A check that is lost on the server (our resolver being down)
 * looks the same as a slow one, so there is no more to say than that.
 *
 * Request errors (e.g. 429, 503) are not caught.
 *
 * @param http - an axios instance whose base URL is the API
 * @param {string} name - the domain name
 * @param {object} [options]
 * @param {function(object): void} [options.onRequested] - called with the
 *   current status once a check is under way
 * @param {function(): boolean} [options.shouldStop] - polled before each
 *   request; stops waiting when true (e.g. once the page is left)
 * @param {function(number): Promise} [options.sleep] - for tests
 */
export async function recheckDelegation(http, name, {onRequested, shouldStop = () => false, sleep = defaultSleep} = {}) {
  const url = `domains/${name}/status/`;
  const response = await http.post(url);
  const {requested, ...current} = response.data;
  if (response.status !== 202) {
    return {status: current, done: true};
  }
  onRequested?.(current);

  // requested is the server's time, so no clock comparison across machines.
  const requestedAt = new Date(requested);
  for (const delay of delays()) {
    await sleep(delay * 1000);
    if (shouldStop()) {
      break;
    }
    const {data} = await http.get(url);
    if (data.checked && new Date(data.checked) >= requestedAt) {
      return {status: data, done: true};
    }
  }
  return {status: current, done: false};
}
