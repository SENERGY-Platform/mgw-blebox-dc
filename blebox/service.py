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


__all__ = ("get_readings", )


from util import conf
from .device import Device
import datetime
import requests


def map_readings(data):
    time = '{}Z'.format(datetime.datetime.utcnow().isoformat())
    readings = list()
    for reading in data:
        readings.append(
            (
                "reading_{}".format(reading['type']),
                {
                    'value': reading['value'],
                    'unit': 'µg/m³',
                    'time': time
                }
            )
        )
    return readings


def get_readings(device: Device):
    try:
        resp = requests.get(
            url="http://{}/{}".format(device.ip_address, conf.Api.air_sensor_state),
            timeout=conf.Discovery.timeout
        )
        if resp.status_code == 200:
            resp = resp.json()
            return map_readings(resp['air']['sensors'])
        else:
            raise RuntimeError(resp.status_code)
    except Exception as ex:
        raise RuntimeError("could not get readings from '{}' - {}".format(device.id, ex))
