#Stop the background process
sleep 30
sudo hciconfig hci0 down
sudo systemctl daemon-reload
sudo systemctl stop bluetooth
sudo /etc/init.d/bluetooth start
# Update  mac address
./updateMac.sh
#Update Name
./updateName.sh test_keyboard_nio
#Get current Path
export C_PATH=$(pwd)

tmux kill-window -t npl:app >/dev/null 2>&1

[ ! -z "$(tmux has-session -t npl 2>&1)" ] && tmux new-session -s npl -n app -d
[ ! -z "$(tmux has-session -t npl:app 2>&1)" ] && {
    tmux new-window -t npl -n app
}
[ ! -z "$(tmux has-session -t npl:app.1 2>&1)" ] && tmux split-window -t npl:app -h
[ ! -z "$(tmux has-session -t npl:app.2 2>&1)" ] && tmux split-window -t npl:app.1 -v
tmux send-keys -t npl:app.0 'cd $C_PATH/server && sudo ./btk_server.py > server.txt' C-m
tmux send-keys -t npl:app.1 'cd $C_PATH/mouse  && python3 ./mouse_emulate.py' C-m
tmux send-keys -t npl:app.2 'cd $C_PATH/keyboard  && python3 ./keyboard_emulate.py' C-m
