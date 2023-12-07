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
    if not a:
        return b
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

        print('Wifi connected')
        self.status['wifi'] = True
        await sleep(0)
        
        self.pool = SocketPool(wifi.radio)
        self.ssl_context = ssl_create_default_context()

        self.ssl_context.load_cert_chain(
            certfile=getenv('DEVICE_CERT_PATH'),
            keyfile=getenv('DEVICE_KEY_PATH'),
        )

        print('SSL setup')
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

        print('MQTT client configured')
        self.status['mqtt'] = True
        await sleep(0)
        
        self.mqtt.connect()

        print('MQTT connected')
        self.status['connect'] = True
        await sleep(0)
        
        self.mqtt.subscribe(self.SUB_CHANNEL)

        print('MQTT subscribed')
        self.status['subscribe'] = True
        gc.collect()
        await sleep(0)
        
        self.reported_at = -999.0
        
    def disconnect(self):
        print('MQTT: DISCONNECTING...')
        self.status['mqtt'] = False
        self.status['connect'] = False
        self.status['subscribe'] = False
        self.status['published'] = False
        self.mqtt = None
        gc.collect()
        
    def handle_message(self, topic, msg):
        print('MQTT: topic', topic, 'message:')
        print(msg)
        if topic.decode() == self.SUB_CHANNEL:
            self.state.handle_delta(json.loads(msg.decode()))

    def reported_state(self):
        current = {
            "now": time.monotonic(),
            "mode": self.state.mode,
            "auto": self.state.auto_state.reported,
            "manual": self.state.manual_state.reported,
            "alarm": self.state.alarm_state.reported,
        }
        delta = dict_difference(self.last_reported, current)
        print(delta)
        self.last_reported = current
        return delta

    def desired_state(self):
        return {
            "alarm": self.state.alarm_state.desired,
        }

    def publish(self, desired=False):
        msg = {
            "state": {"reported": self.reported_state()}
        }
        if desired:
            msg['state']['desired'] = self.desired_state()
        self.mqtt.publish(
            topic=self.PUB_CHANNEL,
            msg=json.dumps(msg).encode(),
            qos=0
        )
        print('MQTT: message published')
        self.reported_at = time.monotonic()
        self.status['published'] = True
    
    async def run(self):
        await self.boot()
        
        while True:
            try:
                changed = self.state.should_report_now()
                if changed or time.monotonic() - self.reported_at > 60.0:
                    self.publish(changed)
            
                self.mqtt.check_msg()
            except:
                self.disconnect()
                await sleep(15.0)
                await self.start_mqtt()
            
            await sleep(4.0)
