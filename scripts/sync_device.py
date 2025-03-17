from dcim.models import Device
from extras.scripts import Script, StringVar

from device_class.devices import CiscoIOS, RouterOS
from device_class.connections import SSH, TCPSocket
from device_class.devices import Device as DC

DEVICE_PLATFORM_MAP = {
    'ios': CiscoIOS,
    'routeros': RouterOS,
}

DEVICE_CONNECTION_MAP = {
    'ssh': SSH,
    'telnet': TCPSocket,
}

class SyncDevice(Script):
    class Meta:
        name = "Import Device"
        description = "Connect to a device via SSH and import it into NetBox"

        username = StringVar(name='Username')
        password = StringVar(name='Password')
        enable = StringVar(name='Enable')

    def run(self, data, commit):
        devices = Device.objects.all()

        if not devices: self.log_failure('No device to preform operation'); return

        for device in devices:
            if device.platform is None: self.log_warning('device does not have any platform', device); return
            device_detail = {
                'host': '',
                'port': None,
            }
            device_detail.update(data)

            connection_type = None
            for service in device.services:
                if service.name == 'SSH': 
                    connection_type = 'ssh'
                    device_detail['port'] = service.ports[0]
                    break

            if connection_type is None: self.log_warning('no connection method detected for device', device); return
            connection_class = DEVICE_CONNECTION_MAP.get(connection_type)

            dc_class = DEVICE_PLATFORM_MAP.get(device.platform.slug.lower())
            dc: DC = dc_class(**device_detail)
            dc.create_connection(connection_class)

            with dc.connection:
                dc.on_connect()
                current_hostname = dc.get_hostname()
                if current_hostname != device.name: self.log_warning(f'device hostname mismatch: current->{current_hostname}, netbox->{device.name}')
                dc.on_disconnect()
