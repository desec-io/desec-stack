// Asking for a domain's delegation to be re-checked, and waiting for the
// result. See docs/design-plans/PLAN-delegation_status.md §4.4.

// Seconds between polls, then every POLL_INTERVAL, for at most POLL_TIMEOUT.
// A check usually takes a few seconds; one stuck behind slow parent
// nameservers can take half a minute.
export const POLL_DELAYS = [2, 3, 5, 8, 13];
export const POLL_INTERVAL = 15;
export const POLL_TIMEOUT = 90;

const defaultSleep = ms => new Promise(resolve => setTimeout(resolve, ms));

// Seconds after the request at which to poll.
function pollTimes() {
  const times = [];
  let at = 0;
  for (const delay of POLL_DELAYS) {
    at += delay;
    times.push(at);
  }
  while (at + POLL_INTERVAL <= POLL_TIMEOUT) {
    at += POLL_INTERVAL;
    times.push(at);
  }
  return times.filter(time => time <= POLL_TIMEOUT);
}

// Seconds to wait as told by a 429 response, if it says.
function retryAfter(response) {
  const seconds = Number.parseInt(response.headers?.['retry-after'], 10);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

/**
 * Asks for the domain to be re-checked, and waits for the result.
 *
 * Resolves to {status, done}: done is true when status holds the result (or,
 * for a 200, when the API answered from what it already knew), and false when
 * the check is still outstanding after POLL_TIMEOUT, or when shouldStop()
 * returned true. A check that is lost on the server (e.g. with the worker
 * down) looks the same as a slow one, so there is no more to say than that.
 *
 * Errors of the re-check request (e.g. 429, 503) are passed on. Polls count
 * against the API's rate limit for reading, which several re-checks at once
 * can reach; a throttled poll is repeated once the API allows it, within
 * POLL_TIMEOUT. Other polling errors are passed on.
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
  const times = pollTimes();
  let elapsed = 0;
  let at = times[0];
  while (at !== undefined && at <= POLL_TIMEOUT) {
    await sleep((at - elapsed) * 1000);
    elapsed = at;
    if (shouldStop()) {
      break;
    }
    let data;
    try {
      ({data} = await http.get(url));
    } catch (e) {
      if (e.response?.status !== 429) {
        throw e;
      }
      at = elapsed + (retryAfter(e.response) ?? POLL_INTERVAL);
      continue;
    }
    if (data.checked && new Date(data.checked) >= requestedAt) {
      return {status: data, done: true};
    }
    at = times.find(time => time > elapsed);
  }
  return {status: current, done: false};
}
