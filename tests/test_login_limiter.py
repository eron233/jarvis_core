import unittest
from concurrent.futures import ThreadPoolExecutor
from security.login_limiter import LoginLimiter


class LoginLimiterTests(unittest.TestCase):
    def test_window_and_capacity(self):
        now = [0.0]
        limiter = LoginLimiter(2, 60, lambda: now[0])
        self.assertTrue(limiter.reserve())
        self.assertTrue(limiter.reserve())
        self.assertFalse(limiter.reserve())
        now[0] = 59
        self.assertFalse(limiter.reserve())
        now[0] = 60
        self.assertTrue(limiter.reserve())

    def test_concurrent_requests_respect_capacity(self):
        limiter = LoginLimiter(10, 60, lambda: 0.0)
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(lambda _: limiter.reserve(), range(100))), 10)
