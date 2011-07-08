import os, sys
curr_dir = ''.join([elem + os.sep for elem in __file__.split(os.sep)[:-1]])
sys.path += [curr_dir]

from ooVar import oovar, oovars
from ooFun import _getAllAttachedConstraints, broadcast, ooarray, ooFun as oofun
from ooSystem import ooSystem as oosystem
from translator import FuncDesignerTranslator as ootranslator
from ooPoint import ooPoint as oopoint
from sle import sle
from ode import ode
from overloads import *
#from overloads import _sum as sum
from FDmisc import FuncDesignerException, _getDiffVarsID
from interpolate import scipy_UnivariateSpline as interpolator
from integrate import integrator
__version__ = '0.34'

isE = False
try:
    import enthought
    isE = True
except ImportError:
    pass
try:
    import envisage
    import mayavi
    isE = True
except ImportError:
    pass
try:
    import xy
    isE = False
except ImportError:
    pass
  
if isE:
    s = """
    Seems like you are using OpenOpt from 
    commercial Enthought Python Distribution;
    consider using free GPL-licensed alternatives
    PythonXY (http://www.pythonxy.com) or
    Sage (http://sagemath.org) instead.
    """
    print(s)
