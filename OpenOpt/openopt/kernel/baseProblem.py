__docformat__ = "restructuredtext en"
from numpy import *
from oologfcn import *
from graphics import Graphics
from setDefaultIterFuncs import setDefaultIterFuncs, IS_MAX_FUN_EVALS_REACHED, denyingStopFuncs
from nonLinFuncs import nonLinFuncs
from residuals import residuals
from ooIter import ooIter
from Point import Point
from iterPrint import ooTextOutput
from ooMisc import setNonLinFuncsNumber, assignScript
from nonOptMisc import isspmatrix, scipyInstalled, scipyAbsentMsg, csr_matrix, Vstack, Hstack
from copy import copy as Copy
try:
    from DerApproximator import check_d1
    DerApproximatorIsInstalled = True
except:
    DerApproximatorIsInstalled = False

ProbDefaults = {'diffInt': 1.5e-8,  'xtol': 1e-6,  'noise': 0}
from runProbSolver import runProbSolver
import GUI
from FDmisc import setStartVectorAndTranslators


class user:
    def __init__(self):
        pass

class oomatrix:
    def __init__(self):
        pass
    def matMultVec(self, x, y):
        return dot(x, y) if not isspmatrix(x) else x._mul_sparse_matrix(csr_matrix(y.reshape((y.size, 1)))).A.flatten() 
    def matmult(self, x, y):
        return dot(x, y)
        #return asarray(x) ** asarray(y)
    def dotmult(self, x, y):
        return x * y
        #return asarray(x) * asarray(y)

class autocreate:
    def __init__(self): pass

