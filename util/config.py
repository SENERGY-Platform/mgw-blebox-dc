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
        id = "blebox-dc"

    @simple_env_var.section
    class Api:
        air_sensor_state = None
        air_sensor_device = None
        delay = 300

    @simple_env_var.section
    class Discovery:
        remote_host = None
        device_query_delay = 10
        device_id_prefix = None
        delay = 30
        check_delay = 60
        check_fail_safe = 2
        timeout = 5

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
    exit('Please provide a SENERGY device types')
