from collections import OrderedDict
from redux.internal.scheduler import Scheduler

class GameWorld(object):
    def __init__(self):
        self.objects = OrderedDict()
        self.round = -1
        self.next_id = 0
        Scheduler.create(self)

    def run(self):
        self.round += 1

        # begin round
        print '[WORLD] begin round', self.round
        for obj in self.objects.itervalues():
            obj.begin_round()

        # execute each object - TODO: assumes all robots are objects
        for obj in self.objects.itervalues():
            obj.begin_turn()
            Scheduler.instance().run_thread(obj.id)
            obj.end_turn()

        # end round
        for obj in self.objects.itervalues():
            obj.end_round()
        print '[WORLD] end round', self.round

    def add_object(self, obj):
        self.objects[obj.id] = obj
        Scheduler.instance().spawn_thread(obj)

    def get_object(self, id):
        return self.objects.get(id)

    def remove_object(self, id):
        del self.objects[id]

    def get_next_id(self):
        id = self.next_id
        self.next_id += 1
        return id


class GameObject(object):
    def __init__(self, gw):
        self.id = gw.get_next_id()
        gw.add_object(self) # TODO: add here??

    def begin_round(self):
        print ' [OBJECT %d] begin round' % self.id

    def end_round(self):
        print ' [OBJECT %d] end round' % self.id

    def begin_turn(self):
        print ' [OBJECT %d] begin turn' % self.id

    def end_turn(self):
        print ' [OBJECT %d] end turn' % self.id


class Robot(GameObject):
    def __init__(self, gw, team):
        self.team = team # needs to come first because of how we add to game world
        super(Robot, self).__init__(gw)

    def interface(self):
        """
        Returns an encapsulated version of the robot that can safely be
        passed to the sandboxed player code.
        """
        this = self
        class _interface(object):
            @property
            def id(self):
                return this.id

            @property
            def team(self):
                return this.team
        return _interface()

if __name__ == '__main__':
    import time
    world = GameWorld()
    robot1 = Robot(world, 'teamA')
    robot2 = Robot(world, 'teamB')
    while True:
        world.run()
        time.sleep(1)