class baseProblem(oomatrix, residuals, ooTextOutput):
    isObjFunValueASingleNumber = True
    manage = GUI.manage # GUI func
    prepared = False
    _baseProblemIsPrepared = False
    
    name = 'unnamed'
    state = 'init'# other: paused, running etc
    castFrom = '' # used by converters qp2nlp etc
    nonStopMsg = ''
    xlabel = 'time'
    plot = False # draw picture or not
    show = True # use command pylab.show() after solver finish or not

    iter = 0
    cpuTimeElapsed = 0.
    TimeElapsed = 0.
    isFinished = False
    invertObjFunc = False # True for goal = 'max' or 'maximum'
    nEvals = {}

    lastPrintedIter = -1
    
    iterObjFunTextFormat = '%0.3e'
    finalObjFunTextFormat = '%0.8g'
    debug = 0
    
    iprint = 10
    #if iprint<0 -- no output
    #if iprint==0 -- final output only

    maxIter = 1000
    maxFunEvals = 10000 # TODO: move it to NinLinProblem class?
    maxCPUTime = inf
    maxTime = inf
    maxLineSearch = 500 # TODO: move it to NinLinProblem class?
    xtol = ProbDefaults['xtol'] # TODO: move it to NinLinProblem class?
    gtol = 1e-6 # TODO: move it to NinLinProblem class?
    ftol = 1e-6
    contol = 1e-6
    
    fTol = None

    minIter = 0
    minFunEvals = 0
    minCPUTime = 0.0
    minTime = 0.0
    
    storeIterPoints = False 

    userStop = False # becomes True is stopped by user
    
    useSparse = 'auto' # involve sparse matrices: 'auto' (autoselect, premature) | True | False

    x0 = None
    isFDmodel = False # OO kernel set it to True if oovars/oofuns are used

    noise = ProbDefaults['noise'] # TODO: move it to NinLinProblem class?

    showFeas = False
    useScaledResidualOutput = False

    # A * x <= b inequalities
    A = None
    b = None

    # Aeq * x = b equalities
    Aeq = None
    beq = None
    
    scale = None

    goal = None# should be redefined by child class
    # possible values: 'maximum', 'min', 'max', 'minimum', 'minimax' etc
    showGoal = False# can be redefined by child class, used for text & graphic output

    color = 'b' # blue, color for plotting
    specifier = '-'# simple line for plotting
    plotOnlyCurrentMinimum = False # some classes like GLP change the default to True
    xlim = (nan,  nan)
    ylim = (nan,  nan)
    legend = ''

    fixedVars = None
    freeVars = None
    
    istop = 0

    fEnough = -inf # if value less than fEnough will be obtained
    # and all constraints no greater than contol
    # then solver will be stopped.
    # this param is handled in iterfcn of OpenOpt kernel
    # so it may be ignored with some solvers not closely connected to OO kernel

    fOpt = None # optimal value, if known
    

    def __init__(self, *args, **kwargs):
        # TODO: add the field to ALL classes
        self.err = ooerr
        self.warn = oowarn
        self.info = ooinfo
        self.hint = oohint
        self.disp = oodisp
        self.data4TextOutput = ['objFunVal', 'log10(maxResidual)']
        
        self.pWarn = ooPWarn
        
        if hasattr(self, 'expectedArgs'): 
            if len(self.expectedArgs)<len(args):
                self.err('Too much arguments for '+self.probType +': '+ str(len(args)) +' are got, at most '+ str(len(self.expectedArgs)) + ' were expected')
            for i, arg in enumerate(args):
                setattr(self, self.expectedArgs[i], arg)
        self.norm = linalg.norm
        self.denyingStopFuncs = denyingStopFuncs()
        self.iterfcn = lambda *args, **kwargs: ooIter(self, *args, **kwargs)# this parameter is only for OpenOpt developers, not common users
        self.graphics = Graphics()
        self.user = user()
        self.F = lambda x: self.objFuncMultiple2Single(self.objFunc(x)) # TODO: should be changes for LP, MILP, QP classes!

        self.point = lambda *args,  **kwargs: Point(self, *args,  **kwargs)

        self.timeElapsedForPlotting = [0.]
        self.cpuTimeElapsedForPlotting = [0.]
        #user can redirect these ones, as well as debugmsg
        self.debugmsg = lambda msg: oodebugmsg(self,  msg)
        
        self.constraints = [] # used in isFDmodel

        self.callback = [] # user-defined callback function(s)
        
        self.solverParams = autocreate()

        self.userProvided = autocreate()

        self.special = autocreate()

        self.intVars = [] # for problems like MILP
        self.binVars = [] # for problems like MILP
        self.optionalData = []#string names of optional data like 'c', 'h', 'Aeq' etc
        
        if 'min' in self.allowedGoals:
            self.minimize = lambda *args, **kwargs: minimize(self, *args, **kwargs)

        if 'max' in self.allowedGoals:
            self.maximize = lambda *args, **kwargs: maximize(self, *args, **kwargs)
            
        assignScript(self, kwargs)

    def __finalize__(self):
        if self.isFDmodel:
            self.xf = self._vector2point(self.xf)

    def objFunc(self, x):
        return self.f(x) # is overdetermined in LP, QP, LLSP etc classes

    def __isFiniteBoxBounded__(self): # TODO: make this function 'lazy'
        return all(isfinite(self.ub)) and all(isfinite(self.lb))

    def __isNoMoreThanBoxBounded__(self): # TODO: make this function 'lazy'
        s = ((), [], array([]), None)
        return self.b.size ==0 and self.beq.size==0 and (self._baseClassName == 'Matrix' or (not self.userProvided.c and not self.userProvided.h))

