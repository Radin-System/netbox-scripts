import random, string
from typing import Iterator
from extras.scripts import Script
from dcim.models import Device
from tenancy.models import Tenant
from extras.models import Tag
from virtualization.models import VirtualMachine
from utilities.exceptions import AbortScript


def generate_random_string(length:int=10,*,
        ascii:bool = True,
        digits:bool = True,
        punctuation:bool = True,
        ) -> str:

        chars = ''
        if ascii: chars += string.ascii_letters
        if digits: chars += string.digits
        if punctuation: chars += string.punctuation

        return ''.join(random.choice(chars) for _ in range(length))


class APIFriendlyIPAddress(Script):
    name = 'API Friendly IP Address'
    description = 'Sets the IP address as custom field in devices and machines'
    commit_default = True

    def run(self, data: dict, commit: bool) -> None:
        def init_objects(objects: Iterator[Device|VirtualMachine]) -> None:
            for obj in objects if objects else []:
                self.log_debug('Initiating Object', obj)

                if not obj.primary_ip:
                    self.log_failure('Object has no IP Address', obj)
                    continue

                ip_address = str(obj.primary_ip.address.ip)

                if obj.custom_field_data.get('api_friendly_primary_ip') == ip_address:
                    self.log_info(f'Unchanged address: {ip_address}', obj)
                    continue

                if commit:
                    obj.snapshot()
                    obj.custom_field_data['api_friendly_primary_ip'] = ip_address
                    obj.full_clean()
                    obj.save()
                    self.log_success(f'Address set: {ip_address}', obj)
                
                self.log_warning(f'Address not commited: {ip_address}', obj)

        self.log_info(f'Commit mode: {'yes' if commit else 'no'}')

        self.log_info('Getting objects from database')
        devices = Device.objects.all()
        vms =  VirtualMachine.objects.all()

        if not devices: self.log_failure('No device to preform operation')
        if not vms: self.log_failure('No vm to preform operation')
        if not devices and not vms: raise AbortScript

        self.log_debug('Checking Custom Fields: Started')
        if devices and 'api_friendly_primary_ip' not in devices[0].cf:
            raise AbortScript('Custom Field is not defined in Devices: api_friendly_primary_ip')
        
        if vms and 'api_friendly_primary_ip' not in vms[0].cf:
            raise AbortScript('Custom Field is not defined in VirtualMachines: api_friendly_primary_ip')
        self.log_debug('Checking Custom Fields: Passed') 

        self.log_debug('Initiating Devices: Started')
        init_objects(devices)
        self.log_debug('Initiating Devices: Done')

        self.log_debug('Initiating VirtualMachines: Started')
        init_objects(vms)
        self.log_debug('Initiating VirtualMachines: Done')


class OxibackAdder(Script):
    name = 'Oxiback Adder'
    description = 'Checks the device and adds oxiback tag if device has the standards.'
    commit_default = True

    def run(self, data: dict, commit: bool) -> None:
        self.log_info(f'Commit mode: {'yes' if commit else 'no'}')

        self.log_info('Getting devices and oxiback Tag from database')
        
        devices = Device.objects.all()
        if not devices: raise AbortScript('No device to preform operation')

        oxiback_tag = Tag.objects.get('oxiback')
        if not oxiback_tag: raise AbortScript('Unable to get oxiback tag')

        for device in devices:
            fail_condition = None
            fail_notes = []

            if device.site is None: 
                fail_condition = True
                self.log_debug('Device does not have any site', device)
                fail_notes.append('Add device to any site')
            
            if device.platform is None: 
                fail_condition = True
                self.log_debug('Device does not have any platform', device)
                fail_notes.append('Define the platform of Device')
            
            if device.primary_ip is None: 
                fail_condition = True
                self.log_debug('Device does not have primary_ip', device)
                fail_notes.append('Define the primary ip address of device')

            if device.cf.get('api_friendly_primary_ip') is None: 
                fail_condition = True
                self.log_debug('Device `api_friendly_primary_ip` Custom Field is not defined', device)
                fail_notes.append('Run `APIFriendlyIPAddress` Script for initiation')


            if fail_condition:
                self.log_failure('Adding device to oxiback failed', device)
                [self.log_warning(fail_note, device) for fail_note in fail_notes]
                continue

            if commit:
                device.tags.add(oxiback_tag)


class GenerateSuppotToken(Script):
    name = 'Generate Support Token'
    description = 'Creates random generated token for tenants'
    commit_default = True

    def run(self, data: dict, commit: bool) -> None:
        self.log_info(f'Commit mode: {'yes' if commit else 'no'}')

        tenants = Tenant.objects.all()
        if not tenants: raise AbortScript('No tenants to preform operation')

        self.log_info('Got all the tenants')

        self.log_debug('Checking Custom fields: Started')
        if 'support_token' not in tenants[0].cf:
            raise AbortScript('Custom Field is not defined: support_token')

        else:
            self.log_debug('Checking Custom fields: Passed') 

        for tenant in tenants:
            if tenant.cf['support_token'] is not None:
                self.log_info(f'Tenant already has token', tenant)
                continue
            
            if commit:
                self.log_debug(f'Generating token', tenant)
                new_token =  generate_random_string(32, punctuation=False)
                tenant.snapshot()
                tenant.custom_field_data['support_token'] = new_token
                tenant.full_clean()
                tenant.save()
                self.log_success(f'Created new token', tenant)

            else:
                self.log_warning(f'No Token Found', tenant)