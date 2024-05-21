#!/usr/bin/env python3
import argparse
import asyncio
import re
import os
import subprocess
import pathlib
import logging
from typing import Mapping, Tuple, List

from aiohttp import web
import prometheus_client
from prometheus_client import CollectorRegistry, Counter
import katsdpservices


ETHTOOL_COUNTERS = [
    'rx_buffer_passed_thres_phy',
    'rx_bytes_phy',
    'rx_corrected_bits_phy',
    'rx_cqe_compress_blks',
    'rx_cqe_compress_pkts',
    'rx_crc_errors_phy',
    'rx_discards_phy',
    'rx_fifo_errors',
    'rx_missed_errors',
    'rx_mpwqe_filler',
    'rx_multicast_phy',
    'rx_out_of_buffer',
    'rx_over_errors',
    'rx_oversize_packets_phy',
    'rx_pci_signal_integrity',
    'rx_pcs_symbol_err_phy',
    'rx_prio0_buf_discard',
    'rx_prio0_cong_discard',
    'rx_prio0_discards',
    'rx_steer_missed_packets',
    'rx_symbol_err_phy',
    'rx_wqe_err',
    'tx_bytes_phy',
    'tx_cqe_err',
    'tx_dropped',
    'tx_fifo_errors',
    'tx_multicast_phy',
    'tx_pci_signal_integrity',
    'tx_queue_stopped',
]

RDMA_COUNTERS = [
    'out_of_buffer',
    'req_cqe_error',
    'req_cqe_flush_error',
    'resp_cqe_error',
    'resp_cqe_flush_error',
    'resp_local_length_error'
]


def make_ethtool_counters(registry: CollectorRegistry) -> Mapping[str, Counter]:
    return {
        name: Counter('ethtool_' + name + '_total', 'ethtool counter ' + name,
                      labelnames=('device',), registry=registry)
        for name in ETHTOOL_COUNTERS
    }


def make_rdma_counters(registry: CollectorRegistry) -> Mapping[str, Counter]:
    return {
        name: Counter('rdma_' + name + '_total', 'RDMA HW counter ' + name,
                      labelnames=('device',), registry=registry)
        for name in RDMA_COUNTERS
    }


async def ibdev_mapping() -> Mapping[str, Tuple[str, int]]:
    """Get mapping between (device, port) of infiniband devices and OS devices.

    Returns a dictionary with OS device as the key and (device, port) as the
    value. OS devices for which no IB device was found are not reported.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            '/usr/bin/ibdev2netdev', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return {}
    (stdout_data, stderr_data) = await process.communicate()
    if process.returncode != 0:
        return {}
    out = {}
    for line in stdout_data.splitlines():
        text = line.decode('utf-8', errors='replace')
        match = re.match(r'([^ ]+) port (\d+) ==> ([^ ]+)', text)
        if match:
            out[match.group(3)] = (match.group(1), int(match.group(2)))
    return out


def physical_devices() -> List[str]:
    """Get network devices which have physical hardware"""
    out = []
    for device in os.listdir('/sys/class/net'):
        if os.path.exists(os.path.join('/sys/class/net', device, 'device')):
            out.append(device)
    return out


async def update_ethtool(device: str, counters: Mapping[str, Counter]) -> None:
    process = await asyncio.create_subprocess_exec(
        '/sbin/ethtool', '-S', device, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout_data, stderr_data) = await process.communicate()
    if process.returncode != 0:
        if process.returncode != 94:  # returned by ethtool if no stats are available
            logging.warning('ethtool failed: ' + stderr_data.decode('utf-8', errors='replace'))
        return
    for line in stdout_data.splitlines():
        text = line.decode('utf-8', errors='replace')
        match = re.match(r' +([^ :]+): (\d+)', text)
        if match:
            name = match.group(1)
            value = int(match.group(2))
            if name in counters:
                counters[name].labels(device).inc(value)


def update_rdma(device: str, ibdev: str, port: int, counters: Mapping[str, Counter]) -> None:
    base = pathlib.Path('/sys/class/infiniband/{}/ports/{}/hw_counters'.format(ibdev, port))
    for name, counter in counters.items():
        try:
            with (base / name).open('r') as f:
                value = int(f.read())
        except (OSError, ValueError):
            pass
        else:
            counter.labels(device).inc(value)


async def get_counters() -> CollectorRegistry:
    registry = CollectorRegistry()
    ethtool_counters = make_ethtool_counters(registry)
    rdma_counters = make_rdma_counters(registry)
    devices = physical_devices()
    ibdevs = await ibdev_mapping()
    for device in devices:
        await update_ethtool(device, ethtool_counters)
        try:
            ibdev, port = ibdevs[device]
        except KeyError:
            pass
        else:
            update_rdma(device, ibdev, port, rdma_counters)
    return registry


async def get_metrics(request: web.Request) -> web.Response:
    registry = await get_counters()
    content = prometheus_client.generate_latest(registry).decode()
    return web.Response(text=content)


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--port', type=int, default=9117, help='Web server port number')
    parser.add_argument(
        '--bind', help='Web server local address')
    parser.add_argument(
        '--log-level', default='WARNING', help='Log level [%(default)s]')
    return parser.parse_args()


def main() -> None:
    args = get_arguments()
    katsdpservices.setup_logging()
    logging.root.setLevel(args.log_level.upper())

    app = web.Application()
    app.router.add_get('/metrics', get_metrics)
    web.run_app(app, host=args.bind, port=args.port)


if __name__ == '__main__':
    main()