#    def __1stBetterThan2nd__(self,  f1, f2,  r1=None,  r2=None):
#        if self.isUC:
#            #TODO: check for goal = max/maximum
#            return f1 < f2
#        else:#then r1, r2 should be defined
#            return (r1 < r2 and  self.contol < r2) or (((r1 <= self.contol and r2 <=  self.contol) or r1==r2) and f1 < f2)
#
#    def __1stCertainlyBetterThan2ndTakingIntoAcoountNoise__(self,   f1, f2,  r1=None,  r2=None):
#        if self.isUC:
#            #TODO: check for goalType = max
#            return f1 + self.noise < f2 - self.noise
#        else:
#            #return (r1 + self.noise < r2 - self.noise and  self.contol < r2) or \
#            return (r1 < r2  and  self.contol < r2) or \
#            (((r1 <= self.contol and r2 <=  self.contol) or r1==r2) and f1 + self.noise < f2 - self.noise)


    def solve(self, *args, **kwargs):
        return runProbSolver(self, *args, **kwargs)
        
    def _solve(self, *args, **kwargs):
        self.debug = True
        return runProbSolver(self, *args, **kwargs)
    
    def objFuncMultiple2Single(self, f):
        #this function can be overdetermined by child class
        if asfarray(f).size != 1: self.err('unexpected f size. The function should be redefined in OO child class, inform OO developers')
        return f

    def inspire(self, newProb, sameConstraints=True):
        # fills some fields of new prob with old prob values
        newProb.castFrom = self.probType

        #TODO: hold it in single place

        fieldsToAssert = ['contol', 'xtol', 'ftol', 'gtol', 'iprint', 'maxIter', 'maxTime', 'maxCPUTime','fEnough', 'goal', 'color', 'debug', 'maxFunEvals', 'xlabel']
        # TODO: boolVars, intVars
        if sameConstraints: fieldsToAssert+= ['lb', 'ub', 'A', 'Aeq', 'b', 'beq']

        for key in fieldsToAssert:
            if hasattr(self, key): setattr(newProb, key, getattr(self, key))


        # note: because of 'userProvided' from prev line
        #self self.userProvided is same to newProb.userProvided
        
