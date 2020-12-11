"""
   Copyright 2020 InfAI (CC SES)

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""


__all__ = ('discover_hosts', )


from util import getLogger, conf, MQTTClient
from .device import Device
import urllib3
import urllib.parse
import threading
import subprocess
import socket
import requests
import time
import json
import typing
import mgw_dc


logger = getLogger(__name__.split(".", 1)[-1])

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def ping(host) -> bool:
    return subprocess.call(['ping', '-c', '2', '-t', '2', host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def get_local_ip(host) -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((host, 80))
        ip_addr = s.getsockname()[0]
        s.close()
        logger.debug("local ip address is '{}'".format(ip_addr))
        return ip_addr
    except Exception as ex:
        raise Exception("could not get local ip - {}".format(ex))


def get_ip_range(local_ip) -> list:
    split_ip = local_ip.rsplit('.', 1)
    base_ip = split_ip[0] + '.'
    if len(split_ip) > 1:
        ip_range = [str(base_ip) + str(i) for i in range(1, 256)]
        ip_range.remove(local_ip)
        return ip_range
    return list()


def discover_hosts_worker(ip_range, alive_hosts):
    for ip in ip_range:
        if ping(ip):
            alive_hosts.append(ip)


def discover_hosts() -> list:
    ip_range = get_ip_range(get_local_ip(urllib.parse.urlparse(conf.Discovery.remote_host).netloc or conf.Discovery.remote_host))
    logger.debug("scanning ip range '{}-255' ...".format(ip_range[0]))
    alive_hosts = list()
    workers = list()
    bin = 0
    bin_size = 3
    if ip_range:
        for i in range(int(len(ip_range) / bin_size)):
            worker = threading.Thread(target=discover_hosts_worker, name='discoverHostsWorker', args=(ip_range[bin:bin + bin_size], alive_hosts))
            workers.append(worker)
            worker.start()
            bin = bin + bin_size
        if ip_range[bin:]:
            worker = threading.Thread(target=discover_hosts_worker, name='discoverHostsWorker', args=(ip_range[bin:], alive_hosts))
            workers.append(worker)
            worker.start()
        for worker in workers:
            worker.join()
    return alive_hosts


def validate_hosts_worker(hosts, valid_hosts):
    for host in hosts:
        try:
            response = requests.get(url="http://{}/{}".format(host, conf.Api.air_sensor_device), timeout=conf.Discovery.timeout)
            if response.status_code == 200 and 'blebox' in response.headers.get('Server'):
                host_info = response.json()
                if "device" in host_info.keys():
                    host_info = host_info.get("device")
                valid_hosts[host_info.get('id')] = {
                    "name": host_info.get("deviceName"),
                    "type": host_info.get("type"),
                    "ip_address": host
                }
        except Exception:
            pass


def validate_hosts(hosts) -> dict:
    valid_hosts = dict()
    workers = list()
    bin = 0
    bin_size = 2
    if len(hosts) <= bin_size:
        worker = threading.Thread(target=validate_hosts_worker, name='validateHostsWorker', args=(hosts, valid_hosts))
        workers.append(worker)
        worker.start()
    else:
        for i in range(int(len(hosts) / bin_size)):
            worker = threading.Thread(target=validate_hosts_worker, name='validateHostsWorker', args=(hosts[bin:bin + bin_size], valid_hosts))
            workers.append(worker)
            worker.start()
            bin = bin + bin_size
        if hosts[bin:]:
            worker = threading.Thread(target=validate_hosts_worker, name='validateHostsWorker', args=(hosts[bin:], valid_hosts))
            workers.append(worker)
            worker.start()
    for worker in workers:
        worker.join()
    return valid_hosts

