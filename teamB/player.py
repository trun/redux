class RobotPlayer(object):
    def __init__(self, rc):
        self.rc = rc

    def run(self):
        while True:
            print 'DO RE ME'
            self.rc.yield_execution()
