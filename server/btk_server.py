#!/usr/bin/python3
#
# Bluetooth keyboard/Mouse emulator DBUS Service
#

from __future__ import absolute_import, print_function
from optparse import OptionParser, make_option
import os
import sys
import uuid
import dbus
import dbus.service
import dbus.mainloop.glib
import time
import socket
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop
import logging
from logging import debug, info, warning, error
import bluetooth
from bluetooth import *

logging.basicConfig(level=logging.DEBUG)

class Agent(dbus.service.Object):
    """ 
    BT Pairing agent
    API: https://git.kernel.org/pub/scm/bluetooth/bluez.git/plain/doc/agent-api.txt 
    examples: https://github.com/elsampsa/btdemo/blob/master/bt_studio.py 
    """

    @dbus.service.method('org.bluez.Agent1',
                    in_signature='os', out_signature='')
    def AuthorizeService(self, device, uuid):
        logging.info(f"[plover_link] Successfully paired device: {device} using Secure Simple Pairing (SSP)")
        return

    @dbus.service.method('org.bluez.Agent1',
                         in_signature='o', out_signature='')
    def RequestAuthorization(self, device):
        logging.info(f"[plover_link] Accepted RequestAuthorization from {device}")
        return

    @dbus.service.method('org.bluez.Agent1',
                         in_signature='', out_signature='')
    def Cancel(self):
        logging.info("[plover_link] Cancel request received from BT client")
        raise(BluezErrorCanceled)
    
    @dbus.service.method('org.bluez.Agent1',
                in_signature='', out_signature='')
    def Release(self):
        self.logging("[plover_link] Connection released due to BT client request")
        mainloop.quit()

class BTKbDevice():
    # change these constants
    MY_ADDRESS = "B8:27:EB:2C:6C:C7"
    MY_DEV_NAME = "test_keyboard_nio"

    # define some constants
    P_CTRL = 17  # Service port - must match port configured in SDP record
    P_INTR = 19  # Interrupt port - must match port configured in SDP record
    # dbus path of the bluez profile we will create
    # file path of the sdp record to load
    SDP_RECORD_PATH = sys.path[0] + "/sdp_record.xml"
    UUID = "00001124-0000-1000-8000-00805f9b34fb"

    def __init__(self):
        print("2. Setting up BT device")
        self.init_bt_device()
        self.init_bluez_profile()
        self.register_bt_pairing_agent()

    # configure the bluetooth hardware device
    def init_bt_device(self):
        print("3. Configuring Device name " + BTKbDevice.MY_DEV_NAME)
        # set the device class to a keybord and set the name
        os.system("hciconfig hci0 up")
        os.system("hciconfig hci0 name " + BTKbDevice.MY_DEV_NAME)
        # make the device discoverable
        os.system("hciconfig hci0 piscan")

    # set up a bluez profile to advertise device capabilities from a loaded service record
    def init_bluez_profile(self):
        print("4. Configuring Bluez Profile")
        # setup profile options
        service_record = self.read_sdp_service_record()
        opts = {
            "AutoConnect": True,
            "ServiceRecord": service_record
        }
        # retrieve a proxy for the bluez profile interface
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object(
            "org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
        manager.RegisterProfile("/org/bluez/hci0", BTKbDevice.UUID, opts)
        print("6. Profile registered ")
        os.system("hciconfig hci0 class 0x0025C0")

    def register_bt_pairing_agent(self):
        """
        Setup and register BT paring agent
        """
        print("start")
        capability = 'NoInputNoOutput'
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object('org.bluez',
                                                     '/org/bluez'),
                                 'org.bluez.AgentManager1')
        Agent(bus, '/org/bluez')

        manager.RegisterAgent('/org/bluez', capability)
        #manager.UnregisterAgent('/org/bluez', capability)
        manager.RequestDefaultAgent('/org/bluez')
        logging.debug(f'[plover_link] Registered secure Bluez pairing agent with capability: {capability}')
        print("done")

    # read and return an sdp record from a file
    def read_sdp_service_record(self):
        print("5. Reading service record")
        try:
            fh = open(BTKbDevice.SDP_RECORD_PATH, "r")
        except:
            sys.exit("Could not open the sdp record. Exiting...")
        return fh.read()

    # listen for incoming client connections
    def listen(self):
        print("\033[0;33m7. Waiting for connections\033[0m")
        self.scontrol = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)  # BluetoothSocket(L2CAP)
        self.sinterrupt = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)  # BluetoothSocket(L2CAP)
        self.scontrol.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sinterrupt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # bind these sockets to a port - port zero to select next available
        self.scontrol.bind((socket.BDADDR_ANY, self.P_CTRL))
        self.sinterrupt.bind((socket.BDADDR_ANY, self.P_INTR))

        # Start listening on the server sockets
        self.scontrol.listen(5)
        self.sinterrupt.listen(5)

        self.ccontrol, cinfo = self.scontrol.accept()
        print (
            "\033[0;32mGot a connection on the control channel from %s \033[0m" % cinfo[0])

        self.cinterrupt, cinfo = self.sinterrupt.accept()
        print (
            "\033[0;32mGot a connection on the interrupt channel from %s \033[0m" % cinfo[0])

    # send a string to the bluetooth host machine
    def send_string(self, message):
        try:
            self.cinterrupt.send(bytes(message))
        except OSError as err:
            error(err)


class BTKbService(dbus.service.Object):

    def __init__(self):
        print("1. Setting up service")
        # set up as a dbus service
        bus_name = dbus.service.BusName(
            "org.npl.btkbservice", bus=dbus.SystemBus())
        dbus.service.Object.__init__(
            self, bus_name, "/org/npl/btkbservice")
        # create and setup our device
        self.device = BTKbDevice()
        # start listening for connections
        self.device.listen()

    @dbus.service.method('org.npl.btkbservice', in_signature='yay')
    def send_keys(self, modifier_byte, keys):
        print("Get send_keys request through dbus")
        print("key msg: ", keys)
        state = [ 0xA1, 1, 0, 0, 0, 0, 0, 0, 0, 0 ]
        state[2] = int(modifier_byte)
        count = 4
        for key_code in keys:
            if(count < 10):
                state[count] = int(key_code)
            count += 1
        self.device.send_string(state)

    @dbus.service.method('org.npl.btkbservice', in_signature='yay')
    def send_mouse(self, modifier_byte, keys):
        state = [0xA1, 2, 0, 0, 0, 0]
        count = 2
        for key_code in keys:
            if(count < 6):
                state[count] = int(key_code)
            count += 1
        self.device.send_string(state)


# main routine
if __name__ == "__main__":
    # we an only run as root
    try:
        if not os.geteuid() == 0:
            sys.exit("Only root can run this script")

        DBusGMainLoop(set_as_default=True)
        myservice = BTKbService()
        loop = GLib.MainLoop()
        loop.run()
    except KeyboardInterrupt:
        sys.exit()
