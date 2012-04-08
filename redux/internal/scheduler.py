from greenlet import greenlet
import os
from sandbox import Sandbox, SandboxConfig
from redux.internal.exceptions import RobotDeathException
import traceback

# this is just for testing
LOADER_CODE_TEST = """
import time
while True:
    try:
        print 'running... %s' % str(rc)
        time.sleep(1)
        print 'done'
        defer()
    except Exception:
        print 'caught exception... ignoring'
"""

# This will be the real player execution code
LOADER_CODE = """
from {team}.player import RobotPlayer
player = RobotPlayer(rc)
player.run()
"""

# TODO paramaterize
BYTECODE_LIMIT = 8000

def passthrough(thread, throw=False):
    """A one shot greenlet that simply resumes an existing greenlet and then
    returns. This allows greenlets to be resumed without a presistent parent.
    """
    def _run():
        retval = thread.resume(throw)
        if retval is None:
            raise Exception('robot run method returned')
        return retval
    g = greenlet(run=_run)
    thread.parent = g
    return g.switch()

class Scheduler():
    _instance = None

    def __init__(self, game_world):
        self.game_world = game_world
        self.current_thread = None
        self.threads = {}
        self.threads_to_kill = set()

    @classmethod
    def create(cls, game_world=None):
        cls._instance = Scheduler(game_world)

    @classmethod
    def destroy(cls):
        cls._instance = None

    @classmethod
    def instance(cls):
        return cls._instance

    def spawn_thread(self, robot):
        """Spawn a new player"""
        player = Player(RobotController(robot, self.game_world).interface())
        thread = PlayerThread(player)
        self.threads[robot.id] = thread

    def run_thread(self, id):
        """Run a player thread for the given robot id"""
        print '[SCHEDULER] running thread', id
        self.current_thread = self.threads.get(id)
        assert not self.current_thread is None, 'null thread?'

        # check if the robot is scheduled to be killed
        throw = id in self.threads_to_kill

        # check if the robot is over the bytecode limit
        if self.get_bytecode_left() < 0 and not throw:
            self.current_thread.bytecode_used -= BYTECODE_LIMIT
            return

        # resume robot execution
        try:
            passthrough(self.current_thread.player, throw)
        except Exception as e:
            if not isinstance(e, RobotDeathException):
                traceback.print_exc()
            del self.threads[id]

        self.current_thread = None

    def end_thread(self):
        self.current_thread.bytecode_used -= min(8000, self.current_thread.bytecode_used)
        self.current_thread.player.pause()

    def current_robot(self):
        return self.current_thread.player.robot_controller.robot

    def kill_robot(self, id):
        self.threads_to_kill.add(id)

    def increment_bytecode(self, amt):
        assert amt >= 0, 'negative bytecode increments not allowed'
        self.current_thread.bytecode_used += amt
        if self.current_thread.bytecode_used > BYTECODE_LIMIT:
            self.end_thread()

    def get_bytecode_left(self):
        return BYTECODE_LIMIT - self.current_thread.bytecode_used

    def get_bytecode_used(self):
        return self.current_thread.bytecode_used


class Player(greenlet):
    def __init__(self, robot_controller):
        super(Player, self).__init__()
        self.robot_controller = robot_controller

        config = SandboxConfig(use_subprocess=False)
        config.enable('traceback')
        config.enable('stdout')
        config.enable('stderr')
        config.enable('time')

        # TODO need to allow *all* imports from team package
        config.allowModule(robot_controller.robot.team + '.player', 'RobotPlayer')

        # TODO need a better method for override the sys_path
        config.sys_path = config.sys_path + (os.getcwd(),)

        # add additional builtins to the config
        #   - increment_clock
        this = self
        def increment_clock(amt):
            Scheduler.instance().increment_bytecode(amt)

        # TODO need a better method to add builtins additions
        config._builtins_additions = {
            'increment_clock': increment_clock,
        }

        self.sandbox = Sandbox(config)
        self.running = False

    def resume(self, throw=False):
        return self.switch(throw)

    def pause(self):
        # break out of the sandbox
        self.sandbox.disable_protections()
        # return execution to the scheduler
        throw = self.parent.switch()
        if throw:
            raise RobotDeathException('killed by engine')
        # re-enable sandbox protections
        self.sandbox.enable_protections()

    def run(self, *args):
        statement = LOADER_CODE.format(team=self.robot_controller.robot.team)
        safelocals = { 'rc': self.robot_controller }
        self.running = True
        self.sandbox.execute(statement, globals={}, locals=safelocals)


class PlayerThread(object):
    def __init__(self, player):
        self.bytecode_used = 0
        self.player = player


class RobotController(object):
    def __init__(self, robot, game_world):
        self.robot = robot
        self.game_world = game_world

    def yield_execution(self):
        # TODO yield bonus
        Scheduler.instance().end_thread()

    def interface(self):
        """
        Returns an encapsulated version of the controller that can safely be
        passed to the sandboxed player code.
        """
        this = self
        class _interface(object):
            def __init__(self):
                self._robot = this.robot.interface() # TODO robot should cache its own interface

            def yield_execution(self):
                this.yield_execution()

            @property
            def robot(self):
                return self._robot
        return _interface()