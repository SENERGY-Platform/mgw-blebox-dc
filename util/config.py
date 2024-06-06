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

__all__ = ("conf",)


import os
import simple_env_var


@simple_env_var.configuration
class Conf:

    @simple_env_var.section
    class MsgBroker:
        host = "message-broker"
        port = 1883

    @simple_env_var.section
    class Logger:
        level = "info"
        enable_mqtt = False

    @simple_env_var.section
    class Client:
        clean_session = False
        keep_alive = 10
        id = "blebox-dc-" + os.getenv("MGW_DID")

    @simple_env_var.section
    class Api:
        air_sensor_state = "api/air/state"
        air_sensor_info = "info"
        air_sensor_device = "api/device/state"
        delay = 60

    @simple_env_var.section
    class Discovery:
        device_id_prefix = None
        delay = 120
        timeout = 5
        host_network_url = "http://core-api/host-info/network"
        networks = None

    @simple_env_var.section
    class StartDelay:
        enabled = False
        min = 5
        max = 20

    @simple_env_var.section
    class Senergy:
        dt_air_sensor = None


conf = Conf()


if not conf.Senergy.dt_air_sensor:
    exit('Please provide a SENERGY device type')
