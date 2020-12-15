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


__all__ = ("Monitor", )


from util import get_logger, conf, MQTTClient
from .device import Device
from .service import get_readings
import threading
import time
import json
import mgw_dc


logger = get_logger(__name__.split(".", 1)[-1])


class Monitor(threading.Thread):
    def __init__(self, device: Device, mqtt_client: MQTTClient):
        super().__init__(name="monitor-{}".format(device.id), daemon=True)
        self.__device = device
        self.__mqtt_client = mqtt_client
        self.__stop = False

    def run(self) -> None:
        logger.info("starting '{}' ...".format(self.name))
        while not self.__stop:
            try:
                readings = get_readings(self.__device)
                for srv_name, data in readings:
                    self.__mqtt_client.publish(
                        topic=mgw_dc.com.gen_event_topic(self.__device.id, srv_name),
                        payload=json.dumps(data),
                        qos=1
                    )
            except Exception as ex:
                logger.error("'{}': {}".format(self.name, ex))
            time.sleep(conf.Api.delay)
        logger.debug("'{}': quit".format(self.name))

    def stop(self):
        self.__stop = True
