import gc
import time
from os import getenv
from ssl import create_default_context as ssl_create_default_context
import json
import wifi
from socketpool import SocketPool
from asyncio import sleep

from umqtt import MQTTClient


class IOT:
    PUB_CHANNEL = f'$aws/things/{getenv("CLIENT_ID")}/shadow/update'
    SUB_CHANNEL = f'$aws/things/{getenv("CLIENT_ID")}/shadow/update/delta'
    
    def __init__(self, state):
        self.state = state

        pool = SocketPool(wifi.radio)
        ssl_context = ssl_create_default_context()

        ssl_context.load_cert_chain(
            certfile=getenv('DEVICE_CERT_PATH'),
            keyfile=getenv('DEVICE_KEY_PATH'),
        )

        self.mqtt = MQTTClient(
            client_id=getenv('CLIENT_ID'),
            server=getenv('BROKER'),
            keepalive=10000,
            socket_pool=pool,
            ssl=True,
            ssl_context=ssl_context,
        )
        self.mqtt.set_callback(self.handle_message)
        self.mqtt.connect()
        self.mqtt.subscribe(self.SUB_CHANNEL)
        
        self.reported_at = 0
        
    def handle_message(self, topic, msg):
        #print('topic', topic, 'message:')
        #print(msg)
        pass

    def reported_state(self):
        return {
            "now": time.monotonic(),
            "mode": self.state.mode,
            "auto": self.state.auto_state.reported,
            "manual": self.state.manual_state.reported,
            "alarm": self.state.alarm_state.reported,
        }

    def publish(self):
        self.mqtt.publish(
            topic=self.PUB_CHANNEL,
            msg=json.dumps({
                "state": {"reported": self.reported_state()}
            }).encode(),
            qos=0
        )
        self.reported_at = time.monotonic()        
    
    async def run(self):
        while True:
            if (
                    self.state.should_report_now()
                    or time.monotonic() - self.reported_at > 60.0
            ):
                self.publish()
            
            self.mqtt.check_msg()
            
            await sleep(4.0)
