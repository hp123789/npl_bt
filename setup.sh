#! /bin/bash
sudo apt-get update -y
sudo apt-get install bluez bluez-tools -y
sudo apt-get install bluez-firmware python-bluez python-dev python-pip -y
sudo pip install evdev
sudo apt install git python python3 python-dev python3-dev python3-dbus python3-pyudev python3-evdev -y
sudo apt-get install python-dbus  -y
sudo apt-get install tmux -y
sudo cp dbus/org.npl.btkbservice.conf /etc/dbus-1/system.d
sudo cp /lib/systemd/system/bluetooth.service ./bluetooth.service.bk
sudo cp bluetooth.service /lib/systemd/system/bluetooth.service
sudo systemctl daemon-reload
sudo /etc/init.d/bluetooth start
sudo apt-get install python3-gi -y
sudo apt install python3-pip -y
sudo pip3 install PyBluez
sudo pip3 install redis
sudo pip3 install numpy
echo "interface eth0" >> /etc/dhcpcd.conf
echo "static ip_address=192.168.150.147" >> /etc/dhcpcd.conf
echo "static routers=192.168.50.1" >> /etc/dhcpcd.conf
echo "static domain_name_servers=192.168.50.1" >> /etc/dhcpcd.conf
echo "dtparam=krnbt" >> /boot/config.txt
echo "cd /home/username/npl_bt/" >> ../.bashrc
echo "sudo ./boot.sh" >> ../.bashrc
sudo reboot
