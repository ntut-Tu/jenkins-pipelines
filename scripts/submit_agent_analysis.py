"""Deliver an immutable Jenkins build to the Agent controller, with safe retries."""

import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, new_url):
        return None


def submit() -> dict:
    """POST once logically; repeated delivery reuses the controller's job identity."""
    endpoint = os.environ['AGENT_API_URL'].rstrip('/')
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Invalid AGENT_API_URL')
    payload = {
        'provider': 'github', 'repository': 'ntut-Tu/cloth_shop_server',
        'number': int(os.environ['PR_NUMBER']), 'head_sha': os.environ['HEAD_SHA'],
        'job_name': os.environ['JOB_NAME'], 'build_number': int(os.environ['BUILD_NUMBER']),
    }
    request = Request(endpoint + '/analyses', data=json.dumps(payload).encode(), headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + os.environ['AGENT_API_TOKEN'],
    })
    opener = build_opener(NoRedirect())
    for attempt in range(3):
        try:
            with opener.open(request, timeout=20) as response:
                result = json.loads(response.read())
            if not isinstance(result, dict) or not re.fullmatch(r'[a-f0-9]{64}', result.get('id', '')):
                raise ValueError('Invalid controller receipt')
            return result
        except HTTPError as error:
            if error.code not in {429, 502, 503, 504} or attempt == 2:
                raise RuntimeError(f'Agent controller returned HTTP {error.code}') from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError('Agent controller is unreachable') from None
        time.sleep(2 ** attempt)
    raise RuntimeError('Agent delivery failed')


if __name__ == '__main__':
    try:
        receipt = submit()
        Path('agent-analysis/controller-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(f"[PASS] Agent analysis accepted: {receipt['id']} ({receipt['status']})")
    except (KeyError, ValueError, RuntimeError) as error:
        # Do not print request headers, tokens or remote response bodies.
        raise SystemExit(f'[FAIL] {error}') from None
