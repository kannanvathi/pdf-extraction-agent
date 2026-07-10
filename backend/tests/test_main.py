import unittest

from fastapi.testclient import TestClient

from backend.main import app


class MainAppTests(unittest.TestCase):
    def test_root_endpoint_returns_healthy_status(self):
        with TestClient(app) as client:
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
