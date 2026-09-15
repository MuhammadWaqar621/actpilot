import time

FREE_MESSAGE_LIMIT = 50
WINDOW_SECONDS = 2 * 60 * 60

# In-memory only: fine for a single local backend process. Resets if the
# backend restarts - a real multi-instance deployment would need this in
# Redis or a DB instead, keyed the same way (by client IP for now, since
# there's no user account system yet).
#
# On Vercel specifically: each serverless function invocation may land on a
# different warm/cold instance, and this dict is process-local, so the
# 50-msgs/2h cap is NOT reliably enforced there - a user can get closer to
# (instances * 50) messages before every instance's counter agrees they're
# over, and a cold start silently resets an instance's count to zero. This
# is a soft, best-effort usage cap (per README: "no real account/billing
# system yet", CORS is "*" and IP-based limiting is explicitly the closest
# thing to access control here) rather than a hard security boundary
# protecting sensitive data or paid actions, so this file is intentionally
# left as-is rather than rewritten onto Redis/Upstash/a DB - flagging it
# here so a real distributed store gets swapped in before this limit is
# relied on for anything stricter than "keep casual abuse down."
_usage: dict[str, tuple[int, float]] = {}


def check_and_increment(client_ip: str) -> tuple[bool, int, int]:
    """Returns (allowed, remaining, reset_in_seconds). Increments the
    counter only when the request is allowed through."""
    now = time.monotonic()
    count, window_start = _usage.get(client_ip, (0, now))

    if now - window_start >= WINDOW_SECONDS:
        count, window_start = 0, now

    reset_in = int(WINDOW_SECONDS - (now - window_start))

    if count >= FREE_MESSAGE_LIMIT:
        return False, 0, reset_in

    _usage[client_ip] = (count + 1, window_start)
    return True, FREE_MESSAGE_LIMIT - (count + 1), reset_in