#        for key in ['f','df', 'd2f']:
#                if hasattr(self.userProvided, key) and getattr(self.userProvided, key):
#                    setattr(newProb, key, getattr(self.user, key))
        
        Arr = ['f', 'df']
        if sameConstraints:
            Arr += ['c','dc','h','dh','d2c','d2h']
        
        for key in Arr:
            if hasattr(self.userProvided, key):
                if getattr(self.userProvided, key):
                    #setattr(newProb, key, getattr(self.user, key))
                    setattr(newProb, key, getattr(self, key)) if self.isFDmodel else setattr(newProb, key, getattr(self.user, key))
                else:
                    setattr(newProb, key, None)
                        
    FuncDesignerSign = 'f'
    _isFDmodel = lambda self: hasattr(self, self.FuncDesignerSign) and \
    ((type(getattr(self, self.FuncDesignerSign)) in [list, tuple] and 'is_oovar' in dir(getattr(self, self.FuncDesignerSign)[0])) \
                                                                                                or 'is_oovar' in dir(getattr(self, self.FuncDesignerSign) ))
    
    # Base class method
    def _prepare(self): 
        if self._baseProblemIsPrepared: return
        if self.useSparse == 0:
            self.useSparse = False
        elif self.useSparse == 1:
            self.useSparse = True
        if self.useSparse == 'auto' and not scipyInstalled:
            self.useSparse = False
        if self.useSparse == True and not scipyInstalled:
            self.err("You can't set useSparse=True without scipy installed")
        if self._isFDmodel():
            self.isFDmodel = True
            from FuncDesigner import _getAllAttachedConstraints, _getDiffVarsID
            self._FDVarsID = _getDiffVarsID()

            if self.probType in ['SLE', 'NLSP']:
                equations = self.C if self.probType == 'SLE' else self.f
                ConstraintTags = [elem.isConstraint for elem in equations]
                cond_all_oofuns_but_not_cons = not any(ConstraintTags) 
                cond_cons = all(ConstraintTags) 
                if not cond_all_oofuns_but_not_cons and not cond_cons:
                    raise OpenOptException('for FuncDesigner SLE/NLSP constructors args must be either all-equalities or all-oofuns')            
                EQs = [((elem.oofun*(self.ftol/elem.tol) if elem.tol != 0 else elem.oofun) if elem.isConstraint else elem) for elem in equations]
                if self.probType == 'SLE': self.C = EQs
                elif self.probType == 'NLSP': self.f = EQs
                else: raise OpenOptException('bug in OO kernel')
                

            for fn in ['lb', 'ub', 'A', 'Aeq', 'b', 'beq']:
                if not hasattr(self, fn): continue
                val = getattr(self, fn)
                if val is not None and any(isfinite(val)):
                    self.err('while using oovars providing lb, ub, A, Aeq for whole prob is forbidden, use for each oovar instead')
                    
            if not isinstance(self.x0, dict):
                self.err('Unexpected start point type: Python dict expected, '+ str(type(self.x0)) + ' obtained')

            if self.probType in ['LP', 'MILP'] and self.f.getOrder(self.freeVars, self.fixedVars) > 1:
                self.err('for LP/MILP objective function has to be linear, while this one ("%s") is not' % self.f.name)


            if self.fixedVars is None or (self.freeVars is not None and len(self.freeVars)<len(self.fixedVars)):
                D_kwargs = {'Vars':self.freeVars}
            else:
                D_kwargs = {'fixedVars':self.fixedVars}
            D_kwargs['useSparse'] = self.useSparse
            D_kwargs['fixedVarsScheduleID'] = self._FDVarsID
            D_kwargs['exactShape'] = True
            
            self._D_kwargs = D_kwargs
            
            setStartVectorAndTranslators(self)
            
            #Z = self._vector2point(zeros(self.n))
            if len(self._fixedVars) < len(self._freeVars):
                areFixed = lambda dep: dep.issubset(self._fixedVars)
                Z = dict([(v, zeros_like(self._x0[v]) if v not in self._fixedVars else self._x0[v]) for v in self._x0.keys()])
            else:
                areFixed = lambda dep: dep.isdisjoint(self._freeVars)
                Z = dict([(v, zeros_like(self._x0[v]) if v in self._freeVars else self._x0[v]) for v in self._x0.keys()])
            self.theseAreFixed = areFixed
            
            lb, ub = -inf*ones(self.n), inf*ones(self.n)

            # TODO: get rid of start c, h = None, use [] instead
            A, b, Aeq, beq = [], [], [], []
            
            
            
            if type(self.constraints) not in (list, tuple, set):
                self.constraints = [self.constraints]
            oovD = self._oovarsIndDict
            LB = {}
            UB = {}
            
            probtol = self.contol
            
            """                                    gather attached constraints                                    """
            
            C = list(self.constraints)
            self.constraints = set(self.constraints)
            if hasattr(self, 'f'):
                if type(self.f) in [list, tuple, set]:
                    C += list(self.f)
                else: # self.f is oofun
                    C.append(self.f)
            
            self.constraints.update(_getAllAttachedConstraints(C))
            
            """                                         handling constraints                                         """
            for c in self.constraints:
                if not hasattr(c, 'isConstraint'): self.err('The type' + str(type(c)) + 'is inappropriate for problem constraints')
                f, tol = c.oofun, c.tol
                Name = f.name
                
                dep = set([f]) if f.is_oovar else f._getDep()

                _lb, _ub = c.lb, c.ub
                if tol < 0:
                    if any(_lb  == _ub):
                        self.err("You can't use negative tolerance for the equality constraint " + c.name)
                    elif any(_lb - tol >= _ub + tol):
                        self.err("You can't use negative tolerance for so small gap in constraint" + c.name)

                    Shift = (1.0+1e-13)*probtol 
                    #######################
                    # not inplace modification!!!!!!!!!!!!!
                    _lb = _lb + Shift
                    _ub = _ub - Shift
                    #######################
                
                if tol != 0: self.useScaledResidualOutput = True
                
                if tol not in (0, probtol, -probtol):
                    scaleFactor = abs(probtol / tol)
                    f *= scaleFactor
                    _lb, _ub = _lb * scaleFactor, _ub * scaleFactor

                if areFixed(dep):
                    # TODO: get rid of self.contol, use separate contols for each constraint
                    Contol = tol if tol != 0 else self.contol
                    if not c(self._x0, tol=Contol):
                        s = """'constraint "%s" with all-fixed optimization variables it depends on is infeasible in start point, 
                        hence the problem is infeasible, maybe you should change start point'""" % c.name
                        self.err(s)
                    # TODO: check doesn't constraint value exeed self.contol
                    continue

                if self.probType in ['LP', 'MILP', 'LLSP', 'LLAVP'] and f.getOrder(self.freeVars, self.fixedVars) > 1:
                    self.err('for LP/MILP/LLSP/LLAVP all constraints have to be linear, while ' + f.name + ' is not')
                
                # TODO: simplify condition of box-bounded oovar detection
                if f.is_oovar:
                    if areFixed(dep):  
                        if self.x0 is None: self.err('your problem has fixed oovar '+ Name + ' but no value for the one in start point is provided')
                        continue
                    
                    inds = oovD[f]
                    f_size = inds[1] - inds[0]

                    if any(isfinite(_lb)):
                        if _lb.size not in (f_size, 1): 
                            self.err('incorrect size of lower box-bound constraint for %s: 1 or %d expected, %d obtained' % (Name, f_size, _lb.size))
                        val = array(f_size*[_lb] if _lb.size < f_size else _lb)
                        if f not in LB:
                            LB[f] = val
                        else:
                            #max((val, LB[f])) doesn't work for arrays
                            if val.size > 1 or LB[f].size > 1:
                                LB[f][val > LB[f]] = val[val > LB[f]] if val.size > 1 else asscalar(val)
                            else:
                                LB[f] = max((val, LB[f]))

                    if any(isfinite(_ub)):
                        if _ub.size not in (f_size, 1): 
                            self.err('incorrect size of upper box-bound constraint for %s: 1 or %d expected, %d obtained' % (Name, f_size, _ub.size))
                        val = array(f_size*[_ub] if _ub.size < f_size else _ub)
                        if f not in UB:
                            UB[f] = val
                        else:
                            #min((val, UB[f])) doesn't work for arrays
                            if val.size > 1 or LB[f].size > 1:
                                UB[f][val < UB[f]] = val[val < UB[f]] if val.size > 1 else asscalar(val)
                            else:
                                UB[f] = min((val, UB[f]))
                            
                elif _lb == _ub:
                    if f.getOrder(self.freeVars, self.fixedVars) < 2:
                        Aeq.append(self._pointDerivative2array(f.D(Z, **D_kwargs)))      
                        beq.append(-f(Z)+_lb)
                    elif self.h is None: self.h = [f+_lb]
                    else: self.h.append(f+_lb)
                elif isfinite(_ub):
                    if f.getOrder(self.freeVars, self.fixedVars) < 2:
                        A.append(self._pointDerivative2array(f.D(Z, **D_kwargs)))                       
                        b.append(-f(Z)+_ub)
                    elif self.c is None: self.c = [f - _ub]
                    else: self.c.append(f - _ub)
                elif isfinite(_lb):
                    if f.getOrder(self.freeVars, self.fixedVars) < 2:
                        A.append(-self._pointDerivative2array(f.D(Z, **D_kwargs)))                       
                        b.append(f(Z) - _lb)                        
                    elif self.c is None: self.c = [- f - _lb]
                    else: self.c.append(- f - _lb)
                else:
                    self.err('inform OpenOpt developers of the bug')
            if len(b) != 0:
                self.A, self.b = Vstack(A), Hstack(b)
                if hasattr(self.b, 'toarray'): self.b = self.b.toarray()
            if len(beq) != 0:
                self.Aeq, self.beq = Vstack(Aeq), Hstack(beq)
                if hasattr(self.beq, 'toarray'): self.beq = self.beq.toarray()
            for vName, vVal in LB.items():
                inds = oovD[vName]
                lb[inds[0]:inds[1]] = vVal
            for vName, vVal in UB.items():
                inds = oovD[vName]
                ub[inds[0]:inds[1]] = vVal
            self.lb, self.ub = lb, ub
        else: # not namedvariablesStyle
            if self.fixedVars is not None or self.freeVars is not None:
                self.err('fixedVars and freeVars are valid for optimization of FuncDesigner models only')
        if self.x0 is None: 
            arr = ['lb', 'ub']
            if self.probType in ['LP', 'MILP', 'QP', 'SOCP', 'SDP']: arr.append('f')
            if self.probType in ['LLSP', 'LLAVP', 'LUNP']: arr.append('D')
            for fn in arr:
                if not hasattr(self, fn): continue
                fv = asarray(getattr(self, fn))
                if any(isfinite(fv)):
                    self.x0 = zeros(fv.size)
                    break
        self.x0 = ravel(self.x0)
        
        if not hasattr(self, 'n'): self.n = self.x0.size
        if not hasattr(self, 'lb'): self.lb = -inf * ones(self.n)
        if not hasattr(self, 'ub'): self.ub =  inf * ones(self.n)        

        for fn in ('A', 'Aeq'):
            fv = getattr(self, fn)
            if fv is not None:
                #afv = asfarray(fv) if not isspmatrix(fv) else fv.toarray() # TODO: omit casting to dense matrix
                afv = asfarray(fv)  if type(fv) in [list, tuple] else fv
                if len(afv.shape) > 1:
                    if afv.shape[1] != self.n:
                        self.err('incorrect ' + fn + ' size')
                else:
                    if afv.shape != () and afv.shape[0] == self.n: afv = afv.reshape(1, self.n)
                setattr(self, fn, afv)
            else:
                setattr(self, fn, asfarray([]).reshape(0, self.n))
                
        nA, nAeq = prod(self.A.shape), prod(self.Aeq.shape) 
        SizeThreshold = 2 ** 15
        if scipyInstalled:
            from scipy.sparse import csc_matrix
            if isspmatrix(self.A) or (nA > SizeThreshold  and flatnonzero(self.A).size < 0.25*nA):
                self._A = csc_matrix(self.A)
            if isspmatrix(self.Aeq) or (nAeq > SizeThreshold and flatnonzero(self.Aeq).size < 0.25*nAeq):
                self._Aeq = csc_matrix(self.Aeq)
            
        elif nA > SizeThreshold or nAeq > SizeThreshold:
            self.pWarn(scipyAbsentMsg)
            
        self._baseProblemIsPrepared = True



