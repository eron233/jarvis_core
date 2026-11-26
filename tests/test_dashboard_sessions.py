import unittest
from security.dashboard_sessions import DashboardSessions


class DashboardSessionTests(unittest.TestCase):
    def test_expiry_and_revocation(self):
        now = [10.0]
        store = DashboardSessions(ttl_seconds=5, clock=lambda: now[0])
        binding = ("trusted", "secret")
        token = store.issue("owner", "trusted_device", binding)
        self.assertEqual(store.resolve(token, binding).device_id, "owner")
        now[0] = 15
        self.assertIsNone(store.resolve(token, binding))
        token = store.issue("owner", "trusted_device", binding)
        store.revoke(token)
        self.assertIsNone(store.resolve(token, binding))

    def test_distinct_tokens_and_credential_rotation(self):
        store = DashboardSessions()
        a = store.issue("owner", "trusted_device", ("old",))
        b = store.issue("owner", "trusted_device", ("old",))
        self.assertNotEqual(a, b)
        self.assertIsNone(store.resolve(a, ("new",)))
        self.assertIsNone(store.resolve(a, ("old",)))
        self.assertIsNotNone(store.resolve(b, ("old",)))

    def test_capacity_restart_and_invalid_input(self):
        store = DashboardSessions(capacity=1)
        first = store.issue("owner", "trusted_device", ("x",))
        second = store.issue("owner", "trusted_device", ("x",))
        self.assertIsNone(store.resolve(first, ("x",)))
        self.assertIsNotNone(store.resolve(second, ("x",)))
        self.assertIsNone(DashboardSessions().resolve(second, ("x",)))
        for token in (None, "", "é" * 43, "x" * 10000):
            self.assertIsNone(store.resolve(token, ("x",)))
