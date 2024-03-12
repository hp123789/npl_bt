# Dev Cart Bluetooth Keyboard and Mouse

Dev cart will emulate a bluetooth device, sending both keyboard and cursor commands

## Setup

For first setup, run:

```sudo ./setup.sh```

After that run:

```sudo ./boot.sh```

And run the following scripts:

Bluetooth server: ```sudo /server/btk_server.py```
Keyboard: ```python3 /keyboard/keyboard_emulate.py```
Mouse: ```python3 /mouse/mouse_emulate.py```

## Running

Plug the Raspberry Pi into ethernet and power and after ~15 seconds a bluetooth device should be visible as "i-am-keyboard-and-mouse"