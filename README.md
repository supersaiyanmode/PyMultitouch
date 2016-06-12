PyMultitouch
===================================

This is a port of [xSwipe](https://github.com/iberianpig/xSwipe).


## Installation

### Prerequisites

If you are using the Ubuntu 14.04 or later, you'll need to rollback to an older version of synclient. Run the following
in a terminal:

```bash
$ sudo apt-get install -y git build-essential libevdev-dev autoconf automake libmtdev-dev xorg-dev xutils-dev libtool
$ sudo apt-get remove -y xserver-xorg-input-synaptics
$ git clone https://github.com/Chosko/xserver-xorg-input-synaptics.git
$ cd xserver-xorg-input-synaptics
$ ./autogen.sh
$ ./configure --exec_prefix=/usr
$ make
$ sudo make install
```

Restart your X session (CTRL + ALT + BACKSPACE, if enabled).

### Install PyMultitouch

```bash
$ wget 'https://github.com/supersaiyanmode/PyMultitouch/archive/master.zip'
$ unzip PyMultitouch-master.zip
$ cd PyMultitouch-master.zip
$ sudo pip install -r requirements.txt
$ mkdir -p ~/.config/pymultitouch
$ cp config.txt ~/.config/multitouch/.
$ python main.py &
```

## Configuration

The configuration file is located at `~/.config/pymultitouch/config.txt`.