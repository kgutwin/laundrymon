import gc
import time
from os import getenv
from ssl import create_default_context as ssl_create_default_context
import json
import wifi
from socketpool import SocketPool
from asyncio import sleep

from umqtt import MQTTClient


def dict_difference(a, b):
    rv = {}
    for k in a:
        if isinstance(a[k], dict):
            v = dict_difference(a[k], b[k])
            if v:
                rv[k] = v
        elif b[k] != a[k]:
            rv[k] = b[k]
    return rv


class IOT:
    PUB_CHANNEL = f'$aws/things/{getenv("CLIENT_ID")}/shadow/update'
    SUB_CHANNEL = f'$aws/things/{getenv("CLIENT_ID")}/shadow/update/delta'
    
    def __init__(self, state):
        self.state = state
        self.status = {
            'wifi': False,
            'ssl': False,
            'mqtt': False,
            'connect': False,
            'subscribe': False,
            'published': False,
        }
        self.last_reported = {}

    @property
    def connected(self):
        return all(self.status.values())
        
    @property
    def status_summary(self):
        if not all([self.status['wifi'], self.status['ssl']]):
            return 'Booting'
        if not all([self.status['mqtt'], self.status['connect'],
                    self.status['subscribe'], self.status['published']]):
            return 'Connecting'
        return 'Online'
        
    async def boot(self):
        """Start from first power-on.
        
        This should only be called once per system boot.
        """
        wifi.radio.connect(
            getenv('CIRCUITPY_WIFI_SSID'),
            getenv('CIRCUITPY_WIFI_PASSWORD'),
        )
        
        self.status['wifi'] = True
        await sleep(0)
        
        self.pool = SocketPool(wifi.radio)
        self.ssl_context = ssl_create_default_context()

        self.ssl_context.load_cert_chain(
            certfile=getenv('DEVICE_CERT_PATH'),
            keyfile=getenv('DEVICE_KEY_PATH'),
        )

        self.status['ssl'] = True
        await sleep(0)

        await self.start_mqtt()        
        
    async def start_mqtt(self):
        """Start the MQTT connection.

        This can be called any time a reconnection is needed.
        """        
        self.mqtt = MQTTClient(
            client_id=getenv('CLIENT_ID'),
            server=getenv('BROKER'),
            keepalive=10000,
            socket_pool=self.pool,
            ssl=True,
            ssl_context=self.ssl_context,
        )
        self.mqtt.set_callback(self.handle_message)

        self.status['mqtt'] = True
        await sleep(0)
        
        self.mqtt.connect()

        self.status['connect'] = True
        await sleep(0)
        
        self.mqtt.subscribe(self.SUB_CHANNEL)

        self.status['subscribe'] = True
        gc.collect()
        await sleep(0)
        
        self.reported_at = 0
        
    def disconnect(self):
        self.status['mqtt'] = False
        self.status['connect'] = False
        self.status['subscribe'] = False
        self.status['published'] = False
        self.mqtt = None
        gc.collect()
        
    def handle_message(self, topic, msg):
        #print('topic', topic, 'message:')
        #print(msg)
        pass

    def reported_state(self):
        current = {
            "now": time.monotonic(),
            "mode": self.state.mode,
            "auto": self.state.auto_state.reported,
            "manual": self.state.manual_state.reported,
            "alarm": self.state.alarm_state.reported,
        }
        delta = dict_difference(self.last_reported, current)
        self.last_reported = current
        return delta

    def publish(self):
        self.mqtt.publish(
            topic=self.PUB_CHANNEL,
            msg=json.dumps({
                "state": {"reported": self.reported_state()}
            }).encode(),
            qos=0
        )
        self.reported_at = time.monotonic()
        self.status['published'] = True
    
    async def run(self):
        await self.boot()
        
        while True:
            try:
                if (
                        self.state.should_report_now()
                        or time.monotonic() - self.reported_at > 60.0
                ):
                    self.publish()
            
                self.mqtt.check_msg()
            except:
                self.disconnect()
                await sleep(15.0)
                await self.start_mqtt()
            
            await sleep(4.0)
