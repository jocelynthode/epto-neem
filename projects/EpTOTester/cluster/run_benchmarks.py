#!/usr/bin/env python3
"""
Author: Jocelyn Thode

This script is in charge of running the benchmarks either locally or on the cluster.

It creates the network, services and the churn if we need it.

"""
import argparse
import docker
import logging
import re
import signal
import subprocess
import threading
import time
import yaml

from churn import Churn
from benchmark import Benchmark
from datetime import datetime
from docker import errors
from docker import types
from docker import utils
from logging import config
from nodes_trace import NodesTrace


with open('config.yaml', 'r') as f:
    config = yaml.load(f)
    MANAGER_IP = config['manager_ip']
    LOCAL_MANAGER_IP = config['local_manager_ip']
    LOCAL_DATA = config['local_data']
    CLUSTER_DATA = config['cluster_data']


def create_logger():
    with open('logger.yaml') as f:
        conf = yaml.load(f)
        logging.config.dictConfig(conf)


def churn_tuple(s):
    try:
        _to_kill, _to_create = map(int, s.split(','))
        return _to_kill, _to_create
    except:
        raise TypeError("Tuples must be (int, int)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run benchmarks',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('peer_number', type=int, help='With how many peer should it be ran')
    parser.add_argument('time_add', type=int, help='Delay experiments start in seconds')
    parser.add_argument('time_to_run', type=int, help='For how long should the experiment run in seconds')
    parser.add_argument('config', type=argparse.FileType('r'), help='Configuration file')
    parser.add_argument('-l', '--local', action='store_true',
                        help='Run locally')
    parser.add_argument('-t', '--tracker', action='store_true', help='Specify whether the app uses a tracker')
    parser.add_argument('-n', '--runs', type=int, default=1, help='How many experiments should be ran')
    parser.add_argument('--verbose', '-v', action='store_true', help='Switch DEBUG logging on')

    subparsers = parser.add_subparsers(dest='churn', help='Specify churn and its arguments')

    churn_parser = subparsers.add_parser('churn', help='Activate churn')
    churn_parser.add_argument('period', type=int,
                              help='The interval between killing/adding new containers in ms')
    churn_parser.add_argument('--synthetic', '-s', metavar='N', type=churn_tuple, nargs='+',
                              help='Pass the synthetic list (to_kill,to_create)(example: 0,100 0,1 1,0)')
    churn_parser.add_argument('--delay', '-d', type=int, default=0,
                              help='With how much delay compared to the tester should the tester start in ms')

    args = parser.parse_args()
    APP_CONFIG = yaml.load(args.config)

    if args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    create_logger()
    logger = logging.getLogger('benchmarks')
    logger.setLevel(log_level)

    logger.info('START')
    if args.local:
        hosts_fname = None
        repository = ''
    else:
        hosts_fname = 'hosts'
        repository = APP_CONFIG['repository']['name']

    churn = Churn(hosts_filename=hosts_fname, service_name=APP_CONFIG['service']['name'], repository=repository)
    churn.set_logger_level(log_level)
    benchmark = Benchmark(APP_CONFIG, args.local, log_level, churn)
    benchmark.set_logger_level(log_level)
    benchmark.run()
    args.time_add *= 1000
    args.time_to_run *= 1000

    def signal_handler(signal, frame):
        logger.info('Stopping Benchmarks')
        benchmark.stop()
        exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.local:
        service_image = APP_CONFIG['service']['name']
        if args.tracker:
            tracker_image = APP_CONFIG['tracker']['name']
        with subprocess.Popen(['../gradlew', '-p', '..', 'docker'],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True) as p:
            for line in p.stdout:
                print(line, end='')
    else:
        service_image = APP_CONFIG['repository'] + APP_CONFIG['service']['name']
        for line in cli.pull(service_image, stream=True, decode=True):
            print(line)
        if args.tracker:
            tracker_image = APP_CONFIG['repository'] + APP_CONFIG['tracker']['name']
            for line in cli.pull(tracker_image, stream=True):
                print(line)
    try:
        cli.init_swarm()
        if not args.local:
            logger.info('Joining Swarm on every hosts:')
            token = cli.inspect_swarm()['JoinTokens']['Worker']
            subprocess.call(['parallel-ssh', '-t', '0', '-h', 'hosts', 'docker', 'swarm',
                             'join', '--token', token, '{:s}:2377'.format(MANAGER_IP)])
        ipam_pool = utils.create_ipam_pool(subnet=APP_CONFIG['service']['network']['subnet'])
        ipam_config = utils.create_ipam_config(pool_configs=[ipam_pool])
        cli.create_network(APP_CONFIG['service']['network']['name'], 'overlay', ipam=ipam_config)
    except errors.APIError:
        logger.info('Host is already part of a swarm')
        if not cli.networks(names=[APP_CONFIG['service']['network']['name']]):
            logger.error('Network  doesn\'t exist!')
            exit(1)

    for run_nb, _ in enumerate(range(args.runs), 1):
        if args.tracker:
            create_service(APP_CONFIG['tracker']['name'], tracker_image,
                           placement={'Constraints': ['node.role == manager']},
                           mem_limit=APP_CONFIG['service']['mem_limit'])
            wait_on_service(APP_CONFIG['tracker']['name'], 1)
        time_to_start = int((time.time() * 1000) + args.time_add)
        logger.debug(datetime.utcfromtimestamp(time_to_start / 1000).isoformat())

        environment_vars = {**APP_CONFIG['service']['parameters'],
                            **{'PEER_NUMBER': args.peer_number,
                               'TIME': time_to_start,
                               'TIME_TO_RUN': args.time_to_run}}
        environment_vars = ['{:s}={}'.format(k, v) for k, v in environment_vars.items()]
        logger.debug(environment_vars)

        service_replicas = 0 if args.churn else args.peer_number
        log_storage = LOCAL_DATA if args.local else CLUSTER_DATA
        create_service(APP_CONFIG['service']['name'], service_image, env=environment_vars,
                       mounts=[types.Mount(target='/data', source=log_storage, type='bind')],
                       replicas=service_replicas, mem_limit=APP_CONFIG['service']['mem_limit'])

        logger.info('Running Benchmark -> Experiment: {:d}/{:d}'.format(run_nb, args.runs))
        if args.churn:
            thread = threading.Thread(target=run_churn, args=[time_to_start + args.delay], daemon=True)
            thread.start()
            wait_on_service(APP_CONFIG['service']['name'], 0, inverse=True)
            logger.info('Running with churn')
            if args.synthetic:
                # Wait for some peers to at least start
                time.sleep(120)
                total = [sum(x) for x in zip(*args.synthetic)]
                # Wait until only stopped containers are still alive
                wait_on_service(APP_CONFIG['service']['name'], containers_nb=total[0], total_nb=total[1])
            else:
                thread.join()  # Wait for churn to finish
                time.sleep(300)  # Wait 5 more minutes

        else:
            wait_on_service(APP_CONFIG['service']['name'], 0, inverse=True)
            logger.info('Running without churn')
            wait_on_service(APP_CONFIG['service']['name'], 0)
        if args.tracker:
            cli.remove_service(APP_CONFIG['tracker']['name'])
        cli.remove_service(APP_CONFIG['service']['name'])

        logger.info('Services removed')
        time.sleep(30)

        if not args.local:
            subprocess.call('parallel-ssh -t 0 -h hosts "mkdir -p {path}/test-{nb}/capture &&'
                            ' mv {path}/*.txt {path}/test-{nb}/ &&'
                            ' mv {path}/capture/*.csv {path}/test-{nb}/capture/"'
                            .format(path=CLUSTER_DATA, nb=run_nb), shell=True)

        subprocess.call('mkdir -p {path}/test-{nb}/capture'.format(path=log_storage, nb=run_nb),
                        shell=True)
        subprocess.call('mv {path}/*.txt {path}/test-{nb}/'.format(path=log_storage, nb=run_nb),
                        shell=True)
        subprocess.call('mv {path}/capture/*.csv {path}/test-{nb}/capture/'.format(path=log_storage, nb=run_nb),
                        shell=True)

    logger.info('Benchmark done!')

