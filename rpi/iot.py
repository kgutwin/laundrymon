import gc
import time
from os import getenv
from ssl import create_default_context as ssl_create_default_context
import json
import wifi
from socketpool import SocketPool
from asyncio import sleep

import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_aws_iot import MQTT_CLIENT


class IOT:
    def __init__(self, state):
        self.state = state

        pool = SocketPool(wifi.radio)
        ssl_context = ssl_create_default_context()

        ssl_context.load_cert_chain(
            certfile=getenv('DEVICE_CERT_PATH'),
            keyfile=getenv('DEVICE_KEY_PATH'),
        )

        print(getenv('BROKER'))
        mqtt = MQTT.MQTT(
            broker=getenv('BROKER'),
            port=getenv('PORT'),
            is_ssl=True,
            client_id=getenv('CLIENT_ID'),
            socket_pool=pool,
            ssl_context=ssl_context,
        )

        self.aws_iot = MQTT_CLIENT(mqtt)
        self.aws_iot.on_message = self.handle_message
        self.aws_iot.connect()
        #self.aws_iot.shadow_subscribe()

        # TODO: try using umqtt/simple.py from rp_pico_w_aws_iot
        # should be able to do a pretty straight port
        
    def handle_message(self, client, topic, msg):
        #print('topic', topic, 'message:')
        #print(msg)
        pass

    def reported_state(self):
        return {
            #"washer": None,
            "now": time.monotonic(),
            "mode": self.state.mode,
            "auto": self.state.auto_state.reported,
            #"manual": self.state.manual_state.reported,
            "alarm": self.state.alarm_state.reported,
        }
    
    async def run(self):
        reported_at = 0
        while True:
            if time.monotonic() - reported_at > 60.0:
                self.aws_iot.shadow_update(json.dumps({
                    "state": {"reported": self.reported_state()}
                }))
                reported_at = time.monotonic()
            
            try:
                if self.aws_iot.connected_to_aws:
                    self.aws_iot.client.loop()
            except MQTT.MMQTTException as ex:
                pass
            
            await sleep(4.0)