class MatrixProblem(baseProblem):
    _baseClassName = 'Matrix'
    ftol = 1e-8
    contol = 1e-8
    #obsolete, should be removed
    # still it is used by lpSolve
    # Awhole * x {<= | = | >= } b
    Awhole = None # matrix m x n, n = len(x)
    bwhole = None # vector, size = m x 1
    dwhole = None #vector of descriptors, size = m x 1
    # descriptors dwhole[j] should be :
    # 1 : <Awhole, x> [j] greater (or equal) than bwhole[j]
    # -1 : <Awhole, x> [j] less (or equal) than bwhole[j]
    # 0 : <Awhole, x> [j] = bwhole[j]
    def __init__(self, *args, **kwargs):
        baseProblem.__init__(self, *args, **kwargs)
        self.kernelIterFuncs = setDefaultIterFuncs('Matrix')

    def _Prepare(self):
        if self.prepared == True:
            return
        baseProblem._prepare(self)
        self.prepared = True

    # TODO: move the function to child classes
    def _isUnconstrained(self):
        s = ((), [], array([]), None)
        return self.b.size ==0 and self.beq.size==0 and (self.lb in s or all(isinf(self.lb))) and (self.ub in s or all(isinf(self.ub)))


class Parallel:
    def __init__(self):
        self.f = False# 0 - don't use parallel calclations, 1 - use
        self.c = False
        self.h = False
        #TODO: add paralell func!
        #self.parallel.fun = dfeval

