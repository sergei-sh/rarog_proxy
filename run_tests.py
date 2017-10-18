
import unittest

from tests.functional import RequestsFunctional
suite = unittest.TestLoader().loadTestsFromTestCase(RequestsFunctional)
unittest.TextTestRunner(verbosity=2).run(suite)


