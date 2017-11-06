import click
import os
import sys
import time
import traceback
from decimal import Decimal
from http.client import BadStatusLine
from urllib.error import URLError

import poloniexlendingbot.Configuration as Config
import poloniexlendingbot.Data as Data
import poloniexlendingbot.Lending as Lending
import poloniexlendingbot.MaxToLend as MaxToLend
from poloniexlendingbot.Logger import Logger
import poloniexlendingbot.PluginsManager as PluginsManager
from poloniexlendingbot.ExchangeApiFactory import ExchangeApiFactory
from poloniexlendingbot.ExchangeApi import ApiError


@click.command()
@click.option(
    "-c", 
    "--config",
    default="default.cfg",
    type=click.File(),
    help="Location of custom configuration file, overrides settings below")
@click.option("-d", "--dryrun", is_flag=True, help="Make fake orders")
def main(config, dryrun):
    Config.init(config)

    output_currency = Config.get('BOT', 'outputCurrency', 'BTC')
    end_date = Config.get('BOT', 'endDate')
    exchange = Config.get_exchange()

    json_output_enabled = Config.has_option('BOT', 'jsonfile') and Config.has_option('BOT', 'jsonlogsize')
    jsonfile = Config.get('BOT', 'jsonfile', '')

    # Configure web server
    web_server_enabled = Config.getboolean('BOT', 'startWebServer')
    if web_server_enabled:
        if json_output_enabled is False:
            # User wants webserver enabled. Must have JSON enabled. Force logging with defaults.
            json_output_enabled = True
            jsonfile = Config.get('BOT', 'jsonfile', 'www/botlog.json')

        import poloniexlendingbot.WebServer as WebServer
        WebServer.initialize_web_server(Config)

    # Configure logging
    log = Logger(jsonfile, Decimal(Config.get('BOT', 'jsonlogsize', 200)), exchange)

    # initialize the remaining stuff
    api = ExchangeApiFactory.createApi(exchange, Config, log)
    MaxToLend.init(Config, log)
    Data.init(api, log)
    Config.init(config, Data)
    notify_conf = Config.get_notification_config()
    if Config.has_option('MarketAnalysis', 'analyseCurrencies'):
        from poloniexlendingbot.MarketAnalysis import MarketAnalysis
        # Analysis.init(Config, api, Data)
        analysis = MarketAnalysis(Config, api)
        analysis.run()
    else:
        analysis = None
    Lending.init(Config, api, log, Data, MaxToLend, dryrun, analysis, notify_conf)

    # load plugins
    PluginsManager.init(Config, api, log, notify_conf)

    print('Welcome to ' + Config.get("BOT", "label", "Lending Bot") + ' on '
          + exchange)

    try:
        while True:
            try:
                Data.update_conversion_rates(output_currency, json_output_enabled)
                PluginsManager.before_lending()
                Lending.transfer_balances()
                Lending.cancel_all()
                Lending.lend_all()
                PluginsManager.after_lending()
                log.refreshStatus(Data.stringify_total_lent(*Data.get_total_lent()),
                                Data.get_max_duration(end_date, "status"))
                log.persistStatus()
                sys.stdout.flush()
                time.sleep(Lending.get_sleep_time())
            except KeyboardInterrupt:
                # allow existing the main bot loop
                raise
            except BadStatusLine:
                print("Caught BadStatusLine exception from Poloniex, ignoring.")
            except URLError as ex:
                print("Caught {0} from exchange, ignoring.".format(ex))
            except ApiError as ex:
                print("Caught {0} reading from exchange API, ignoring.".format(ex))
            except Exception as ex:
                log.log_error(ex)
                log.persistStatus()
                if 'Invalid API key' in ex:
                    print("!!! Troubleshooting !!!")
                    print("Are your API keys correct? No quotation. Just plain keys.")
                    raise
                elif 'Nonce must be greater' in ex:
                    print("!!! Troubleshooting !!!")
                    print("Are you reusing the API key in multiple applications? Use a unique key for every application.")
                    raise
                elif 'Permission denied' in ex:
                    print("!!! Troubleshooting !!!")
                    print("Are you using IP filter on the key? Maybe your IP changed?")
                    raise
                elif 'timed out' in ex:
                    print("Timed out, will retry in " +
                          str(Lending.get_sleep_time()) + "sec")
                elif 'Error 429' in ex:
                    additional_sleep = max(130.0-Lending.get_sleep_time(), 0)
                    sum_sleep = additional_sleep + Lending.get_sleep_time()
                    log.log_error('IP has been banned due to many requests. Sleeping for {} seconds'.format(sum_sleep))
                    if Config.has_option('MarketAnalysis', 'analyseCurrencies'):
                        if api.req_period <= api.default_req_period * 1.5:
                            api.req_period += 3
                        if Config.getboolean('MarketAnalysis', 'ma_debug_log'):
                            print("Caught ERR_RATE_LIMIT, sleeping capture and increasing request delay. Current"
                                " {0}ms".format(api.req_period))
                            log.log_error('Expect this 130s ban periodically when using MarketAnalysis, it will fix itself')
                    time.sleep(additional_sleep)
                # Ignore all 5xx errors (server error) as we can't do anything about it (https://httpstatuses.com/)
                else:
                    print(traceback.format_exc())
                    print("v{0} Unhandled error, please open a Github issue so we can fix it!".format(Data.get_bot_version()))
                    if notify_conf['notify_caught_exception']:
                        log.notify("{0}\n-------\n{1}".format(ex, traceback.format_exc()), notify_conf)
                sys.stdout.flush()
                time.sleep(Lending.get_sleep_time())


    except KeyboardInterrupt:
        if web_server_enabled:
            WebServer.stop_web_server()
        PluginsManager.on_bot_exit()
        log.log('bye')
        print('bye')


if __name__ == "__main__":
    main()
