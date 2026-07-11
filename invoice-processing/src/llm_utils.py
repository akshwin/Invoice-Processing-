"""Shared retry helper for Groq API calls.

Both the extraction and reasoning calls hit the same two transient failure modes:
rate limiting, and occasional malformed tool-call generations (a known flakiness in
hosted open-weight function-calling — the model produces a slightly malformed
function-call token stream that Groq's parser rejects as `tool_use_failed`; re-running
the identical request typically succeeds on the next sampling attempt).
"""
import time

import groq

MAX_RETRIES = 3


def call_with_retry(fn):
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn()
        except groq.RateLimitError as e:
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                retry_after = getattr(e, "response", None) and e.response.headers.get("retry-after")
                delay = min(float(retry_after), 15) if retry_after else 2 * (attempt + 1)
                time.sleep(delay)
                continue
            raise
        except groq.BadRequestError as e:
            last_exc = e
            if "tool_use_failed" in str(e) and attempt < MAX_RETRIES - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise
    raise last_exc
