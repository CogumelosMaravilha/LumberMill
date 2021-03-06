import lumbermill.utils.DictUtils as DictUtils

from tests.ModuleBaseTestCase import ModuleBaseTestCase, MockLumberMill
from lumbermill.parser import NetFlowParser


class TestNetFlowParser(ModuleBaseTestCase):

    def setUp(self):
        test_object = NetFlowParser.NetFlowParser(MockLumberMill())
        test_object.lumbermill.addModule('NetFlowParser',test_object)
        super(TestNetFlowParser, self).setUp(test_object)

    def testNetFlowV5(self):
        self.test_object.configure({})
        self.checkConfiguration()
        nf_v5_hex_data = '00050002e9cfd946560e6acc0bd469710000000000000000c389e016c389e01800000000000000000000000100000040e9cfd946e9cfd94600000000000201000000000018180000c389e018c389e01600000000000000000000000100000065e9cfd946e9cfd94600000000000001000000000018180000'
        nf_v5_data = nf_v5_hex_data.decode('hex')
        count = 0
        for event in self.test_object.handleEvent(DictUtils.getDefaultEventDict({'data': nf_v5_data})):
            if count == 0:
                self.assertTrue(event['data']['sys_uptime'] == 3922712902)
                self.assertTrue(event['data']['unix_nsecs'] == 198470001)
                self.assertTrue(event['data']['unix_secs'] == 1443785420)
                self.assertTrue(event['data']['uptime_start'] == 3922712902)
                self.assertTrue(event['data']['uptime_end'] == 3922712902)
                self.assertTrue(event['data']['srcaddr'] == '195.137.224.22')
                self.assertTrue(event['data']['dstaddr'] == '195.137.224.24')
                self.assertTrue(event['data']['tcp_flags'] == ['SYN'])
                self.assertTrue(event['data']['prot_name'] == 'icmp')
                self.assertTrue(event['lumbermill']['event_type'] == 'NetFlowV5')
            if count == 1:
                self.assertTrue(event['data']['srcaddr'] == '195.137.224.24')
                self.assertTrue(event['data']['dstaddr'] == '195.137.224.22')
                self.assertTrue(event['lumbermill']['event_type'] == 'NetFlowV5')
            count += 1