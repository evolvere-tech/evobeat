#!/usr/bin/env python
import sys
import os
import time
import sys
import datetime
import urllib3
import yaml
import json
import logging
import importlib
import importlib.util
import traceback
from elasticsearch import Elasticsearch, helpers, RequestsHttpConnection
from pprint import pprint
from logging.handlers import RotatingFileHandler
from logging import StreamHandler


class basebeat(object):

    def __init__(self, **kwargs):
        self.version = '1.0.1'
        self.path = os.getcwd()
        self.msgs = []
        self.elastic_docs = []
        self.debug = False
        if kwargs:
            self.name = kwargs['name']
            self.yaml = self.path + '/configs/' + self.name + '.yaml'
        try:
            with open(self.yaml, 'r') as input_file:
                self.config_data = yaml.full_load(input_file)
        except yaml.parser.ParserError:
            sys.exit(f'ERROR: Failed to parse YAML file {self.yaml}')
        except FileNotFoundError:
            sys.exit(f'ERROR: File {self.yaml} not found.')
        except Exception as error:
            sys.exit(f'ERROR: Failed to read configuration file: {str(error)}.')
        try:
            # Copy name to config_data to make available to plugin modules
            self.config_data['args_name'] = self.name
            # Mandatory parameters
            self.elastic_host = self.config_data['elastic_host']
            self.elastic_index = self.config_data['elastic_index']
            self.elastic_username = self.config_data['elastic_username']
            self.elastic_password = self.config_data['elastic_password']
            # Load the collector module
            collector_module_name = self.config_data['collector_module']
            collector_module_path = os.path.join(self.path, 'collectors', collector_module_name) + '.py'
            # Get the module spec
            collector_module_spec = importlib.util.spec_from_file_location(collector_module_name, collector_module_path)
            # Create module from spec
            self.collector_module = importlib.util.module_from_spec(collector_module_spec)
            # Load the module
            collector_module_spec.loader.exec_module(self.collector_module)
            # Test for collect_data() function in collector_module
            if not hasattr(self.collector_module, 'collect_data'):
                sys.exit(f'ERROR: Module {collector_module_name} doe not have collect_data() function')
        except Exception as error:
            sys.exit('ERROR: Configuration parameter {} not found in {}.'.format(str(error), self.yaml))
        # Optional parameters
        # elastic_index_rotate defaults to 'daily'
        if 'elastic_index_rotate' in self.config_data:
            self.elastic_index_rotate = self.config_data['elastic_index_rotate']
        else:
            self.elastic_index_rotate = 'daily'   
        # interval defaults to 30 seconds
        if 'interval' in self.config_data:
            if self.config_data['interval'] < 30:
                sys.exit('ERROR: Minimum interval is 30.')
            self.interval = self.config_data['interval']
        else:
            self.interval = 60
        # log_file defaults to logs/{name}.log
        if 'log_file' in self.config_data:
            log_file = self.config_data['log_file']
        else:
            log_file = self.path + '/logs/' + self.name + '.log'
        # Check for collector_vault_path
        if 'collector_vault_path' in self.config_data:
            self.collector_vault_path = self.config_data['collector_vault_path']
        else:
            self.collector_vault_path = None
        try:
            self.logger = logging.getLogger(self.name)
            self.logger.setLevel(logging.DEBUG)
            # log_file can be set to "stdout" to stream output
            if log_file == 'stdout':
                handler = StreamHandler(sys.stdout)
            else:
                handler = RotatingFileHandler(log_file, maxBytes=50*1024*1024, backupCount=1)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        except Exception as error:
            sys.exit('ERROR: Failed to open log file {}.'.format(log_file))
        # Set base parameters
        self.started = False
        # Declare vault client and secrets
        self.vault_client = None
        self.vault_secrets = None
        self.collector_vault_secrets = None
        # Copy secrets to config_data to make available to plugin modules
        self.config_data['secrets'] = None
        self.config_data['collector_secrets'] = None
        # Get secrets from Vault
        #self.get_vault_credentials()
        # Create elastic session
        self.es = Elasticsearch(
                        self.elastic_host,
                        http_auth=(self.elastic_username,self.elastic_password),
                        port=443,
                        scheme='https',
                        verify_certs=False,
                        connection_class=RequestsHttpConnection
                            )
        # Disable certificate warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        urllib3.disable_warnings(urllib3.exceptions.InsecurePlatformWarning)
        urllib3.disable_warnings(urllib3.exceptions.SNIMissingWarning)

    def __del__(self):
        f_name = sys._getframe().f_code.co_name
        try:
            self.logger.info(f_name + ': Stopped.')
        except:
            pass

    def post(self):
        f_name = sys._getframe().f_code.co_name
        # "mode" is either "run" or "test"
        if self.config_data['mode'] == "test":
            msg = f'WARNING: {f_name}: POST not allowed in test mode.'
            self.logger.warning(msg)
            return {'rc': 1}
        if self.elastic_index_rotate == 'daily':
            index_suffix = '%Y-%m-%d'
        elif self.elastic_index_rotate == 'monthly':
            index_suffix = '%Y-%m'
        else:
            msg = f'{f_name}: Invalid index_rotate value {self.elastic_index_rotate}'
            return {'rc': 1}
        es_index = self.elastic_index + '-' + datetime.datetime.now().strftime(index_suffix)
        doc_header = {
                    "_index": es_index,
                    "_op_type": "create"
                    }
        if time.localtime().tm_isdst:
            offset = time.altzone / 3600
        else:
            offset = time.timezone / 3600
        utc_dt = datetime.datetime.now() + datetime.timedelta(hours=offset)
        #es = Elasticsearch(
        #                self.elastic_host,
        #                http_auth=(self.elastic_username,self.elastic_password),
        #                port=443,
        #                scheme='https',
        #                verify_certs=False,
        #                connection_class=RequestsHttpConnection
        #                    )
        for doc in self.elastic_docs:
            # Add doc header to each doc.
            doc.update(doc_header)
            # Add @timestamp field if not already set.
            if '@timestamp' not in doc:
                doc['@timestamp'] = utc_dt.isoformat()
        # POST to elastic.
        if self.debug:
            msg = f'{f_name}: POSTing to index {es_index}'
            self.logger.debug(msg)
        retry = 2
        while retry:
            try:
                bulk_results = helpers.bulk(self.es, self.elastic_docs)
                msg = f'{f_name}: {bulk_results[0]} documents POSTed successfully.'
                self.logger.info(msg)
                rc = 0
                retry = 0
            except Exception as error:
                self.logger.error(str(error))
                rc = 1
                retry -= 1
                if retry:
                    time.sleep(2)
                    msg = f'{f_name}: POST failed, retrying.'
                    self.logger.info(msg)
        # Empty list of collected docs
        self.elastic_docs = []
        return {'rc': rc}

    def run(self):
        f_name = sys._getframe().f_code.co_name
        # POST when time is a multiple of interval.
        # Collect data ahead of the POST time (processing_time)
        self.started = True
        processing_time = 5
        # wait_time = self.interval - processing_time
        # Calculate seconds to wait to run first collection
        time_now = time.time()
        seconds_until_post = self.interval - (time_now % self.interval)
        seconds_until_collect = seconds_until_post - processing_time
        post_time = time_now + seconds_until_post
        collect_time = datetime.datetime.fromtimestamp(time_now + seconds_until_collect)
        msg = f'{f_name}: Starting at {collect_time}.'
        self.logger.info(msg)
        # Wait for first collection.
        if seconds_until_collect > 0:
            time.sleep(seconds_until_collect)
        while True:
            start_collect_time = time.time()
            # Run the collector module, collect_data() function.
            self.elastic_docs = self.collector_module.collect_data(self.config_data)
            actual_processing_time = time.time() - start_collect_time
            time_now = time.time()
            seconds_until_post = post_time - time_now
            if seconds_until_post > 0:
                time.sleep(seconds_until_post)
            self.post()
            # Calculate next collect time.
            time_now = int(time.time())
            seconds_until_post = self.interval - (time_now % self.interval)
            seconds_until_collect = seconds_until_post - processing_time
            post_time = time_now + seconds_until_post
            if seconds_until_collect > 0:
                minutes_to_sleep, seconds_to_sleep = divmod((seconds_until_collect), 60)
                msg = f'{f_name}: Time to collect data: {actual_processing_time:.2f}, ' + \
                      f'sleeping for {minutes_to_sleep} minutes {seconds_to_sleep} seconds.'
                self.logger.info(msg)
                time.sleep(seconds_until_collect)
