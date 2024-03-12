#Stop the background process
sudo hciconfig hci0 down
sudo systemctl daemon-reload
sudo systemctl stop bluetooth
sudo /etc/init.d/bluetooth start
# Update  mac address
./updateMac.sh
#Update Name
./updateName.sh i-am-keyboard-and-mouse
