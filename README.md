# Raspberry Pi 4 Bluetooth Keyboard and Mouse

Raspberry Pi 4 will read directly from redis and emulate a bluetooth device, sending both keyboard and cursor commands

## Setup

Install Raspbian Buster on a Raspberry Pi 4

Once installed, ssh in and run the following commands:

```git clone https://github.com/hp123789/npl_bt.git```

```cd npl_bt```

```sudo ./setup.sh```

## Running

Plug the Raspberry Pi into ethernet and power and after ~15 seconds a bluetooth device should be visible as "i-am-keyboard-and-mouse"