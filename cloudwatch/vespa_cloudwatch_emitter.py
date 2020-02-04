# Copyright 2020 Oath Inc. Licensed under the terms of the Apache 2.0 license. See LICENSE in the project root.
import boto3
import json
import logging
import requests
from requests.exceptions import Timeout, HTTPError, InvalidURL, ConnectionError

logging.basicConfig(format='%(asctime)s\t%(levelname)s\t%(message)s',
                    level=logging.INFO)
log = logging.getLogger('vespa_cloudwatch_emitter')


class VespaCloudwatchEmitter:

    VESPA_URL = 'http://my-host:8080/metrics/v2/values'
    NAMESPACE = 'my-cloudwatch-namespace'
    KEY_NAME = 'album-recommendation-private-key'
    CERT_NAME = 'album-recommendation-public-cert'
    SSM_REGION = "us-east-1"
    CHUNK_SIZE = 20

    def run(self):
        log.info('Retrieving Vespa metrics from {}'.format(self.VESPA_URL))
        try:
            metrics_json = self._get_metrics_json(self.VESPA_URL)
            log.debug("json: {}".format(metrics_json))
            if 'nodes' not in metrics_json:
                log.warning("No 'nodes' in metrics json")
                return
            metric_data = self.all_metric_data_for_response(metrics_json)
            self._emit_metric_data(metric_data)
        except Timeout as e:
            log.warning("Timed out connecting to Vespa's metrics api: {}".format(e))
        except (HTTPError, InvalidURL, ConnectionError) as e:
            log.warning("Could not connect to Vespa's metrics api: {}".format(e))
        except Exception as e:
            log.warning("Unexpected error: {}".format(e))

    def _emit_metric_data(self, metric_data):
        """ Emit metric data in chunks of max CHUNK_SIZE metrics each
        """
        cloudwatch = boto3.client('cloudwatch')
        log.info("Emitting {} metrics in chunks of max {}".format(len(metric_data), self.CHUNK_SIZE))
        metric_data_chunks = self.split_list(metric_data, self.CHUNK_SIZE)
        for chunk in metric_data_chunks:
            log.info("Emitting chunk with {} metrics".format(len(chunk)))
            response = self._emit_to_cloudwatch(cloudwatch, chunk)
            log.info(response)

    def _emit_to_cloudwatch(self, client, metric_data):
        response = client.put_metric_data(MetricData=metric_data, Namespace=self.NAMESPACE)
        return response

    def _get_metrics_json(self, url):
        """ Send rest request to metrics api and return the response as JSON
        """
        log.info("Sending request to {}".format(url))
        cert = self._write_certificate()
        response = requests.get(url, cert=cert)
        response.raise_for_status()
        return response.json()

    def _write_certificate(self):
        """
        Retrieves application certificate and key stored in SSM parameter store, and writes result to /tmp/
        :return: Tuple (path_to_certificate, path_to_key)
        """
        ssm = boto3.client('ssm', self.SSM_REGION)
        response = ssm.get_parameters(
            Names=[self.CERT_NAME, self.KEY_NAME], WithDecryption=True
        )
        paths = []
        for parameter in response['Parameters']:
            path = "/tmp/" + parameter["Name"]
            self._write_file(path, parameter["Value"])
            paths.append(path)
        return tuple(paths)

    def _write_file(self, path, content):
        f = open(path, "w")
        f.write(content)
        f.close()

    def all_metric_data_for_response(self, response_json):
        metric_data = []
        for nodes_elem in response_json['nodes']:
            # Using dict.get() to avoid exception if non-existent
            log.info("Parsing metrics from node {}".format(nodes_elem.get('hostname')))

            metric_data.extend(self._metric_data_for_node_node(nodes_elem))
            metric_data.extend(self._metric_data_for_node_services(nodes_elem))
        return metric_data

    def _metric_data_for_node_node(self, nodes_elem):
        """
        Returns a list of MetricsData for the 'node' (= node metrics) element
        for a Vespa node (here represented by nodes_elem).
        """
        if 'node' not in nodes_elem:
            log.info("No node metrics for node {} (this is expected for self-hosted Vespa)."
                         .format(nodes_elem.get('hostname')))
            return []
        return self._metric_data_for_service_or_node(nodes_elem['node'])

    def _metric_data_for_node_services(self, nodes_elem):
        """
        Returns a list of MetricsData for all elements in the 'services'
        list for a Vespa node (here represented by nodes_elem).
        """
        if 'services' not in nodes_elem:
            log.warning("No services for node {}".format(nodes_elem.get('hostname')))
            return []

        metric_data = []
        for service in nodes_elem['services']:
            metric_data.extend(self._metric_data_for_service_or_node(service))
        return metric_data

    def _metric_data_for_service_or_node(self, service_or_node):
        """
        Returns a list of MetricsData for all elements in the 'metrics' json
        list of a 'nodes' element's 'node' element or one of the elements
        in a node's 'services' list.
        """
        if 'metrics' not in service_or_node:
            return []
        metric_data = []
        for metrics_elem in service_or_node['metrics']:
            metric_data.extend(self._get_metrics_with_dimensions(metrics_elem))
        return metric_data

    def _get_metrics_with_dimensions(self, metrics_elem):
        """
        Returns a list of MetricsData for one element in a 'metrics' json list.
        """
        if 'values' not in metrics_elem:
            return []
        metric_data = []
        dimensions = self._get_dimensions(metrics_elem)
        for name, value in metrics_elem['values'].items():
            metric_data.append({'MetricName': name,
                                'Value': value,
                                'Unit': 'None',
                                'Dimensions': dimensions})
        return metric_data

    def _get_dimensions(self, metrics):
        dimensions = []
        if 'dimensions' in metrics:
            dimensions_json = metrics['dimensions']
            for dim, dim_val in dimensions_json.items():
                dimensions.append({'Name': dim,
                                   'Value': dim_val})
        return dimensions

    def split_list(self, lst, chunk_size):
        """
        Splits the given list into chunks and returns the result as a list of lists/chunks
        """
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def lambda_handler(event, context):
    VespaCloudwatchEmitter().run()
    return {
        'statusCode': 200,
        'body': json.dumps('Done.')
    }


if __name__ == '__main__':
    VespaCloudwatchEmitter().run()
