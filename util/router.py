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


__all__ = ("Router", )


from .logger import getLogger
import typing
import mgw_dc


logger = getLogger(__name__.split(".", 1)[-1])


class Router:
    def __init__(self, refresh_callback: typing.Callable, command_callback: typing.Callable):
        self.__refresh_callback = refresh_callback
        self.__command_callback = command_callback

    def route(self, topic: str, payload: typing.AnyStr):
        try:
            if topic == mgw_dc.dm.gen_refresh_topic():
                self.__refresh_callback()
            else:
                self.__command_callback((*mgw_dc.com.parse_command_topic(topic), payload))
        except Exception as ex:
            logger.error("can't route message - {}\n{}: {}".format(ex, topic, payload))
