from extras.scripts import Script
from dcim.models import Device
from virtualization.models import VirtualMachine
from utilities.exceptions import AbortScript


class APIFriendlyIPAddress(Script):
    name = 'API Friendly IP Address'
    description = 'Sets the IP address as custom field in devices and machines'
    commit_default = True

    def run(self, data: dict, commit: bool) -> None:
        self.log_info(f'Commit mode: {'yes' if commit else 'no'}')

        self.log_info('Initiating All Devices')
        devices = Device.objects.all()

        if devices:
            self.log_debug('Checking Custom fields: Started')
            if 'api_friendly_primary_ip' not in devices[0].cf:
                raise AbortScript('Custom Field is not defined: api_friendly_primary_ip')

            else:
                self.log_debug('Checking Custom fields: Passed') 

            for device in devices:
                self.log_debug('Initiating Device', device)

                if not device.primary_ip:
                    self.log_warning('Device has no IP Address', device)
                    continue

                ip_address = str(device.primary_ip.address.ip)

                if device.custom_field_data.get('api_friendly_primary_ip') == ip_address:
                    self.log_info(f'Unchanged address: {ip_address}', device)
                    continue

                if commit:
                    device.snapshot()
                    device.custom_field_data['api_friendly_primary_ip'] = ip_address
                    device.full_clean()
                    device.save()

                self.log_success(f'Address set: {ip_address}', device)

        else:
            self.log_warning(f'Device Count is zero')

        self.log_info('-------------------------------')
        self.log_info('Initiating All Virtual Machines')
        machines = VirtualMachine.objects.all()

        if machines:
            self.log_debug('Checking Custom fields: Started')
            if 'api_friendly_primary_ip' not in machines[0].cf:
                raise AbortScript('Custom Field is not defined: api_friendly_primary_ip')

            else:
                self.log_debug('Checking Custom fields: Passed') 

            for machine in machines:
                self.log_debug('Initiating Machine', machine)

                if not machine.primary_ip:
                    self.log_warning('Machine has no IP Address', machine)
                    continue

                ip_address = str(machine.primary_ip.address.ip)

                if machine.custom_field_data.get('api_friendly_primary_ip') == ip_address:
                    self.log_info(f'Unchanged address: {ip_address}', machine)
                    continue

                if commit:
                    machine.snapshot()        
                    machine.custom_field_data['api_friendly_primary_ip'] = ip_address
                    machine.full_clean()
                    machine.save()

                self.log_success(f'Address set: {ip_address}', machine)

        else:
            self.log_warning(f'machine Count is zero')
