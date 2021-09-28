# fliprfull
Plugin to add flipr measures to domoticz

install :

cd ~/domoticz/plugins

mkdir fliprfull

sudo apt-get update

sudo apt-get install git

git clone https://github.com/Erwanweb/fliprfull.git fliprfull

cd fliprfull

sudo chmod +x plugin.py

sudo /etc/init.d/domoticz.sh restart

Upgrade :

cd ~/domoticz/plugins/fliprfull

git reset --hard

git pull --force

sudo chmod +x plugin.py

sudo /etc/init.d/domoticz.sh restart
