# -*- coding: utf-8 -*-
from hashlib import md5
import sys
import datetime
import time
import elasticsearch
import Queue
import BaseMultiProcessModule
import Utils
import Decorators

json = False
for module_name in ['yajl', 'simplejson', 'json']:
    try:
        json = __import__(module_name)
        break
    except ImportError:
        pass
if not json:
    raise ImportError

@Decorators.ModuleDocstringParser
class ElasticSearchMultiProcessSink(BaseMultiProcessModule.BaseMultiProcessModule):
    """
    Store the data dictionary in an elasticsearch index.

    The elasticsearch module takes care of discovering all nodes of the elasticsearch cluster.
    Requests will the be loadbalanced via round robin.

    nodes: configures the elasticsearch nodes.
    connection_type: one of: 'thrift', 'http'
    http_auth: 'user:password'
    use_ssl: one of: True, False
    index_prefix: es index prefix to use, will be appended with '%Y.%m.%d'.
    index_name: sets a fixed name for the es index.
    doc_id: sets the es document id for the committed event data.
    ttl: When set, documents will be automatically deleted after ttl expired.
         Can either set time in microseconds or elasticsearch date format, e.g.: 1d, 15m etc.
         This feature needs to be enabled for the index.
         @See: http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/mapping-ttl-field.html
    consistency: one of: 'one', 'quorum', 'all'
    replication: one of: 'sync', 'async'.
    store_interval_in_secs: sending data to es in x seconds intervals.
    batch_size: sending data to es if event count is above, even if store_interval_in_secs is not reached.
    backlog_size: maximum count of events waiting for transmission. Events above count will be dropped.

    Configuration example:

    - module: ElasticSearchMultiProcessSink
        nodes: ["localhost:9200"]                 # <type: list; is: required>
        connection_type: http                     # <default: "thrift"; type: string; values: ['thrift', 'http']; is: optional>
        http_auth: 'user:password'                # <default: None; type: None||string; is: optional>
        use_ssl: True                             # <default: False; type: boolean; is: optional>
        index_prefix: agora_access-               # <default: 'gambolputty-'; type: string; is: required if index_name is False else optional>
        index_name: "Fixed index name"            # <default: ""; type: string; is: required if index_prefix is False else optional>
        doc_id: 'data'                            # <default: "data"; type: string; is: optional>
        ttl:                                      # <default: None; type: None||string; is: optional>
        consistency: 'one'                        # <default: "quorum"; type: string; values: ['one', 'quorum', 'all']; is: optional>
        replication: 'sync'                       # <default: "sync"; type: string;  values: ['sync', 'async']; is: optional>
        store_interval_in_secs: 1                 # <default: 5; type: integer; is: optional>
        batch_size: 500                           # <default: 500; type: integer; is: optional>
        backlog_size: 5000                        # <default: 5000; type: integer; is: optional>
    """

    module_type = "output"
    """Set module type"""

    def configure(self, configuration):
        # Call parent configure method
        BaseMultiProcessModule.BaseMultiProcessModule.configure(self, configuration)
        self.events_container = []
        self.batch_size = self.getConfigurationValue('batch_size')
        self.backlog_size = self.getConfigurationValue('backlog_size')
        self.replication = self.getConfigurationValue("replication")
        self.consistency = self.getConfigurationValue("consistency")
        self.ttl = self.getConfigurationValue("ttl")
        self.connection_class = elasticsearch.connection.ThriftConnection
        if self.getConfigurationValue("connection_type") == 'http':
            self.connection_class = elasticsearch.connection.Urllib3HttpConnection
        self.es = self.connect()
        if not self.es:
            self.gp.shutDown()
            return
        self.is_storing = False
        self.timed_store_func = self.getTimedStoreFunc()

    def getTimedStoreFunc(self):
        @Decorators.setInterval(self.getConfigurationValue('store_interval_in_secs'))
        def timedStoreData():
            if self.is_storing:
                return
            self.storeData(self.events_container)
        return timedStoreData

    def run(self):
        self.timed_store_func()
        BaseMultiProcessModule.BaseMultiProcessModule.run(self)

    def connect(self):
        es = False
        try:
            # Connect to es node and round-robin between them.
            es = elasticsearch.Elasticsearch(self.getConfigurationValue('nodes'),
                                             connection_class=self.connection_class,
                                             sniff_on_start=True, maxsize=20,
                                             use_ssl=self.getConfigurationValue('use_ssl'),
                                             http_auth=self.getConfigurationValue('http_auth'))
        except:
            etype, evalue, etb = sys.exc_info()
            self.logger.error("%sNo index servers configured or none could be reached.Exception: %s, Error: %s.%s" % (Utils.AnsiColors.FAIL, etype, evalue, Utils.AnsiColors.ENDC))
            es = False
        return es

    def sendEvent(self, event):
        """Override the default behaviour of destroying an event when no receivers are set.
        This module aggregates a configurable amount of events to use the bulk update feature
        of elasticsearch. So events must only be destroyed when bulk update was successful"""
        receivers = self.getFilteredReceivers(event)
        if not receivers:
            return
        for idx, receiver in enumerate(receivers):
            if isinstance(receiver, Queue.Queue):
                receiver.put(event if idx is 0 else event.copy())
            else:
                receiver.receiveEvent(event if idx is 0 else event.copy())

    def handleEvent(self, event):
        # Wait till a running store is finished to avoid strange race conditions.
        while self.is_storing:
            time.sleep(.001)
        if len(self.events_container) >= self.backlog_size:
            self.logger.warning("%sMaximum number of events (%s) in backlog reached. Dropping event.%s" % (Utils.AnsiColors.WARNING, self.backlog_size, Utils.AnsiColors.ENDC))
            yield event
            return
        self.events_container.append(event)
        if len(self.events_container) >= self.batch_size:
            self.storeData(self.events_container)
        yield event

    def dataToElasticSearchJson(self, index_name, events):
        """
        Format data for elasticsearch bulk update
        """
        json_data = ""
        for event in events:
            try:
                event_type = event['event_type']
            except KeyError:
                event_type = 'Unknown'
            try:
                doc_id = event[self.getConfigurationValue("doc_id", event)]
            except KeyError:
                doc_id = self.getConfigurationValue("doc_id", event)
            if not doc_id:
                self.logger.error("%sCould not find doc_id %s for event %s.%s" % (Utils.AnsiColors.FAIL, self.getConfigurationValue("doc_id"), event, Utils.AnsiColors.ENDC))
                continue
            doc_id = json.dumps(doc_id.strip())
            if self.ttl:
                event['_ttl'] = self.ttl
            es_index = '{"index": {"_index": "%s", "_type": "%s", "_id": %s}}\n' % (index_name, event_type, doc_id)
            try:
                json_data += "%s%s\n" % (es_index,json.dumps(event))
            except UnicodeDecodeError:
                etype, evalue, etb = sys.exc_info()
                self.logger.error("%sCould not json encode %s. Exception: %s, Error: %s.%s" % (Utils.AnsiColors.FAIL, event, etype, evalue, Utils.AnsiColors.ENDC))
        return json_data

    def storeData(self, events):
        if len(events) == 0 or not self.es:
            return
        self.is_storing = True
        if self.getConfigurationValue("index_name"):
            index_name = self.getConfigurationValue("index_name")
        else:
            index_name = "%s%s" % (self.getConfigurationValue("index_prefix"), datetime.date.today().strftime('%Y.%m.%d'))

        json_data = self.dataToElasticSearchJson(index_name, events)
        try:
            self.es.bulk(body=json_data, consistency=self.consistency, replication=self.replication)
            self.destroyEvent(event_list=events)
            self.events_container = []
        except elasticsearch.exceptions.ConnectionError:
            try:
                self.logger.warning("%sLost connection to %s. Trying to reconnect.%s" % (Utils.AnsiColors.WARNING, (self.getConfigurationValue("nodes"),index_name), Utils.AnsiColors.ENDC))
                self.es = self.connect()
            except:
                time.sleep(.5)
        except:
            etype, evalue, etb = sys.exc_info()
            self.logger.error("%sServer cummunication error. Exception: %s, Error: %s.%s" % (Utils.AnsiColors.FAIL, etype, evalue, Utils.AnsiColors.ENDC))
            self.logger.debug("Payload: %s" % json_data)
            time.sleep(.2)
            if "Broken pipe" in evalue or "Connection reset by peer" in evalue:
                tries = 0
                self.es = False
                while tries < 5 and not self.es:
                    time.sleep(7)
                    self.logger.warning("%sLost connection to %s.Trying to reconnect...%s" % (Utils.AnsiColors.WARNING, self.getConfigurationValue("nodes"), Utils.AnsiColors.ENDC))
                    # Try to reconnect.
                    self.es = self.connect()
                    tries += 1
                if not self.es:
                    self.logger.error("%sReconnect failed. Shutting down.%s" % (Utils.AnsiColors.FAIL, etype, evalue, Utils.AnsiColors.ENDC))
                    self.gp.shutDown()
                else:
                    self.logger.info("%sReconnection to %s successful.%s" % (Utils.AnsiColors.LIGHTBLUE, self.getConfigurationValue("nodes"), Utils.AnsiColors.ENDC))
        finally:
            self.is_storing = False