from dcim.models import Device, Site, DeviceRole, Platform, Manufacturer, DeviceType
from extras.scripts import Script


class SyncDevice(Script):
    class Meta:
        name = "Import Device"
        description = "Connect to a device via SSH and import it into NetBox"

    def run(self, data, commit):
        devices = Device.objects.all()

        if not devices:
            self.log_failure('No device to preform operation')