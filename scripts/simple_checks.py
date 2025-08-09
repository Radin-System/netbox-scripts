import random, string, requests
from typing import Iterator, Literal, LiteralString
from extras.scripts import Script
from dcim.models import Site, Device
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
    name: LiteralString = 'API Friendly IP Address'
    description: LiteralString = 'Sets the IP address as custom field in devices and machines'
    commit_default: Literal[True] = True

    def run(self, data: dict, commit: bool) -> None:
        # Helper Function
        def init_objects(objects: Iterator[Device|VirtualMachine]) -> None:
            for obj in objects if objects else []:
                self.log_debug('Initiating Object', obj)

                api_freindly_ip = obj.custom_field_data.get('api_friendly_primary_ip')

                # Check for device ip address                
                if not obj.primary_ip:
                    self.log_failure('Object has no IP Address', obj)
                    # Remove friendly ip if exists
                    if api_freindly_ip:
                        if commit:
                            obj.snapshot()
                            obj.custom_field_data['api_friendly_primary_ip'] = None
                            obj.full_clean()
                            obj.save()
                            self.log_success(f'Address removed: {current_ip}', obj)
                        else:
                            self.log_info(f'Address removal not commited', obj)
                    continue

                current_ip = str(obj.primary_ip.address.ip)

                # Check unmodified
                if api_freindly_ip == current_ip:
                    self.log_info(f'Unchanged address: {current_ip}', obj)
                    continue

                # Save Changes
                if commit:
                    obj.snapshot()
                    obj.custom_field_data['api_friendly_primary_ip'] = current_ip
                    obj.full_clean()
                    obj.save()
                    self.log_success(f'Address set: {current_ip}', obj)

                self.log_info(f'Address not commited: {current_ip}', obj)

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
        init_objects(devices) # type: ignore
        self.log_debug('Initiating Devices: Done')

        self.log_debug('Initiating VirtualMachines: Started')
        init_objects(vms) # type: ignore
        self.log_debug('Initiating VirtualMachines: Done')


class OxidizedIntegration(Script):
    name: LiteralString = 'Oxidized Integration'
    description: LiteralString = 'Checks the device and adds oxiback tag if device has the standards.'
    commit_default: Literal[True] = True

    def run(self, data: dict, commit: bool) -> None:
        self.log_info(f'Commit mode: {'yes' if commit else 'no'}')

        self.log_info('Getting devices and oxiback Tag from database')
        
        devices = Device.objects.all()
        if not devices: raise AbortScript('No device to preform operation')

        oxiback_tag = Tag.objects.get(name='Oxiback')
        if not oxiback_tag: raise AbortScript('Unable to get oxiback tag')

        reload_oxidized = None

        for device in devices:
            self.log_debug('Initiating Device', device)
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


            if device.tags.filter(id=oxiback_tag.id).exists():
                self.log_info('Device already has `oxiback` tag', device)
                continue

            if commit:
                    device.tags.add(oxiback_tag)
                    self.log_success('Tag Added to Device', device)
                    reload_oxidized = True
            else:
                self.log_info('Changes not Commited', device)

        if reload_oxidized:
            self.log_info('Changes Detected, sending refresh request to oxidized')
            response = requests.get('http://192.168.205.46:8888/reload', headers={'content-type': 'application/json'})

            if response and response.status_code == 200:
                self.log_success('Refreshed Oxidized Data List')
            else:
                self.log_failure('Requests finished with non 200 status code')


class GenerateSuppotToken(Script):
    name: LiteralString = 'Generate Support Token'
    description: LiteralString = 'Creates random generated token for sites'
    commit_default: Literal[True] = True

    def run(self, data: dict, commit: bool) -> None:
        self.log_info(f'Commit mode: {'yes' if commit else 'no'}')

        sites = Site.objects.all()
        if not sites: raise AbortScript('No sites to preform operation')
        self.log_info('Got all the sites')

        self.log_debug('Checking Custom fields: Started')
        if 'radin_api_token' not in sites[0].cf:
            raise AbortScript('Custom Field is not defined: radin_api_token')

        else:
            self.log_debug('Checking Custom fields: Passed') 

        for site in sites:
            if site.cf['radin_api_token'] is not None:
                self.log_info(f'Tenant already has token', site)
                continue
            
            if commit:
                self.log_debug(f'Generating token', site)
                new_token =  generate_random_string(32, punctuation=False)
                site.snapshot()
                site.custom_field_data['radin_api_token'] = new_token
                site.full_clean()
                site.save()
                self.log_success(f'Created new token', site)

            else:
                self.log_warning(f'No Token Found', site)
