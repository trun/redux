class RobotPlayer(object):
    def __init__(self, rc):
        self.rc = rc

    def run(self):
        while True:
            print 'LA LA LA'
            self.rc.yield_execution()
