from greenlet import greenlet
from sandbox import Sandbox, SandboxConfig
import __builtin__
import time
import traceback

# This is just for testing
LOADER_CODE = """
import time
while True:
    try:
        print 'running... %s' % str(rc)
        time.sleep(1)
        print 'done'
        yield_and_reschedule()
    except Exception:
        print 'caught exception... ignoring'
"""

# This will be the real player execution code
LOADER_CODE_REAL = """
from {team}.player import RobotPlayer
player = RobotPlayer(rc)
player.run()
"""

def passthrough(thread):
    """A one shot greenlet that simply resumes an existing greenlet and then
    returns. This allows greenlets to be resumed without a presistent parent.
    """
    def _run():
        retval = thread.resume()
        if retval is None:
            raise Exception('robot run method returned') # TODO: RobotDeathException
        return retval
    g = greenlet(run=_run)
    thread.parent = g
    return g.switch()

class Scheduler():
    def __init__(self):
        self.threads = []

    def add(self, thread):
        self.threads.append(thread)

    def run_next(self):
        thread = self.threads.pop(0)
        try:
            passthrough(thread)
        except Exception:
            traceback.print_exc()
            pass # TODO: thread is dead -- cleanup
        else:
            self.threads.append(thread)

    def run(self):
        while self.threads:
            self.run_next()

class Player(greenlet):
    def __init__(self, rc, team):
        super(Player, self).__init__()
        self.rc = rc
        self.team = team

        # TODO: we need to add additional builins to the config
        #   - increment_clock
        #   - yield_and_reschedule
        config = SandboxConfig(use_subprocess=False)
        config.enable('stdout')
        config.enable('stderr')
        config.enable('time')
        config.allowModule('time', 'sleep')
        self.sandbox = Sandbox(config)
        self.running = False

    def resume(self):
        if self.running:
            self.sandbox.enable_protections()
        return self.switch()

    def run(self):
        this = self
        def yield_and_reschedule():
            # break out of the sandbox
            this.sandbox.disable_protections()
            # return execution to the scheduler
            this.parent.switch()

        statement = LOADER_CODE.format(team=self.team)
        safeglobals = {
            'yield_and_reschedule': yield_and_reschedule,
        }
        safelocals = { 'rc': self.rc }
        self.running = True
        self.sandbox.execute(statement, globals=safeglobals, locals=safelocals)

if __name__ == '__main__':
    s = Scheduler()
    p1 = Player('rc1', 'teamA')
    p2 = Player('rc2', 'teamB')
    s.add(p1)
    s.add(p2)
    s.run()