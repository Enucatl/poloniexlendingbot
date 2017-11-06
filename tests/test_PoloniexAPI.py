import time

# Hack to get relative imports - probably need to fix the dir structure instead but we need this at the minute for
# pytest to work
import os, sys, inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

from poloniexlendingbot.Poloniex import Poloniex
import poloniexlendingbot.Configuration as Config
import poloniexlendingbot.Data as Data
from poloniexlendingbot.Logger import Logger
import threading

Config.init('default.cfg', Data)
api = Poloniex(Config, Logger())


def api_rate_limit(n, start):
    api.limit_request_rate()
    # verify that the (N % 6) th request is delayed by (N / 6) sec from the start time
    if n != 0 and n % 6 == 0:
        print 'limit request ' + str(n) + ' ' + str(start) + ' ' + str(time.time()) + '\n'
        assert time.time() - start >= int(n / 6), "rate limit failed"


# Test rate limiter
def test_rate_limiter():
    start = time.time()
    for i in xrange(20):
        thread1 = threading.Thread(target=api_rate_limit, args=(i, start))
        thread1.start()
