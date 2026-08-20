import { io } from "socket.io-client";
import { socketio_port } from "../../../../sites/common_site_config.json";

// extend window object
declare global {
  interface Window {
    site_name: string;
  }
}

export function initSocket() {
  let host = window.location.hostname;
  let siteName = window.site_name || host;
  let port = window.location.port ? `:${socketio_port}` : "";
  let protocol = port ? "http" : "https";
  let url = `${protocol}://${host}${port}/${siteName}`;

  const socket = io(url, {
    withCredentials: true,
    // PYEK: this used to be `reconnectionAttempts: 5`, and five attempts on the
    // default backoff is about fifteen seconds. After that socket.io gives up
    // FOR THE LIFE OF THE PAGE — silently. A sleeping laptop, a wifi hop, a
    // locked phone or one of our own deploys was enough to permanently kill
    // every realtime feature on that tab: the Tickets list stopped refreshing
    // (its only trigger is the "helpdesk:new-ticket" event), and an SOS could
    // no longer reach that desk. The page looked completely normal throughout.
    // Diagnosed 2026-08-20 from ticket 0493, which was created 13s after its
    // email arrived and did not appear in Mark's open list for four hours.
    // Retry forever instead, and cap the backoff so a long outage doesn't leave
    // us waiting minutes to notice the site came back.
    reconnectionAttempts: Infinity,
    reconnectionDelayMax: 10_000,
  });

  return socket;
}

export const socket = initSocket();
