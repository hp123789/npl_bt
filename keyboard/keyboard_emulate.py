import dbus
import dbus.service
import dbus.mainloop.glib
import keymap
import time
import redis
import json
import numpy as np


class BtkStringClient():
    # constants
    KEY_DOWN_TIME = 0.01
    KEY_DELAY = 0.01

    def __init__(self):
        # the structure for a bt keyboard input report (size is 10 bytes)
        self.state = [
            0xA1,  # this is an input report
            0x01,  # Usage report = Keyboard
            # Bit array for Modifier keys
            [0,  # Right GUI - Windows Key
                 0,  # Right ALT
                 0,  # Right Shift
                 0,  # Right Control
                 0,  # Left GUI
                 0,  # Left ALT
                 0,  # Left Shift
                 0],  # Left Control
            0x00,  # Vendor reserved
            0x00,  # rest is space for 6 keys
            0x00,
            0x00,
            0x00,
            0x00,
            0x00]
        self.scancodes = {
            "-": "KEY_MINUS",
            "=": "KEY_EQUAL",
            ";": "KEY_SEMICOLON",
            "'": "KEY_APOSTROPHE",
            "`": "KEY_GRAVE",
            "\\": "KEY_BACKSLASH",
            ",": "KEY_COMMA",
            ".": "KEY_DOT",
            "/": "KEY_SLASH",
            "_": "key_minus",
            "+": "key_equal",
            ":": "key_semicolon",
            "\"": "key_apostrophe",
            "~": "key_grave",
            "|": "key_backslash",
            "<": "key_comma",
            ">": "key_dot",
            "?": "key_slash",
            " ": "KEY_SPACE",
        }

        # connect with the Bluetooth keyboard server
        print("setting up DBus Client")
        self.bus = dbus.SystemBus()
        self.btkservice = self.bus.get_object(
            'org.npl.btkbservice', '/org/npl/btkbservice')
        self.iface = dbus.Interface(self.btkservice, 'org.npl.btkbservice')
        self.output_stream = "tts_final_decoded_sentence"
        self.trial_info_stream = 'trial_info'
        self.r = redis.Redis('192.168.150.2', socket_timeout=5)
        self.run_keyboard = True
        self.old_supergraph_id = None

    def send_key_state(self):
        """sends a single frame of the current key state to the emulator server"""
        bin_str = ""
        element = self.state[2]
        for bit in element:
            bin_str += str(bit)
        self.iface.send_keys(int(bin_str, 2), self.state[4:10])

    def send_key_down(self, scancode, modifiers):
        """sends a key down event to the server"""
        self.state[2] = modifiers
        self.state[4] = scancode
        self.send_key_state()

    def send_key_up(self):
        """sends a key up event to the server"""
        self.state[4] = 0
        self.send_key_state()

    def send_string(self, string_to_send):
        for c in string_to_send:
            cu = c.upper()
            modifiers = [ 0, 0, 0, 0, 0, 0, 0, 0 ]
            if cu in self.scancodes:
                scantablekey = self.scancodes[cu]
                if scantablekey.islower():
                    modifiers = [ 0, 0, 0, 0, 0, 0, 1, 0 ]
                    scantablekey = scantablekey.upper()
            else:
                if c.isupper():
                    modifiers = [ 0, 0, 0, 0, 0, 0, 1, 0 ]
                scantablekey = "KEY_" + cu

            scancode = keymap.keytable[scantablekey]
            self.send_key_down(scancode, modifiers)
            time.sleep(BtkStringClient.KEY_DOWN_TIME)
            self.send_key_up()
            time.sleep(BtkStringClient.KEY_DELAY)

    def load_supergraph(self):
        supergraph_entries = self.r.xrevrange("supergraph_stream", count=1)

        # Parse the result from redis.
        supergraph_id, supergraph_entry = supergraph_entries[0]
        supergraph_bytes = supergraph_entry[b"data"]
        supergraph_str = supergraph_bytes.decode()
        supergraph_dict = json.loads(supergraph_str)

        # If this is a new supergraph, update this class's version.
        if supergraph_id != self.old_supergraph_id:
            self.old_supergraph_id = supergraph_id
            # Also grab the parameters for this specific node.
            matching_node_dicts = [
                n
                for n in supergraph_dict["nodes"].values()
                if n["nickname"] == "brainToText_personalUse"
            ]
            if not matching_node_dicts:
                message = {"message": f"Bluetooth: No parameters entry in supergraph for node '{self.nickname}'"}
                self.r.xadd("console_logging", message)
            node_dict = matching_node_dicts[0]

            node_params = node_dict["parameters"]

            if node_params.get('run_keyboard') is not None:
                self.run_keyboard = bool(node_params['run_keyboard'])
                self.last_entry_seen = "$"
                
    
    def run(self):
        self.last_entry_seen = "$"
        self.trial_info_last_entry_seen = "$"

        while True:

            try:
                self.load_supergraph()
            except Exception as e:
                self.r.xadd("console_logging", "keyboard supergraph error: " + e)

            if self.run_keyboard:

                try:
                    sentence = self.r.xread(
                        {self.output_stream: self.last_entry_seen}, block=0, count=1
                    )
                    if len(sentence) > 0:
                        self.last_entry_seen = sentence[0][1][0][0]
                        output = sentence[0][1][0][1][b'final_decoded_sentence'].decode() + " "

                        # trial_info = self.r.xread(
                        #     {self.trial_info_stream: self.trial_info_last_entry_seen},
                        #     block=0,
                        #     count=1,
                        # )

                        # for entry_id, entry in trial_info[0][1]:
                        #     self.trial_info_last_entry_seen = entry_id
                        #     if b'decoded_correctly' in entry:
                        #         decoded_correctly = int(entry[b'decoded_correctly'].decode())
                        #     else:
                        #         decoded_correctly = int(-1)

                        # # only type correct or mostly correct sentences
                        # if decoded_correctly in [-1,1,2]:
                        #     # 0 is INCORRECT
                        #     # 1 is CORRECT
                        #     # 2 is MOSTLY CORRECT
                        #     # -1 is NOT SPECIFIED

                        self.send_string(output)
                        message = {"message": "WRITING SENTENCE: " + output}
                        self.r.xadd("console_logging", message)
                            
                except:
                    isConnected = False
                    while not isConnected:
                        try:
                            self.r.ping()
                            t = self.r.time()
                            self.last_entry_seen = int(t[0]*1000 + t[1]/1000)
                            self.trial_info_last_entry_seen = int(t[0]*1000 + t[1]/1000)
                            isConnected = True
                        except:
                            pass


if __name__ == "__main__":
    node = BtkStringClient()
    node.run()
