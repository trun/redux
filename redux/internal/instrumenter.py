import __builtin__
from ast import *

class InstrumentTransformer(NodeTransformer):
    def __init__(self):
        self.expr_count = 0
        super(InstrumentTransformer, self).__init__()

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
        node = parse('__builtins__["clockIncrement"](' + str(incr) + ')').body
        return node

    @staticmethod
    def isbody(node, field):
        if isinstance(node, FunctionDef):
            return field == 'body'
        if isinstance(node, For):
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
        compileall.compile_file(path, force=True)

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    options, args = parser.parse_args()
    instrument(*args, **options.__dict__)
