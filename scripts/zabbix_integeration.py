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

    def check_id(self, device: Device, commit: bool) -> int | None:
        # Getting ID from cf or zabbix itself
        zabbix_host_id: int | None = device.cf.get('zabbix_host_id') or self.get_id_by_hostname(device.name)

        if zabbix_host_id:
            self.log_info(f'Device on Zabbix: <a href="{self.zabbix_config['url']}//zabbix.php?action=popup&popup=host.edit&hostid={zabbix_host_id}">Zabbix: {device.name}</a>', device)
            
            # Check if Device has the id set in `zabbix_host_id` and set it
            if not device.cf.get('zabbix_host_id') and commit:
                self.log_debug(f'Saving new device id {zabbix_host_id}', device)
                device.snapshot()
                device.custom_field_data['zabbix_host_id'] = zabbix_host_id
                device.full_clean()
                device.save()
                self.log_success(f'Saved new id: {zabbix_host_id}', device)
            
            else:
                self.log_warning('Found ID from zabbix but cannot save it: commit = False')

            return int(zabbix_host_id)

        else:
            self.log_warning(f'No Device ID Found on Zabbix or Netbox, Check hostname on both services')
            return None


    def run(self, data: dict, commit: bool) -> None:
        # initiate Zabbix Api
        self.init_zabbix(Zabbix_Config)

        # Check if the device has custom fields neccesery.
        devices = Device.objects.all()
        self.validate_device_custom_fields(devices)

        for device in devices:
            self.log_debug('Initiating Object', device)

            try:
                zabbix_host_id = self.check_id(device, commit)

            except Exception as e:
                self.log_failure(f'Error While initiating device: {e}', device)