class Args:
    def __init__(self): pass
    f, c, h = (), (), ()

class NonLinProblem(baseProblem, nonLinFuncs, Args):
    _baseClassName = 'NonLin'
    diffInt = ProbDefaults['diffInt']        #finite-difference gradient aproximation step
    #non-linear constraints
    c = None # c(x)<=0
    h = None # h(x)=0
    #lines with |info_user-info_numerical| / (|info_user|+|info_numerical+1e-15) greater than maxViolation will be shown
    maxViolation = 1e-2
    JacobianApproximationStencil = 1
    def __init__(self, *args, **kwargs):
        baseProblem.__init__(self, *args, **kwargs)
        if not hasattr(self, 'args'): self.args = Args()
        self.prevVal = {}
        for fn in ['f', 'c', 'h', 'df', 'dc', 'dh', 'd2f', 'd2c', 'd2h']:
            self.prevVal[fn] = {'key':None, 'val':None}

        self.functype = {}

        #self.isVectoriezed = False

#        self.fPattern = None
#        self.cPattern = None
#        self.hPattern = None
        self.kernelIterFuncs = setDefaultIterFuncs('NonLin')

    def checkdf(self, *args,  **kwargs):
        return self.checkGradient('df', *args,  **kwargs)

    def checkdc(self, *args,  **kwargs):
        return self.checkGradient('dc', *args,  **kwargs)

    def checkdh(self, *args,  **kwargs):
        return self.checkGradient('dh', *args,  **kwargs)
    
    def checkGradient(self, funcType, *args,  **kwargs):
        self._Prepare()
        if not DerApproximatorIsInstalled:
            self.err('To perform gradients check you should have DerApproximator installed, see http://openopt.org/DerApproximator')
        
        if not getattr(self.userProvided, funcType):
            self.warn("you haven't analitical gradient provided for " + funcType[1:] + ', turning derivatives check for it off...')
            return
        if len(args)>0:
            if len(args)>1 or 'x' in kwargs:
                self.err('checkd<func> funcs can have single argument x only (then x should be absent in kwargs )')
            xCheck = asfarray(args[0])
        elif 'x' in kwargs:
            xCheck = asfarray(kwargs['x'])
        else:
            xCheck = asfarray(self.x0)
        
        maxViolation = 0.01
        if 'maxViolation' in kwargs:
            maxViolation = kwargs['maxViolation']
            
        self.disp(funcType + (': checking user-supplied gradient of shape (%d, %d)' % (getattr(self, funcType[1:])(xCheck).size, xCheck.size)))
        self.disp('according to:')
        self.disp('    diffInt = ' + str(self.diffInt)) # TODO: ADD other parameters: allowed epsilon, maxDiffLines etc
        self.disp('    |1 - info_user/info_numerical| < maxViolation = '+ str(maxViolation))        
        
        check_d1(getattr(self, funcType[1:]), getattr(self, funcType), xCheck, **kwargs)
        
        # reset counters that were modified during check derivatives
        self.nEvals[funcType[1:]] = 0
        self.nEvals[funcType] = 0
        
    def _makeCorrectArgs(self):
        argslist = dir(self.args)
        if not ('f' in argslist and 'c' in argslist and 'h' in argslist):
            tmp, self.args = self.args, autocreate()
            self.args.f = self.args.c = self.args.h = tmp
        for j in ('f', 'c', 'h'):
            v = getattr(self.args, j)
            if type(v) != type(()): setattr(self.args, j, (v,))

    def __finalize__(self):
        #BaseProblem.__finalize__(self)
        if self.isFDmodel:
            self.xf = self._vector2point(self.xf)

    def _Prepare(self):
        baseProblem._prepare(self)
        if hasattr(self, 'solver'):
            if not self.solver.iterfcnConnected:
                if self.solver.funcForIterFcnConnection == 'f':
                    if not hasattr(self, 'f_iter'):
                        self.f_iter = max((self.n, 4))
                else:
                    if not hasattr(self, 'df_iter'):
                        self.df_iter = True
        
        if self.prepared == True:
            return
            
        
        
        # TODO: simplify it
        self._makeCorrectArgs()
        for s in ('f', 'df', 'd2f', 'c', 'dc', 'd2c', 'h', 'dh', 'd2h'):
            derivativeOrder = len(s)-1
            self.nEvals[Copy(s)] = 0
            if hasattr(self, s) and getattr(self, s) not in (None, (), []) :
                setattr(self.userProvided, s, True)

                A = getattr(self,s)

                if type(A) not in [list, tuple]: #TODO: add or ndarray(A)
                    A = (A,)#make tuple
                setattr(self.user, s, A)
            else:
                setattr(self.userProvided, s, False)
            if derivativeOrder == 0:
                setattr(self, s, lambda x, IND=None, userFunctionType= s, ignorePrev=False, getDerivative=False: \
                        self.wrapped_func(x, IND, userFunctionType, ignorePrev, getDerivative))
            elif derivativeOrder == 1:
                setattr(self, s, lambda x, ind=None, funcType=s[-1], ignorePrev = False, useSparse=self.useSparse:
                        self.wrapped_1st_derivatives(x, ind, funcType, ignorePrev, useSparse))
            elif derivativeOrder == 2:
                setattr(self, s, getattr(self, 'user_'+s))
            else:
                self.err('incorrect non-linear function case')

        self.diffInt = ravel(self.diffInt)
        
        # TODO: mb get rid of the field
        self.vectorDiffInt = self.diffInt.size > 1
        
        if self.scale is not None:
            self.scale = ravel(self.scale)
            if self.vectorDiffInt or self.diffInt[0] != ProbDefaults['diffInt']:
                self.info('using both non-default scale & diffInt is not recommended. diffInt = diffInt/scale will be used')
            self.diffInt = self.diffInt / self.scale
       

        #initialization, getting nf, nc, nh etc:
        for s in ['c', 'h', 'f']:
            if not getattr(self.userProvided, s):
                setattr(self, 'n'+s, 0)
            else:
                setNonLinFuncsNumber(self,  s)
                
        self.prepared = True

    # TODO: move the function to child classes
    def _isUnconstrained(self):
        s = ((), [], array([]), None)
        return self.b.size ==0 and self.beq.size==0 and not self.userProvided.c and not self.userProvided.h \
            and (self.lb in s or all(isinf(self.lb))) and (self.ub in s or all(isinf(self.ub)))
    

def minimize(p, *args, **kwargs):
    if 'goal' in kwargs:
        if kwargs['goal'] in ['min', 'minimum']:
            p.warn("you shouldn't pass 'goal' to the function 'minimize'")
        else:
            p.err('ambiguous goal has been requested: function "minimize", goal: %s' %  kwargs['goal'])
    p.goal = 'minimum'
    return runProbSolver(p, *args, **kwargs)

def maximize(p, *args, **kwargs):
    if 'goal' in kwargs:
        if kwargs['goal'] in ['max', 'maximum']:
            p.warn("you shouldn't pass 'goal' to the function 'maximize'")
        else:
            p.err('ambiguous goal has been requested: function "maximize", goal: %s' %  kwargs['goal'])
    p.goal = 'maximum'
    return runProbSolver(p, *args, **kwargs)            
