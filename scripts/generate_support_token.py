import random, string
from utilities.exceptions import AbortScript
from extras.scripts import Script
from tenancy.models import Tenant

def Generate(length:int=10,*,
        ascii:bool = True,
        digits:bool = True,
        punctuation:bool = True,
        ) -> str:

        chars = ''
        if ascii: chars += string.ascii_letters
        if digits: chars += string.digits
        if punctuation: chars += string.punctuation

        return ''.join(random.choice(chars) for _ in range(length))

class GenerateSuppotToken(Script):
    name = 'Generate Support Token'
    description = 'Creates random generated token for tenants'
    commit_default = True

    def run(self, data: dict, commit: bool) -> None:
        self.log_info(f'Commit mode: {'yes' if commit else 'no'}')

        tenants = Tenant.objects.all()
        if not tenants: self.log_failure('No tenants to preform operation'); return

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
                new_token =  Generate(32, punctuation=False)
                tenant.snapshot()
                tenant.custom_field_data['support_token'] = new_token
                tenant.full_clean()
                tenant.save()
                self.log_success(f'Created new token', tenant)

            else:
                self.log_warning(f'No Token Found', tenant)