# Copyright 2020 Oath Inc. Licensed under the terms of the Apache 2.0 license. See LICENSE in the project root.
from cloudwatch import VespaCloudwatchEmitter
import os
import json
import unittest
from mock import MagicMock

HERE = os.path.dirname(os.path.abspath(__file__))


class TestMetricsEmitter(unittest.TestCase):
    
    def test_emit_metrics(self):
        emitter = VespaCloudwatchEmitter()
        with open(os.path.join(HERE, 'metrics.json'), 'r') as f:
            emitter._get_metrics_json = MagicMock(return_value=json.load(f))
        emitter._emit_to_cloudwatch = MagicMock(return_value='Successfully emitted metrics')
        emitter.CHUNK_SIZE = 3
        emitter.run()
    
    def test_split_list(self):
        lst = list(range(1, 11))
        list_of_chunks = VespaCloudwatchEmitter().split_list(lst, 3)
    
        assert len(list_of_chunks) == 4
        assert list_of_chunks[0] == [1, 2, 3]
        assert list_of_chunks[3] == [10]
    
    def test_split_list_with_only_one_chunk(self):
        lst = list(range(1, 3))
        list_of_chunks = VespaCloudwatchEmitter().split_list(lst, 3)
    
        assert len(list_of_chunks) == 1
        assert list_of_chunks[0] == [1, 2]
    
    def test_generated_metric_data(self):
        emitter = VespaCloudwatchEmitter()
        with open(os.path.join(HERE, 'metrics.json'), 'r') as f:
            response = json.load(f)
        metric_data = emitter.all_metric_data_for_response(response)
        assert len(metric_data) == 8
    
        cpu_util = metric_data[0]
        assert cpu_util['MetricName'] == 'cpu.util'
        assert cpu_util['Value'] == 11.1
    
        cpu_dimensions = cpu_util['Dimensions']
        assert len(cpu_dimensions) == 4
        assert cpu_dimensions[2]['Name'] == 'host'
        assert cpu_dimensions[2]['Value'] == 'host1'
    
        net_in_bytes = metric_data[2]
        assert net_in_bytes['MetricName'] == 'net.in.bytes'
        assert net_in_bytes['Value'] == 12345
    
        http_status = metric_data[4]
        assert http_status['MetricName'] == 'http.status.2xx.rate'
        assert http_status['Value'] == 4.95
    
        http_dimensions = http_status['Dimensions']
        assert len(http_dimensions) == 6
        assert http_dimensions[5]['Name'] == 'httpMethod'
        assert http_dimensions[5]['Value'] == 'GET'
    
        mem_util = metric_data[7]
        assert mem_util['MetricName'] == 'mem.util'
        assert mem_util['Value'] == 62
    
        mem_dimensions = mem_util['Dimensions']
        assert len(mem_dimensions) == 4
        assert mem_dimensions[2]['Name'] == 'host'
        assert mem_dimensions[2]['Value'] == 'host2'

    def test_synthetic_metric_data(self):
        """
        Included to show the format that should be emitted to Cloudwatch
        """
        metric_data = synthetic_metric_data()
        assert 2 == len(metric_data)

        metric1 = metric_data[0]
        assert 'cpu.util' == metric1['MetricName']
        assert 18.7 == metric1['Value']

        dimensions = metric1['Dimensions']
        assert 2 == len(dimensions)
        assert 'host' == dimensions[0]['Name']
        assert 'host1' == dimensions[0]['Value']


def synthetic_metric_data():
    return [
        {
            'MetricName': 'cpu.util',
            'Dimensions': [
                {
                    'Name': 'host',
                    'Value': 'host1'
                },
                {
                    'Name': 'applicationId',
                    'Value': 'my-app'
                },
            ],
            'Unit': 'None',
            'Value': 18.7
        },
        {
            'MetricName': 'metric2',
            'Dimensions': [
                {
                    'Name': 'disk.util',
                    'Value': 'm2-dim1-val'
                },
            ],
            'Unit': 'None',
            'Value': 2
        }
    ]
