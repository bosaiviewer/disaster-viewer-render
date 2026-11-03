import unittest
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests',pattern='test_cloud56.py')).wasSuccessful())
