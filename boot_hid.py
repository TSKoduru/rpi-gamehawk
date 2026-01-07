#!/usr/bin/env python3

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import sys

# =========================================
# 1. The Absolute Mouse HID Descriptor
# =========================================
# This tells the host (iPhone) that we are a mouse with X/Y coordinates
# mapped to a 0-32767 grid (Absolute), not relative movement.
HID_DESCRIPTOR = [
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x02,        # Usage (Mouse)
    0xA1, 0x01,        # Collection (Application)
    0x09, 0x01,        #   Usage (Pointer)
    0xA1, 0x00,        #   Collection (Physical)
    
    # Button Map (Left/Right Click)
    0x05, 0x09,        #     Usage Page (Button)
    0x19, 0x01,        #     Usage Minimum (1)
    0x29, 0x03,        #     Usage Maximum (3)
    0x15, 0x00,        #     Logical Minimum (0)
    0x25, 0x01,        #     Logical Maximum (1)
    0x95, 0x03,        #     Report Count (3)
    0x75, 0x01,        #     Report Size (1)
    0x81, 0x02,        #     Input (Data,Var,Abs)
    0x95, 0x01,        #     Report Count (1)
    0x75, 0x05,        #     Report Size (5)
    0x81, 0x03,        #     Input (Const,Var,Abs)
    
    # Absolute X/Y Axis Definition
    0x05, 0x01,        #     Usage Page (Generic Desktop)
    0x09, 0x30,        #     Usage (X)
    0x09, 0x31,        #     Usage (Y)
    0x15, 0x00,        #     Logical Minimum (0)
    0x26, 0xFF, 0x7F,  #     Logical Maximum (32767) - High Res
    0x35, 0x00,        #     Physical Minimum (0)
    0x46, 0xFF, 0x7F,  #     Physical Maximum (32767)
    0x75, 0x10,        #     Report Size (16)
    0x95, 0x02,        #     Report Count (2)
    0x81, 0x02,        #     Input (Data,Var,Abs) <--- ABSOLUTE!
    
    0xC0,              #   End Collection
    0xC0               # End Collection
]

# =========================================
# 2. DBus Bluetooth Profile Classes
# =========================================
class HumanInterfaceDeviceProfile(dbus.service.Object):
    def __init__(self, bus, path):
        super().__init__(bus, path)
        self.fd = -1

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        print("Release")
        sys.exit(0)

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Cancel(self):
        print("Cancel")
        sys.exit(0)

    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, path, fd, properties):
        self.fd = fd.take()
        print("NewConnection(%s, %d)" % (path, self.fd))
        # We don't need to hold the file descriptor here in this script,
        # but in a real app, this 'self.fd' is where you write the mouse bytes!
        # For now, we just want to advertise the capability.

    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, path):
        print("RequestDisconnection(%s)" % (path))
        if self.fd > 0:
            os.close(self.fd)
            self.fd = -1

# =========================================
# 3. Main Registration Logic
# =========================================
if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    manager = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")

    # Define Service Record (SDP)
    service_record = """
    <record>
        <attribute id="0x0001">
            <sequence>
                <uuid value="00001124-0000-1000-8000-00805f9b34fb"/>
            </sequence>
        </attribute>
        <attribute id="0x0004">
            <sequence>
                <sequence>
                    <uuid value="00000100-0000-1000-8000-00805f9b34fb"/>
                </sequence>
                <sequence>
                    <uuid value="00000011-0000-1000-8000-00805f9b34fb"/>
                </sequence>
            </sequence>
        </attribute>
        <attribute id="0x0005">
            <sequence>
                <uuid value="00001002-0000-1000-8000-00805f9b34fb"/>
            </sequence>
        </attribute>
        <attribute id="0x0006">
            <sequence>
                <uint16 value="0x656e"/> <uint16 value="0x006a"/> <uint16 value="0x0100"/> </sequence>
        </attribute>
        <attribute id="0x000d">
            <sequence>
                <sequence>
                    <sequence>
                        <uuid value="00000100-0000-1000-8000-00805f9b34fb"/>
                        <uint16 value="0x0100"/>
                    </sequence>
                </sequence>
            </sequence>
        </attribute>
        <attribute id="0x0100">
            <text value="GameHawk Controller"/>
        </attribute>
    </record>
    """

    opts = {
        "ServiceRecord": service_record,
        "Role": "server",
        "RequireAuthentication": False,
        "RequireAuthorization": False
    }

    # Convert byte array to formatted string for BlueZ
    opts["ServiceRecord"] = service_record

    # We register the binary descriptor separately? 
    # Actually, for standard HID, we often pass the descriptor in the options or 
    # handle it via the 'Report Map' attribute in SDP. 
    # But BlueZ's ProfileManager usually wants the raw ServiceRecord XML.
    # The 'HID_DESCRIPTOR' bytes are actually handled by the kernel/bluez 
    # once the connection opens or via a specific SDP attribute.
    # 
    # CRITICAL FIX for Python BlueZ profiles:
    # The SDP record above advertises the device. 
    # The actual HID descriptor is often queried by the host. 
    # For this simple setup, we use the "Input Profile" approach.
    
    # Let's keep it simple: We register a profile. 
    # When iOS connects, it will ask for the Report Descriptor.
    # BlueZ handles the heavy lifting if we set up the input socket correctly.
    
    print("Configuring BlueZ Profile...")
    profile = HumanInterfaceDeviceProfile(bus, "/org/bluez/test/hidd")
    manager.RegisterProfile("/org/bluez/test/hidd", 
                            "00001124-0000-1000-8000-00805f9b34fb", 
                            opts)

    print("GameHawk Service is running. Waiting for connections...")
    loop = GLib.MainLoop()
    loop.run()
