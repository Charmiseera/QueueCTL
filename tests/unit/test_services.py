import unittest
import os
from src.services.db_service import DB_PATH, get_connection
from src.services.queue_service import set_config, get_config

class TestConfigServices(unittest.TestCase):
    def setUp(self):
        # Drop config table to start fresh
        try:
            with get_connection() as conn:
                conn.execute("DROP TABLE IF EXISTS config;")
                conn.commit()
        except:
            pass

    def tearDown(self):
        self.setUp()

    def test_config_get_set(self):
        set_config("max-retries", 5)
        self.assertEqual(get_config("max-retries"), "5")

        set_config("backoff-base", 3.5)
        self.assertEqual(get_config("backoff-base"), "3.5")

    def test_config_validation(self):
        # max-retries validation
        with self.assertRaises(ValueError):
            set_config("max-retries", -1)
        with self.assertRaises(ValueError):
            set_config("max-retries", "abc")

        # backoff-base validation
        with self.assertRaises(ValueError):
            set_config("backoff-base", 0)
        with self.assertRaises(ValueError):
            set_config("backoff-base", -2.0)
        with self.assertRaises(ValueError):
            set_config("backoff-base", "xyz")

if __name__ == "__main__":
    unittest.main()
