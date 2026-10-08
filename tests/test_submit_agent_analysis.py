import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError


path = Path(__file__).resolve().parents[1] / 'scripts/submit_agent_analysis.py'
spec = importlib.util.spec_from_file_location('agent_submit', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Reply:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return json.dumps({'id': 'a' * 64, 'status': 'queued'}).encode()


class SubmitAgentTests(unittest.TestCase):
    def test_retries_the_same_immutable_build_without_following_redirects(self):
        requests = []
        class Opener:
            def open(self, request, timeout):
                requests.append(request)
                if len(requests) == 1:
                    raise HTTPError(request.full_url, 503, 'busy', {}, None)
                return Reply()
        environment = {'AGENT_API_URL': 'http://proxy/test-agent', 'AGENT_API_TOKEN': 'secret',
                       'PR_NUMBER': '31', 'HEAD_SHA': 'f' * 40, 'JOB_NAME': 'pdd/test-all-server', 'BUILD_NUMBER': '7'}
        with patch.dict(module.os.environ, environment), patch.object(module, 'build_opener', return_value=Opener()), patch.object(module.time, 'sleep'):
            result = module.submit()
        self.assertEqual(result['id'], 'a' * 64)
        self.assertEqual(len(requests), 2)
        payload = json.loads(requests[0].data)
        self.assertEqual(payload['build_number'], 7)
        self.assertNotIn('artifact_url', payload)
        self.assertEqual(requests[0].data, requests[1].data)
        self.assertEqual(requests[0].get_header('Authorization'), 'Bearer secret')
        self.assertIsNone(module.NoRedirect().redirect_request(None, None, 302, '', {}, 'http://other'))


if __name__ == '__main__':
    unittest.main()
