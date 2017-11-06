'''
Factory to instanciate right API class
'''

from poloniexlendingbot.Poloniex import Poloniex
from poloniexlendingbot.Bitfinex import Bitfinex

EXCHANGE = {'POLONIEX': Poloniex, 'BITFINEX': Bitfinex}


class ExchangeApiFactory(object):
    @staticmethod
    def createApi(exchange, cfg, log):
        if exchange not in EXCHANGE:
            raise Exception("Invalid exchange: " + exchange)
        return EXCHANGE[exchange](cfg, log)
