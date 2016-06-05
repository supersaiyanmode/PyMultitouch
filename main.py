import os.path
import threading
from subprocess import Popen, STDOUT, PIPE

from pykeyboard import PyKeyboard

NORTH, EAST, SOUTH, WEST = range(4)
TIME, COORD, PRESSURE, FINGER = range(4)

class PyMTException(Exception):
    def __init__(self, msg):
        super(Exception, self).__init__(msg)

class Config(object):
    TIME_THRESHOLD = 0.5

class SynClientPoller(object):
    POLL_COMMAND = ["stdbuf", "-oL", "synclient", "-m"]

    def __init__(self, pollFreq=50):
        self.command = self.POLL_COMMAND + [str(pollFreq)]
        self.listener = None
        #self.thread = threading.Thread(target=self.run)
        self.stop_requested = False

    def register(self, obj):
        """Overwrites the previous listener."""
        self.listener = obj

    def start(self):
        self.thread.start()

    def run(self):
        p = Popen(self.command, stdout=PIPE, stderr=PIPE, bufsize=1)
        while not self.stop_requested:
            line = p.stdout.readline()
            if not self.listener:
                continue
            data = self.parseData(str(line).strip())
            if data:
                self.listener.event(data)
        p.stdout.close()
        p.wait()

    def parseData(self, line):
        if line.startswith("time"):
            return None
        try:
            parts = line.split()

            time = float(parts[0])
            coords = (int(parts[1]), int(parts[2]))
            pressure = int(parts[3])
            fingers = int(parts[4])
            return (time, coords, pressure, fingers)
        except Exception, e:
            print e
            return None

class TouchpadState(object):
    def __init__(self):
        self.listener = None
        self.reset()

    def register(self, obj):
        self.listener = obj

    def reset(self):
        self.history = []
        self.prevFinger = 0
        self.prevTime = -5

    def event(self, obj):
        if obj[FINGER] == 0:
            print "All fingers lifted. Reset."
            self.process()
            self.reset()
            return

        if obj[TIME] - self.prevTime > Config.TIME_THRESHOLD:
            print "Time elapsed."
            self.reset()

        if obj[FINGER] != self.prevFinger:
            self.reset()

        self.prevFinger = obj[FINGER]
        self.prevTime = obj[TIME]
        self.history.append(obj)

    def process(self):
        if len(self.history) < 2:
            return

        direction = self.get_direction([x[COORD] for x in self.history])
        print "Direction:", ["NORTH", "EAST", "SOUTH", "WEST"][direction],
        print "Fingers:", self.prevFinger

        if self.listener:
            self.listener.event("SWIPE", direction, self.prevFinger)
        

    def get_direction(self, arr):
        arr = list(reversed(arr))
        delta = map(sum, zip(*[(x[0] - y[0], x[1] - y[1]) for x, y in zip(arr, arr[1:])]))
        if abs(delta[0]) < abs(delta[1]): #More difference in Y direction
            return NORTH if delta[1] < 0 else SOUTH
        else:
            return WEST if delta[0] < 0 else EAST

class KeyMapper(object):
    KEY_MAP = {
        "LEFT_CONTROL": 'control_l_key', "RIGHT_CONTROL": 'control_r_key',
        "LEFT_ALT": 'alt_l_key', "RIGHT_ALT": 'alt_r_key',
        "LEFT_SHIFT": 'shift_l_key', "RIGHT_SHIFT": 'shift_r_key',
        "RIGHT": 'right_key', "LEFT": 'left_key', "UP": 'up_key', "DOWN": 'down_key',
        "SUPER": 'super_l_key', "TAB": 'tab_key',
    }

    def __init__(self):
        path = os.path.join(os.path.expanduser("~"), ".config/pymultitouch/config.txt")
        self.keyboard = PyKeyboard()
        self.map = {}
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if '#' in line:
                    line = line[:line.index('#')].strip()

                parts = line.split("=")
                if len(parts) != 2:
                    raise PyMTException("Invalid syntax near: " + line)
                key, value = map(lambda x: x.strip(), parts)
                combinations = map(lambda x: x.strip(), value.split("+"))
                if any([x not in self.KEY_MAP for x in combinations]):
                    raise PyMTException("Invalid key combination: " + line)
                key_combos = [getattr(self.keyboard, self.KEY_MAP[c]) for c in combinations]
                self.map[key] = (key_combos, value)
                print "Loaded:", line

    def event(self, style, direction, fingers):
        style = "SWIPE"
        direction = ["NORTH", "EAST", "SOUTH", "WEST"][direction]
        fingers = str(fingers) + "_FINGERS"

        map_key = "%s_%s_%s"%(style, direction, fingers)

        if map_key not in self.map:
            return

        combinations, text = self.map[map_key]

        print "Sending:", text

        for press_key in combinations[:-1]:
            self.keyboard.press_key(press_key)

        self.keyboard.tap_key(combinations[-1])


        for press_key in combinations[:-1]:
            self.keyboard.release_key(press_key)



def main():
    poller = SynClientPoller()
    touchpad = TouchpadState()
    keymapper = KeyMapper()
    poller.register(touchpad)
    touchpad.register(keymapper)
    poller.run()

if __name__ == '__main__':
    main()

