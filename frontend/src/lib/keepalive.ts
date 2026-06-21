/**
 * Pings the backend every 10 minutes to prevent Render free tier sleep.
 */
export function startKeepAlive() {
  const ping = () => {
    fetch("https://opensync-api.onrender.com/health").catch(() => {});
  };

  // Ping immediately
  ping();

  // Then every 10 minutes
  setInterval(ping, 10 * 60 * 1000);
}