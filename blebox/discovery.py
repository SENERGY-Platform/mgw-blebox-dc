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


__all__ = ("Discovery", )


from util import get_logger, conf, MQTTClient
from .device import Device
from .monitor import Monitor
import threading
import subprocess
import requests
import time
import json
import typing
import mgw_dc
import ipaddress


logger = get_logger(__name__.split(".", 1)[-1])


def ping(host) -> bool:
    return subprocess.call(['ping', '-c', '2', '-t', '2', host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def get_local_networks() -> typing.List[str]:
    try:
        resp = requests.get(url=conf.Discovery.host_network_url, timeout=conf.Discovery.timeout)
        if resp.status_code != 200:
            raise RuntimeError("{} {}".format(resp.status_code, resp.text))
        resp = resp.json()
        networks = list()
        for network in resp["interfaces"]:
            networks.append(network["ipv4_net"])
        return networks
    except Exception as ex:
        raise Exception("could not get local networks - {}".format(ex))


def get_ip_range(network) -> list:
    return [str(ip) for ip in ipaddress.IPv4Network(network)]


def discover_hosts_worker(ip_range, alive_hosts):
    for ip in ip_range:
        if ping(ip):
            alive_hosts.append(ip)


def discover_hosts() -> list:
    alive_hosts = list()
    if isinstance(conf.Discovery.networks, str) and conf.Discovery.networks != "":
        networks = conf.Discovery.networks.split(",")
    else:
        networks = get_local_networks()
    for network in networks:
        ip_range = get_ip_range(network)
        logger.debug("scanning network '{}' with '{}' potential hosts ...".format(network, len(ip_range)))
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
            resp = requests.get(url="http://{}/{}".format(host, conf.Api.air_sensor_info), timeout=conf.Discovery.timeout)
            if resp.status_code != 200:
                resp = requests.get(url="http://{}/{}".format(host, conf.Api.air_sensor_device), timeout=conf.Discovery.timeout)
            if resp.status_code == 200 and 'blebox' in resp.headers.get('Server'):
                resp = resp.json()
                if "device" in resp.keys():
                    resp = resp["device"]
                prefix = ""
                if conf.Discovery.device_id_prefix is not None:
                    prefix = conf.Discovery.device_id_prefix
                valid_hosts["{}{}".format(prefix, resp['id'])] = {
                    "name": resp["deviceName"],
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


class Discovery(threading.Thread):

    def __init__(self, mqtt_client: MQTTClient):
        super().__init__(name="discovery", daemon=True)
        self.__mqtt_client = mqtt_client
        self.__device_pool: typing.Dict[str, typing.Tuple[Device, Monitor]] = dict()
        self.__refresh_flag = False
        self.__lock = threading.Lock()

    def run(self):
        if not self.__mqtt_client.connected():
            time.sleep(3)
        logger.info("starting '{}' ...".format(self.name))
        while True:
            if self.__refresh_flag:
                self.__refresh_devices()
            try:
                discovered_devices = validate_hosts(discover_hosts())
                self.__evaluate(discovered_devices)
            except Exception as ex:
                logger.error("discovery failed - {}".format(ex))
            time.sleep(conf.Discovery.delay)

    def __diff(self, known: dict, unknown: dict):
        known_set = set(known)
        unknown_set = set(unknown)
        missing = known_set - unknown_set
        new = unknown_set - known_set
        changed = {key for key in known_set & unknown_set if dict(known[key][0]) != unknown[key]}
        return missing, new, changed

    def __handle_missing_device(self, device_id: str):
        try:
            device, monitor = self.__device_pool[device_id]
            logger.info("can't find '{}' with id '{}'".format(device.name, device.id))
            self.__mqtt_client.publish(
                topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                payload=json.dumps(mgw_dc.dm.gen_delete_device_msg(device)),
                qos=1
            )
            monitor.stop()
            del self.__device_pool[device.id]
        except Exception as ex:
            logger.error("can't remove '{}' - {}".format(device_id, ex))

    def __handle_new_device(self, device_id: str, data: dict):
        try:
            device = Device(id=device_id, **data)
            device.state = mgw_dc.dm.device_state.online
            logger.info("found '{}' with id '{}'".format(device.name, device_id))
            self.__mqtt_client.publish(
                topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                payload=json.dumps(mgw_dc.dm.gen_set_device_msg(device)),
                qos=1
            )
            monitor = Monitor(device=device, mqtt_client=self.__mqtt_client)
            monitor.start()
            self.__device_pool[device.id] = (device, monitor)
        except Exception as ex:
            logger.error("can't add '{}' - {}".format(device_id, ex))

    def __handle_changed_device(self, device_id: str, data: dict):
        try:
            device, _ = self.__device_pool[device_id]
            backup = dict(device)
            device.name = data["name"]
            device.ip_address = data["ip_address"]
            if backup["name"] != data["name"]:
                try:
                    self.__mqtt_client.publish(
                        topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                        payload=json.dumps(mgw_dc.dm.gen_set_device_msg(device)),
                        qos=1
                    )
                except Exception as ex:
                    device.name = backup["name"]
                    raise ex
        except Exception as ex:
            logger.error("can't update '{}' - {}".format(device_id, ex))

    def __evaluate(self, queried_devices):
        try:
            missing_devices, new_devices, changed_devices = self.__diff(self.__device_pool, queried_devices)
            if missing_devices:
                for device_id in missing_devices:
                    self.__handle_missing_device(device_id)
            if new_devices:
                for device_id in new_devices:
                    self.__handle_new_device(device_id, queried_devices[device_id])
            if changed_devices:
                for device_id in changed_devices:
                    self.__handle_changed_device(device_id, queried_devices[device_id])
        except Exception as ex:
            raise RuntimeError("can't evaluate devices - {}".format(ex))

    def __refresh_devices(self):
        with self.__lock:
            self.__refresh_flag = False
        for device, _ in self.__device_pool.values():
            try:
                self.__mqtt_client.publish(
                    topic=mgw_dc.dm.gen_device_topic(conf.Client.id),
                    payload=json.dumps(mgw_dc.dm.gen_set_device_msg(device)),
                    qos=1
                )
            except Exception as ex:
                logger.error("setting device '{}' failed - {}".format(device.id, ex))

    def schedule_refresh(self):
        with self.__lock:
            self.__refresh_flag = True
