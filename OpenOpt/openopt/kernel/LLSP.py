from ooMisc import assignScript
from baseProblem import MatrixProblem
from numpy import asfarray, ones, inf, dot, nan, zeros, any, all, isfinite, eye, vstack
from numpy.linalg import norm
import NLP

class LLSP(MatrixProblem):
    __optionalData__ = ['damp', 'X', 'c']
    expectedArgs = ['C', 'd']# for FD it should be Cd and x0
    probType = 'LLSP'
    goal = 'minimum'
    allowedGoals = ['minimum', 'min']
    showGoal = False
    FuncDesignerSign = 'C'
    
    def __init__(self, *args, **kwargs):
        MatrixProblem.__init__(self, *args, **kwargs)
        if 'damp' not in kwargs.keys(): self.damp = None
        if 'f' not in kwargs.keys(): self.f = None
        
        if len(args)>0:
            self.n = args[0].shape[1]
        else:
            self.n = kwargs['C'].shape[1]
        #self.lb = -inf * ones(self.n)
        #self.ub =  inf * ones(self.n)
        if not hasattr(self, 'lb'): self.lb = -inf * ones(self.n)
        if not hasattr(self, 'ub'): self.ub = inf * ones(self.n)
        if self.x0 is None: self.x0 = zeros(self.n)        


    def objFunc(self, x):
        r = norm(dot(self.C, x) - self.d) ** 2  /  2.0
        if self.damp is not None:
            r += self.damp * norm(x-self.X)**2 / 2.0
        if self.f is not None: r += dot(self.f, x)
        return r

    def llsp2nlp(self, solver, **solver_params):
        if hasattr(self,'x0'): p = NLP.NLP(ff, self.x0, df=dff, d2f=d2ff)
        else: p = NLP.NLP(ff, zeros(self.n), df=dff, d2f=d2ff)
        p.args.f = self # DO NOT USE p.args = self IN PROB ASSIGNMENT!
        self.inspire(p)
        self.iprint = -1
        # for LLSP plot is via NLP
        p.show = self.show
        p.plot, self.plot = self.plot, 0
        #p.checkdf()
        r = p.solve(solver, **solver_params)
        self.xf, self.ff, self.rf = r.xf, r.ff, r.rf
        return r

    def __prepare__(self):
        if isinstance(self.d, dict): # FuncDesigner startPoint 
            self.x0 = self.d
        MatrixProblem.__prepare__(self)
        if self.isFDmodel:
            C, d = [], []
            Z = self._vector2point(zeros(self.n))
            for lin_oofun in self.C:
                C.append(self._pointDerivative2array(lin_oofun._D(Z, **self._D_kwargs)))
                d.append(-lin_oofun(Z))
            self.C, self.d = vstack(C), vstack(d).flatten()
        if not self.damp is None and not any(isfinite(self.X)):
            self.X = zeros(self.n)




#def llsp_init(prob, kwargs):
#    if 'damp' not in kwargs.keys(): kwargs['damp'] = None
#    if 'X' not in kwargs.keys(): kwargs['X'] = nan*ones(prob.n)
#    if 'f' not in kwargs.keys(): kwargs['f'] = nan*ones(prob.n)
#
#    if prob.x0 is nan: prob.x0 = zeros(prob.n)


#def ff(x, LLSPprob):
#    r = dot(LLSPprob.C, x) - LLSPprob.d
#    return dot(r, r)
ff = lambda x, LLSPprob: LLSPprob.objFunc(x)
def dff(x, LLSPprob):
    r = dot(LLSPprob.C.T, dot(LLSPprob.C,x)  - LLSPprob.d)
    if not LLSPprob.damp is None: r += LLSPprob.damp*(x - LLSPprob.X)
    if LLSPprob.f is not None and all(isfinite(LLSPprob.f)) : r += LLSPprob.f
    return r

def d2ff(x, LLSPprob):
    r = dot(LLSPprob.C.T, LLSPprob.C)
    if not LLSPprob.damp is None: r += LLSPprob.damp*eye(x.size)
    return r
