import os.path
import threading
from subprocess import Popen, STDOUT, PIPE
from Queue import Queue, Empty
import signal
from collections import Counter
import re

from pykeyboard import PyKeyboard

NORTH, EAST, SOUTH, WEST = range(4)
TIME, COORD, PRESSURE, FINGER, LEFT, RIGHT = range(6)

class PyMTException(Exception):
    def __init__(self, msg):
        super(Exception, self).__init__(msg)

class Config(object):
    TIME_THRESHOLD = 0.5

class SynClientPoller(object):
    POLL_COMMAND = ["stdbuf", "-oL", "synclient", "-m"]

    def __init__(self, pollFreq=50, debug=False):
        self.command = self.POLL_COMMAND + [str(pollFreq)]
        self.listener = None
        self.stop_requested = False
        self.debug = debug

    def register(self, obj):
        """Overwrites the previous listener."""
        self.listener = obj

    def start(self):
        p = Popen(self.command, stdout=PIPE, stderr=PIPE, bufsize=1)
        while not self.stop_requested:
            try:
                line = p.stdout.readline()
            except KeyboardInterrupt as e:
                self.stop()
                continue
            if not self.listener:
                continue
            data = self.parseData(str(line).strip())
            if data:
                self.listener.event(data)
        p.stdout.close()
        print "Closing client process."
        p.wait()
        print "Closed client process."

    def stop(self):
        self.stop_requested = True

    def parseData(self, line):
        if line.startswith("time"):
            return None
        try:
            parts = line.split()

            time = float(parts[0])
            coords = (int(parts[1]), int(parts[2]))
            pressure = int(parts[3])
            fingers = int(parts[4])
            left = bool(int(parts[6]))
            right = bool(int(parts[7]))
            return (time, coords, pressure, fingers, left, right)
        except Exception, e:
            print e
            return None

class TouchpadEventProcessor(object):
    def __init__(self):
        self.listener = None
        self.queue = Queue()
        self.processorThread = threading.Thread(target=self.process)
        self.processorThread.daemon = True
        self.stop_requested = False

    def start(self):
        self.stop_requested = False
        self.processorThread.start()

    def stop(self):
        self.stop_requested = True

    def register(self, obj):
        self.listener = obj

    def event(self, obj):
        self.queue.put(obj)

    def process(self):
        print "Start processing events.."
        history = []
        prevTime = -Config.TIME_THRESHOLD
        clicked = False
        gesture = True
        while not self.stop_requested:
            item = self.queue.get()

            self.queue.task_done()

            if item[FINGER] == 0:
                print "All fingers lifted."
                if gesture:
                    self.evaluate(history)
                history = []
                clicked = False
                gesture = True
                ignore = False
            elif not clicked and (item[LEFT] or item[RIGHT]):
                clicked = True
                gesture = False
                if self.listener:
                    self.listener.click(LEFT if item[LEFT] else RIGHT, item[FINGER])
            elif clicked and not (item[LEFT] or item[RIGHT]):
                clicked = False
            elif gesture:
                history.append(item)
        print "Done processing events."
    
    def evaluate(self, history):
        if len(history) < 2:
            return

        #finger = Counter(x[FINGER] for x in history).most_common(n=1)[0][0]
        finger = max(x[FINGER] for x in history)

        direction = self.get_direction([x[COORD] for x in history if x[FINGER] == finger])
        if direction is None:
            return

        print "Direction:", ["NORTH", "EAST", "SOUTH", "WEST"][direction],
        print "Fingers:", finger

        if self.listener:
            self.listener.swipe(direction, finger)
        

    def get_direction(self, arr):
        arr = list(reversed(arr))
        print "Arr:", arr
        delta = map(sum, zip(*[(x[0] - y[0], x[1] - y[1]) for x, y in zip(arr, arr[1:])]))
        print "Delta:", delta
        if len(delta) != 2:
            return None
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
                if value:
                    combinations = map(lambda x: x.strip(), value.split("+"))
                    key_combos = [self.parse_key(c) for c in combinations]
                    self.map[key] = (key_combos, value)
                else:
                    self.map[key] = []
                print "Loaded:", line
    
    def parse_key(self, key):
        if key in self.KEY_MAP:
            return getattr(self.keyboard, self.KEY_MAP[key])
        elif key.isalpha():
            return key.lower()
        elif re.match('[fF]((1[0-2]?)|[2-9])', key):
            return self.keyboard.function_keys[int(key[1:])]
        else:
            raise PyMTException("Invalid key combination: " + line)
        

    def swipe(self, direction, fingers):
        direction = ["NORTH", "EAST", "SOUTH", "WEST"][direction]
        fingers = str(fingers) + "_FINGERS"

        map_key = "SWIPE_%s_%s"%(direction, fingers)
        self.process_event(map_key)

    def click(self, typ, fingers):
        typ = "LEFT" if typ == LEFT else RIGHT
        map_key = "%s_CLICK_%d_FINGERS"%(typ, fingers)
        self.process_event(map_key)
    
    def process_event(self, map_key):
        if map_key not in self.map or not self.map[map_key]:
            return

        combinations, text = self.map[map_key]

        print "Sending:", text
        if len(combinations) > 1:
            for press_key in combinations[:-1]:
                self.keyboard.press_key(press_key)
            self.keyboard.tap_key(combinations[-1])

            for press_key in combinations[:-1]:
                self.keyboard.release_key(press_key)
        else:
            self.keyboard.tap_key(combinations[0])

class DebugKeyMapper(object):
    def swipe(self, direction, fingers):
        logger.info("Swipe:"  + ["NORTH", "EAST", "SOUTH", "WEST"][direction] + str(fingers) + " fingers")

    def click(self, typ, fingers):
        logger.info("Click:" + ("LEFT" if typ == LEFT else "RIGHT") + " with " + str(fingers) + " fingers")

poller = SynClientPoller(debug="debug" in sys.argv)
touchpad = TouchpadEventProcessor()
keymapper = DebugKeyMapper() if "debug" in sys.argv else KeyMapper()

def exit():
    print "Stopping .."
    poller.stop()
    touchpad.stop()

def restart():
    exit()
    logger.info("Restarting ..")
    os.execl(sys.executable, *([sys.executable]+sys.argv))

def main():
    for sig in (signal.SIGTERM, signal.SIGINT):
        prev_handler = signal.getsignal(sig)

        def sig_handler(x, y, prevFn):
            exit()
            if prevFn:
                prevFn(x, y)
        signal.signal(sig, lambda x, y: sig_handler(x, y, prev_handler))
    signal.signal(signal.SIGHUP, lambda x, y: restart())

    poller.register(touchpad)
    touchpad.register(keymapper)
    touchpad.start()
    poller.start()


if __name__ == '__main__':
    main()

