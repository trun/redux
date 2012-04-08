import __builtin__
from ast import *

class InstrumentTransformer(NodeTransformer):
    def __init__(self):
        self.expr_count = 0
        super(InstrumentTransformer, self).__init__()

    def visit_TryExcept(self, node):
        """Adds an uncatchable handler for RobotDeathExceptions"""
        handler = self.robot_death_handler()
        handlers = [ handler ] + node.handlers
        node.handlers[:] = handlers
        return self.generic_visit(node)

    def generic_visit(self, node):
        self.expr_count += 1
        for field, old_value in iter_fields(node):
            old_value = getattr(node, field, None)
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, AST):
                        value = self.visit(value)
                        if value is None:
                            continue
                        elif not isinstance(value, AST):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                # add increment at the end of each basic block
                if self.isbody(node, field):
                    new_values += self.incr_stmt(self.expr_count)
                old_value[:] = new_values
            elif isinstance(old_value, AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node

    def incr_stmt(self, incr=1):
        # TODO reference builtins to prevent local override
        node = parse('increment_clock(' + str(incr) + ')').body
        return node

    def robot_death_handler(self):
        node = parse('try:\n  pass\nexcept RobotDeathException:\n  raise')
        return node.body[0].handlers[0]

    @staticmethod
    def isbody(node, field):
        if isinstance(node, FunctionDef):
            return field == 'body'
        if isinstance(node, For):
            return field == 'body' or field == 'orelse'
        if isinstance(node, While):
            return field == 'body' or field == 'orelse'
        if isinstance(node, If):
            return field == 'body' or field == 'orelse'
        if isinstance(node, TryExcept):
            return field == 'body' or field == 'orelse'
        return False

def instrument(*args, **kwargs):
    compile = __builtin__.compile

    def compile_and_instrument(source, filename, mode, flags=0, dont_inherit=0):
        if flags == PyCF_ONLY_AST:
            return compile(source, filename, mode, flags)
        assert mode == 'exec'
        src = open(filename).read()
        tree = parse(src, filename)
        tree = InstrumentTransformer().visit(tree)
        code = compile(tree, filename, 'exec', flags, dont_inherit)
        return code

    __builtin__.compile = compile_and_instrument

    import compileall
    for path in args:
        compileall.compile_dir(path, force=True)

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    options, args = parser.parse_args()
    instrument(*args, **options.__dict__)
