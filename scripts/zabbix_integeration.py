from typing import Any, Dict, Literal, LiteralString, Optional, Type
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

    def generate_zabbix_host_link(self, host_id: int, device: Device) -> str:
        """Creates Human Clickable link for host"""
        return f'<a href="{self.zabbix_config['url']}//zabbix.php?action=popup&popup=host.edit&hostid={host_id}">Zabbix: {device.name}</a>'

    def get_id_by_hostname(self, hostname: str|None) -> int | None:
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
            zabbix_host_id = first_host.get('hostid')
            return int(zabbix_host_id) if zabbix_host_id is not None else None

    def get_host_parameter(self, host_id: int, output: str, output_type: Type = str) -> None:
        response = self.zabbix_client.send_api_request(
            method='host.get',
            params={
                'filter': {
                    'hostid': host_id,
                },
                'output': [output]
            }
        )
        result: list = response.get('result') # type: ignore

        if response and len(result) > 0:
            first_host: dict = result[0]
            return output_type(first_host.get(output))

    def set_host_parameter(self, host_id: int, key: str, value: Any) -> None:
        self.zabbix_client.send_api_request(
            method='host.update',
            params={
                'hostid': host_id,
                key: value,
            }
        )

class Zabbix_CheckHosts(Script, ZabbixMixin):
    name: LiteralString = 'Zabbix - Check Hosts'
    description: LiteralString = 'Checks All Devices'
    commit_default: Literal[True] = True

    def generate_compare_log(self, parameter: str, zabbix_version: Any, netbox_version: Any) -> str:
        return f'Comparing Parameter ({parameter}):\n  - zabbix={zabbix_version}\n  - netbox={netbox_version}'

    def generate_commit_off_log(self, parameter: str) -> str:
        return f'Unable to push or pull ({parameter}) --> commit=False'

    def generate_changed_parameter_log(self, parameter: str, change_type: Literal['push', 'pull'], value: Any) -> str:
        if change_type == 'push': start_text = 'Pushed to Zabbix'
        elif change_type == 'pull': start_text = 'Pulled From Zabbix'
        return f'{start_text} Parameter ({parameter}): {value}'

    def get_zabbix_host_id(self, device: Device) -> int:
        """Get Zabbix Host ID From Device Custom Fields or From zabbix Server"""
        zabbix_host_id = device.cf.get('zabbix_host_id') or self.get_id_by_hostname(device.name)
        if not zabbix_host_id:
            raise Exception('No Device ID Found on Zabbix or Netbox, Check hostname on both services.')

        return zabbix_host_id

    def sync_id(self, device: Device, zabbix_host_id: int, commit: bool) -> None:
        """Checks if Device has host id set in `zabbix_host_id`"""
        if not device.cf.get('zabbix_host_id'):
            if commit:
                self.log_debug(f'Saving new device id {zabbix_host_id}', device)
                device.snapshot()
                device.custom_field_data['zabbix_host_id'] = zabbix_host_id
                device.full_clean()
                device.save()
                self.log_success(self.generate_changed_parameter_log('hostid', 'pull', zabbix_host_id), device)

            else:
                self.log_warning(self.generate_commit_off_log('hostid'), device)

    def sync_hostname(self, device: Device, zabbix_host_id: int, commit: bool) -> None:
        """Syncs hostname from saved cf id (Keeps Netbox Version)"""
        zabbix_hostname = self.get_host_parameter(zabbix_host_id, 'host', str)
        self.log_debug(self.generate_compare_log('hostname', zabbix_hostname, device.name), device)

        if not device.name == zabbix_hostname:
            if commit:
                self.set_host_parameter(zabbix_host_id, 'host', device.name)
                self.log_success(self.generate_changed_parameter_log('hostname', 'push', device.name), device)

            else:
                self.log_warning(self.generate_commit_off_log('hostname'), device)

    def sync_status(self, device: Device, zabbix_host_id: int, commit: bool) -> None:
        """Syncs device Status from saved cf id (Keeps Netbox Version)"""
        zabbix_status = self.get_host_parameter(zabbix_host_id, 'status', int) # 0=Enable, 1=Disable
        self.log_debug(self.generate_compare_log('status', 'enable' if zabbix_status == 0 else 'disable', device.status), device)

        if device.status == 'offline' and zabbix_status == 0:
            if commit:                
                self.set_host_parameter(zabbix_host_id, 'status', 1)
                self.log_success(self.generate_changed_parameter_log('status', 'push', 'disable'), device)

            else:
                self.log_warning(self.generate_commit_off_log('status'), device)

        elif device.status != 'offline' and zabbix_status == 1:
            if commit:
                self.set_host_parameter(zabbix_host_id, 'status', 0)
                self.log_success(self.generate_changed_parameter_log('status', 'push', 'enable'), device)

            else:
                self.log_warning(self.generate_commit_off_log('status'), device)

    def sync_description(self, device: Device, zabbix_host_id: int, commit: bool) -> None:
        """Syncs device Description from saved cf id (Keeps Netbox Version)"""
        zabbix_description = self.get_host_parameter(zabbix_host_id, 'description')
        self.log_debug(self.generate_compare_log('description', '<Description>', '<Comments>'), device)

        if not device.comments == zabbix_description:
            if commit:
                self.set_host_parameter(zabbix_host_id, 'description', device.comments)
                self.log_success(self.generate_changed_parameter_log('hostname', 'push', '<Comments>'), device)
            
            else:
                self.log_warning(self.generate_commit_off_log('description'))

    def run(self, data: dict, commit: bool) -> None:
        # initiate Zabbix Api
        self.init_zabbix(Zabbix_Config)

        # Check if the device has custom fields neccesery.
        devices = Device.objects.all()
        self.validate_device_custom_fields(devices)

        for device in devices:
            try:
                zabbix_host_id: int = self.get_zabbix_host_id(device)
                self.log_info(f'Syncing from Zabbix: {self.generate_zabbix_host_link(zabbix_host_id, device)}', device)

                self.sync_id(device, zabbix_host_id, commit)
                self.sync_hostname(device, zabbix_host_id, commit)
                self.sync_status(device, zabbix_host_id, commit)
                self.sync_description(device, zabbix_host_id, commit)

            except Exception as e:
                self.log_failure(f'Error syncing: {e}', device)
