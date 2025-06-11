from typing import Any, Dict, Literal, LiteralString
from zabbix_utils import ZabbixAPI
from extras.scripts import Script
from dcim.models import Device
from utilities.exceptions import AbortScript
from netbox.plugins import get_plugin_config


Zabbix_Config: Dict[str, Any] = {
    'url': get_plugin_config('netbox_zabbix_integration', 'url'),
    'token': get_plugin_config('netbox_zabbix_integration', 'token'),
    'user': get_plugin_config('netbox_zabbix_integration', 'user'),
    'password': get_plugin_config('netbox_zabbix_integration', 'password'),
    'validate_certs': get_plugin_config('netbox_zabbix_integration', 'validate_certs'),
}
Zabbix_Config = {k: v for k, v in Zabbix_Config.items() if v is not None}

class ZabbixMixin:
    log_debug = Script.log_debug
    log_info = Script.log_info
    log_failure = Script.log_failure

    def init_zabbix(self, config: Dict[str, Any]) -> None:
        self.zabbix_client = ZabbixAPI(**config)
        self.zabbix_config = config

        # Getting Version
        zabbix_version = self.zabbix_client.api_version()
        self.log_info(f'Initiated Zabbix Client - Version: {zabbix_version}')

    def validate_device_custom_fields(self, devices) -> None:
        if not devices:
            if not devices: self.log_failure('No device to preform operation')

        if devices and 'zabbix_host_id' not in devices[0].cf:
            raise AbortScript('Custom Field is not defined in Devices: zabbix_host_id')

    def get_id_by_hostname(self, hostname) -> int | None:
        response = self.zabbix_client.send_api_request(
            method='host.get',
            params={
                'filter': {
                    'host': hostname,
                },
                'output': ['hostid'],
            }
        )

        result: list = response.get('result') # type: ignore

        if response and len(result) > 0:
            first_host: dict = result[0]
            return first_host.get('hostid') 

        else:
            return None


class Zabbix_CheckHosts(Script, ZabbixMixin):
    name: LiteralString = 'Zabbix - Check Hosts'
    description: LiteralString = 'Checks All Devices'
    commit_default: Literal[True] = True

    def run(self, data: dict, commit: bool) -> None:
        # initiate Zabbix Api
        self.init_zabbix(Zabbix_Config)

        # Check if the device has custom fields neccesery.
        devices = Device.objects.all()
        self.validate_device_custom_fields(devices)

        for device in devices:
            self.log_debug('Initiating Object', device)

            if device.cf.get('zabbix_host_id'):
                self.log_debug('Object has zabbix id set')

            else:
                self.log_warning('Object Does not have zabbix id set in custom field')
                self.log_debug('Trying to lookup the object', device)
                zabbix_host_id = self.get_id_by_hostname(device.name)

                if zabbix_host_id is not None:
                    self.log_info(f'Found the id from zabbix: {self.zabbix_config['url']}//zabbix.php?action=popup&popup=host.edit&hostid={zabbix_host_id}')
                
                else:
                    self.log_info(f'Device Not Found Skipping')
                    continue
