import importlib.util
import pathlib
import unittest

MODULE_PATH=pathlib.Path(__file__).with_name("verify_live_v117.py")
spec=importlib.util.spec_from_file_location("verify_live_v117",MODULE_PATH)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class LivePublicPageIntegrityTests(unittest.TestCase):
    def test_identical_document_passes(self):
        original=b"<!doctype html><html><body>published</body></html>"
        self.assertTrue(module.verify_http_response(original,original))
    def test_changed_deployed_document_blocks(self):
        original=b"<!doctype html><html><body>original</body></html>"
        changed=b"<!doctype html><html><body>changed</body></html>"
        with self.assertRaises(ValueError):
            module.verify_http_response(changed,original)
    def test_big_document_blocks(self):
        with self.assertRaises(ValueError):
            module.verify_http_response(b"<!doctype html>"+b"x"*module.LIMIT,b"<!doctype html>"+b"x"*module.LIMIT)
    def test_non_html_payload_blocks(self):
        with self.assertRaises(ValueError):
            module.verify_http_response(b"\x00" * 100,b"\x00" * 100)
if __name__=="__main__":
    unittest.main()
