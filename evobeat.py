#!/usr/bin/env python
import evobeatd
import argparse
from pprint import pprint as pprint

parser = argparse.ArgumentParser(description='Collect elastic telemetry.')
subparsers = parser.add_subparsers(help='Sub-command help', dest='subcommand')
# test
parser_test = subparsers.add_parser('test', help='Verify configuration and collect data once. Data is not POSTed to elastic.')
parser_test.add_argument('--name', help='Collector name, configuration must be stored in config/name.yaml.', required=True)
parser_test.add_argument('--debug', help='Print debug messages and collected data.', action='store_true')
# run
parser_run = subparsers.add_parser('run', help='Start the collector and POST data.')
parser_run.add_argument('--name', help='Collector name, configuration must be stored in config/name.yaml.', required=True)
parser_run.add_argument('--run_once', help='Collect and post once.', action='store_true')
parser_run.add_argument('--debug', help='Print debug messages and collected data.', action='store_true')
# Check supplied args
args = parser.parse_args()
if args.subcommand == 'test':
    try:
        beat = evobeatd.basebeat(name=args.name, mode='test')
    except Exception as error:
        print(str(error))
    else:
        print('INFO: Configuration OK.')
        if args.debug:
            beat.debug = True
            beat.config_data['debug'] = None
        # Run collector once
        print('INFO: Collecting data.')
        beat.elastic_docs = beat.collector_module.collect_data(beat.config_data)
        pprint(beat.elastic_docs)
elif args.subcommand == 'run':
    beat = evobeatd.basebeat(name=args.name, mode='run')
    if args.debug:
        beat.debug = True
        beat.config_data['debug'] = None
    if args.run_once:
        # Collect data and POST once
        beat.elastic_docs = beat.collector_module.collect_data(beat.config_data)
        beat.post()
    else:
        # Run at times set by interval
        beat.run()
