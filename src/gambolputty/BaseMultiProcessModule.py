# -*- coding: utf-8 -*-
import sys
import multiprocessing
import Queue
import Utils
import BaseModule

class BaseMultiProcessModule(BaseModule.BaseModule, multiprocessing.Process):
    """
    Base class for all gambolputty modules that will run as separate processes.
    If you happen to override one of the methods defined here, be sure to know what you
    are doing ;) You have been warned ;)

    Configuration example:

    - module: SomeModuleName
      alias: AliasModuleName                    # <default: ""; type: string; is: optional>
      pool_size: 4                              # <default: None; type: None||integer; is: optional>
      queue_size: 20                            # <default: None; type: None||integer; is: optional>
      redis_client: RedisClientName             # <default: ""; type: string; is: optional>
      redis_key: XPathParser%(server_name)s     # <default: ""; type: string; is: required if redis_client is True else optional>
      redis_ttl: 600                            # <default: 60; type: integer; is: optional>
      ...
      receivers:
       - ModuleName
       - ModuleAlias
    """

    can_run_parallel = True

    def __init__(self, gp, stats_collector=False):
        BaseModule.BaseModule.__init__(self, gp, stats_collector)
        multiprocessing.Process.__init__(self)
        self.daemon = True

    def setInputQueue(self, queue):
        self.input_queue = queue

    def getInputQueue(self):
        return self.input_queue

    def getEventFromInputQueue(self, block=True, timeout=None):
        event = False
        try:
            event = self.input_queue.get(block, timeout)
        except Queue.Empty:
            raise
        except (KeyboardInterrupt, SystemExit):
            # Keyboard interrupt is catched in gambolputtys main run method.
            # This will take care to shutdown all running modules.
            pass
        except:
            exc_type, exc_value, exc_tb = sys.exc_info()
            self.logger.error("%sCould not read data from input queue. Exception: %s, Error: %s.%s" % (Utils.AnsiColors.FAIL, exc_type, exc_value, Utils.AnsiColors.ENDC) )
        return event

    def run(self):
        if not self.receivers:
            # Only issue warning for those modules that are expected to have receivers.
            # TODO: A better solution should be implemented...
            if self.module_type not in ['stand_alone', 'output']:
                self.logger.error("%sShutting down module %s since no receivers are set.%s" % (Utils.AnsiColors.FAIL, self.__class__.__name__, Utils.AnsiColors.ENDC))
                return
        if not self.input_queue:
            # Only issue warning for those modules that are expected to have an input queue.
            # TODO: A better solution should be implemented...
            if self.module_type not in ['stand_alone', 'input']:
                self.logger.error("%sShutting down module %s since no input queue set.%s" % (Utils.AnsiColors.FAIL, self.__class__.__name__, Utils.AnsiColors.ENDC))
            return
        while self.is_alive:
            event = self.getEventFromInputQueue()
            self.receiveEvent(event)

    def shutDown(self):
        # Call parent shutDown method
        BaseModule.BaseModule.shutDown(self)
        self.is_alive = False