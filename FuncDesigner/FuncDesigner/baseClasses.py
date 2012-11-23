from numpy import ndarray

class OOArray(ndarray):
    pass



def distrib_err_fcn(*args, **kw):
    from FDmisc import FuncDesignerException
    raise FuncDesignerException('''
            direct operations (like +, -, *, /, ** etc) on stochastic distributions are forbidden,
            you should declare FuncDesigner variables, define function(s) on them 
            and then get new distribution via evaluating the obtained oofun(s) on a data point
            ''')

stochasticDistribution = 'stochastic distribution'
class Stochastic:
    #__array_priority__ = 100
    def __init__(self):
        self._str = stochasticDistribution
    __repr__ = lambda self: self._str
    __add__ = __mul__ = __pow__ = __rpow__ = __rmul__ = __radd__ = __neg__ = __pos__ = distrib_err_fcn
