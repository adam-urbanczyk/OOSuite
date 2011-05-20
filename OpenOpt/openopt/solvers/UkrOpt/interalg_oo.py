from numpy import isfinite, all, argmax, where, delete, array, asarray, inf, argmin, hstack, vstack, tile, arange, amin, \
logical_and, float64, ceil, amax, inf, ndarray, isinf, any, logical_or, nan, take, logical_not, asanyarray, searchsorted

import numpy
from numpy.linalg import norm, solve, LinAlgError
from openopt.kernel.setDefaultIterFuncs import SMALL_DELTA_X,  SMALL_DELTA_F, MAX_NON_SUCCESS
from openopt.kernel.baseSolver import *
from openopt.kernel.Point import Point
from FuncDesigner import ooPoint

hasHeapMerge = False
try:
    from heapq import merge
    hasHeapMerge = True
except ImportError:
    pass

try:
    from bottleneck import nanargmin, nanargmax, nanmin
    bottleneck_is_present = True
except ImportError:
    from numpy import nanmin, nanargmin, nanargmax
    bottleneck_is_present = False
#from numpy import nanmin, nanargmin, nanargmax

class interalg(baseSolver):
    __name__ = 'interalg_0.17'
    __license__ = "BSD"
    __authors__ = "Dmitrey"
    __alg__ = ""
    __optionalDataThatCanBeHandled__ = ['lb', 'ub']
    iterfcnConnected = True
    fStart = None
    dataType = float64
    #maxMem = '150MB'
    maxNodes = 150000
    maxActiveNodes = 1500
    useArrays4Store = False
    __isIterPointAlwaysFeasible__ = lambda self, p: p.__isNoMoreThanBoxBounded__()
    #_canHandleScipySparse = True

    #lv default parameters

    def __init__(self): pass
    def __solver__(self, p):
        if not p.__isFiniteBoxBounded__(): 
            p.err('solver %s requires finite lb, ub: lb <= x <= ub' % self.__name__)
#        if p.goal in ['max', 'maximum']:
#            p.err('solver %s cannot handle maximization problems yet' % self.__name__)
        if p.fixedVars is not None:
            p.err('solver %s cannot handle FuncDesigner problems with some variables declared as fixed' % self.__name__)
        if p.probType in ('LP', 'MILP', 'MINLP'):
            p.err("the solver can't handle problems of type " + p.probType)
        if not p.isFDmodel:
            p.err('solver %s can handle only FuncDesigner problems' % self.__name__)
        for val in p._x0.values():
            if isinstance(val,  (list, tuple, ndarray)) and len(val) > 1:
                p.err('''
                solver %s currently can handle only single-element variables, 
                use oovars(n) instead of oovar(size=n)'''% self.__name__)

        if not hasHeapMerge:
            p.pWarn('''cannot import merge from heapq, 
            maybe you using Python version prior to 2.6
            useArrays4Store will be set to False
            (this is slower and more unstable mode, 
            maybe even buggy, out of maintanance)
            ''')
            self.useArrays4Store = True
        

        point = p.point
        
        p.kernelIterFuncs.pop(SMALL_DELTA_X)
        p.kernelIterFuncs.pop(SMALL_DELTA_F)
        if MAX_NON_SUCCESS in p.kernelIterFuncs: 
            p.kernelIterFuncs.pop(MAX_NON_SUCCESS)
        
        if not bottleneck_is_present:
                p.pWarn('''
                installation of Python module "bottleneck" 
                (http://berkeleyanalytics.com/bottleneck,
                available via easy_install, takes several minutes for compilation)
                could speedup the solver %s''' % self.__name__)
        
        p.useMultiPoints = True
        
        nNodes = []        
        p.extras['nNodes'] = nNodes
        nActiveNodes = []
        p.extras['nActiveNodes'] = nActiveNodes
        
        dataType = self.dataType
        if type(dataType) == str:
            if not hasattr(numpy, dataType):
                p.pWarn('your architecture has no type "%s", float64 will be used instead')
                dataType = 'float64'
            dataType = getattr(numpy, dataType)
        lb, ub = asarray(p.lb, dataType), asarray(p.ub, dataType)

        n = p.n
        f = p.f
        C = p.constraints
        ooVars = p._freeVarsList
        
        fTol = p.fTol
        if fTol is None:
            fTol = 1e-7
            p.warn('solver %s require p.fTol value (required objective function tolerance); 10^-7 will be used' % self.__name__)

        xRecord = 0.5 * (lb + ub)

        CurrentBestKnownPointsMinValue = inf
            
        y = lb.reshape(1, -1)
        e = ub.reshape(1, -1)
        fr = inf

        fd_obj = p.user.f[0]
        if p.fOpt is not None:  fOpt = p.fOpt
        if p.goal in ('max', 'maximum'):
            fd_obj = -fd_obj
            if p.fOpt is not None:
                fOpt = -p.fOpt

        
        # TODO: maybe rework it, especially for constrained case
        fStart = self.fStart

        if fStart is not None and fStart < CurrentBestKnownPointsMinValue: 
            fr = fStart
            
        for X0 in [point(xRecord), point(p.x0)]:
            if X0.isFeas(altLinInEq=False) and X0.f() < CurrentBestKnownPointsMinValue:
                CurrentBestKnownPointsMinValue = X0.f()
            
        tmp = fd_obj(p._x0)
        if  tmp < fr:
            fr = tmp
            
        if p.fOpt is not None:
            if fOpt > fr:
                p.warn('user-provided fOpt seems to be incorrect, ')
            fr = fOpt
        


#        if dataType==float64:
#            numBytes = 8 
#        elif self.dataType == 'float128':
#            numBytes = 16
#        else:
#            p.err('unknown data type, should be float64 or float128')
#        maxMem = self.maxMem
#        if type(maxMem) == str:
#            if maxMem.lower().endswith('kb'):
#                maxMem = int(float(maxMem[:-2]) * 2 ** 10)
#            elif maxMem.lower().endswith('mb'):
#                maxMem = int(float(maxMem[:-2]) * 2 ** 20)
#            elif maxMem.lower().endswith('gb'):
#                maxMem = int(float(maxMem[:-2]) * 2 ** 30)
#            elif maxMem.lower().endswith('tb'):
#                maxMem = int(float(maxMem[:-2]) * 2 ** 40)
#            else:
#                p.err('incorrect max memory parameter value, should end with KB, MB, GB or TB')
        m = 0
        #maxActive = 1
        #maxActiveNodes = self.maxActiveNodes 
        
        b = array([]).reshape(0, n)
        v = array([]).reshape(0, n)
        maxz = []
        _in = []
        z = array([]).reshape(0, 2*n)
        l = array([]).reshape(0, 2*n)
        
        y_excluded, e_excluded, o_excluded, a_excluded = [], [], [], []
        k = True
        g = inf
        C = p._FD.nonBoxCons
        isOnlyBoxBounded = p.__isNoMoreThanBoxBounded__()
        varTols = p.variableTolerances
        nCut = 1 if fd_obj.isUncycled and all(isfinite(a)) and all(isfinite(o)) and isOnlyBoxBounded else self.maxNodes
        
        for itn in range(p.maxIter+10):
            ip = func10(y, e, n, ooVars)
            
#            for f, lb_, ub_ in C:
#                TMP = f.interval(domain, dataType)
#                lb, ub = asarray(TMP.lb, dtype=dataType), asarray(TMP.ub, dtype=dataType)
                
            o, a, bestCenter, bestCenterObjective = func8(ip, fd_obj, dataType)
            
            if p.debug and any(a<o):  p.warn('interval lower bound exceeds upper bound, it seems to be FuncDesigner kernel bug')
            
            xk, Min = bestCenter, bestCenterObjective
           
            p.iterfcn(xk, Min)
            if p.istop != 0: 
                break
            
            if CurrentBestKnownPointsMinValue > Min:
                CurrentBestKnownPointsMinValue = Min
                xRecord = xk# TODO: is copy required?
            if fr > Min:
                fr = Min

            fo = min((fr, CurrentBestKnownPointsMinValue - fTol)) 
            
            m = e.shape[0]
            o, a = o.reshape(2*n, m).T, a.reshape(2*n, m).T
            
            y, e, o, a = func7(y, e, o, a)
            s, q = o[:, 0:n], o[:, n:2*n]
            tmp = where(q<s, q, s)
            ind = nanargmax(tmp, 1)
            ar = tmp[arange(m),ind]

            if self.useArrays4Store:
                y, e, o, a, ar = \
                vstack((y, b)), vstack((e, v)), vstack((o, z)), vstack((a, l)), hstack((ar, maxz))

                y, e, o, a, ar, g = func6(y, e, o, a, ar, n, fo, g)
                y, e, o, a, ar, g = func5(y, e, o, a, ar,  n, nCut, g)
                y, e, o, a, ar, b, v, z, l, maxz =\
                func3(y, e, o, a, ar, n, self.maxActiveNodes)
                m = y.shape[0]
                nActiveNodes.append(m)
                nNodes.append(m + b.shape[0])
                
                
            
            
#            ind = all(e-y <= varTols, 1)
#            y_excluded += y[ind]
#            e_excluded += e[ind]
#            o_excluded += o[ind]
#            a_excluded += a[ind]
            else:
                nodes = func11(y, e, o, a, ar)
                nodes.sort()
                an = list(merge(nodes, _in))
                an, g = func9(an, n, fo, g)
            

            # TODO: rework it
            if (self.useArrays4Store and y.size == 0) or (not self.useArrays4Store and len(an) == 0): 
                if not self.useArrays4Store: 
                    # For more safety against bugs
                    an1 = []
                    _in = []
                k = False
                p.istop, p.msg = 1000, 'optimal solution obtained'
                break            
            
            
            
            if not self.useArrays4Store:
                an, g = func52(an, n, nCut, g)
                
                an1, _in = func32(an, n, self.maxActiveNodes)

                m = len(an1)
                nActiveNodes.append(m)
                
                nNodes.append(len(an1) + len(_in))

                y, e, o, a = asanyarray([t.data[0] for t in an1]), \
                asanyarray([t.data[1] for t in an1]), \
                asanyarray([t.data[2] for t in an1]), \
                asanyarray([t.data[3] for t in an1])
            
            # Changes end
            y, e = func4(y, e, o, a, n, fo)
            
            t = func1(y, e, o, a, n, varTols)
            y, e = func2(y, e, t)
            # End of main cycle
            
        ff = f(xRecord)
        p.iterfcn(xRecord, ff)
        if not self.useArrays4Store:
            o = asanyarray([t.data[2] for t in an])
        if o.size != 0:
            g = nanmin([nanmin(o), g])
        p.extras['isRequiredPrecisionReached'] = True if ff - g < fTol and k is False else False
        # TODO: simplify it
        if p.goal in ('max', 'maximum'):
            g = -g
            o = -o
        tmp = [nanmin(hstack((ff, g, o.flatten()))), numpy.asscalar(array((ff if p.goal not in ['max', 'maximum'] else -ff)))]
        if p.goal in ['max', 'maximum']: tmp = tmp[1], tmp[0]
        p.extras['extremumBounds'] = tmp
        if p.iprint >= 0:
            s = 'Solution with required tolerance %0.1e \n is%s guarantied (obtained precision: %0.1e)' \
                   %(fTol, '' if p.extras['isRequiredPrecisionReached'] else ' NOT', tmp[1]-tmp[0])
            if not p.extras['isRequiredPrecisionReached']: s += '\nincrease maxNodes (current value %d)' % self.maxNodes
            p.info(s)

def func10(y, e, n, ooVars):
    LB = [[] for i in range(n)]
    UB = [[] for i in range(n)]
    m = y.shape[0]
    Centers = 0.5 * (y + e)
    
    # TODO: remove the cycle
    #T1, T2 = tile(y, (2*n,1)), tile(e, (2*n,1))
    
    for i in range(n):
        t1, t2 = tile(y[:, i], 2*n), tile(e[:, i], 2*n)
        #t1, t2 = T1[:, i], T2[:, i]
        #T1[(n+i)*m:(n+i+1)*m, i] = T2[i*m:(i+1)*m, i] = Centers[:, i]
        t1[(n+i)*m:(n+i+1)*m] = t2[i*m:(i+1)*m] = Centers[:, i]
        LB[i], UB[i] = t1, t2

####        LB[i], UB[i] = T1[:, i], T2[:, i]

#    sh1, sh2, inds = [], [], []
#    for i in range(n):
#        sh1+= arange((n+i)*m, (n+i+1)*m).tolist()
#        inds +=  [i]*m
#        sh2 += arange(i*m, (i+1)*m).tolist()

#    sh1, sh2, inds = asdf(m, n)
#    asdf2(T1, T2, Centers, sh1, sh2, inds)
    
    #domain = dict([(v, (T1[:, i], T2[:, i])) for i, v in enumerate(ooVars)])
    domain = dict([(v, (LB[i], UB[i])) for i, v in enumerate(ooVars)])
    
    domain = ooPoint(domain, skipArrayCast = True)
    domain.isMultiPoint = True
    return domain

def func8(domain, fd_obj, dataType):

    TMP = fd_obj.interval(domain, dataType)
    
    #TODO: remove 0.5*(val[0]+val[1]) from cycle
    centers = dict([(key, 0.5*(val[0]+val[1])) for key, val in domain.items()])
    centers = ooPoint(centers, skipArrayCast = True)
    centers.isMultiPoint = True
    F = fd_obj(centers)
    bestCenterInd = nanargmin(F)
    if isnan(bestCenterInd):
        bestCenterInd = 0
        bestCenterObjective = inf
    
    # TODO: check it , maybe it can be improved
    #bestCenter = centers[bestCenterInd]
    bestCenter = array([0.5*(val[0][bestCenterInd]+val[1][bestCenterInd]) for val in domain.values()], dtype=dataType)
    bestCenterObjective = atleast_1d(F)[bestCenterInd]
    #assert TMP.lb.dtype == dataType
    return asarray(TMP.lb, dtype=dataType), asarray(TMP.ub, dtype=dataType), bestCenter, bestCenterObjective

def func7(y, e, o, a):
    IND = logical_and(all(isnan(o), 1), all(isnan(a), 1))
    #ind = where(IND)[0]
    #if ind.size != 0:
    #    y, e, o, a = delete(y, ind, 0), delete(e, ind, 0), delete(o, ind, 0), delete(a, ind, 0)
    if any(IND):
        j = where(logical_not(IND))[0]
        lj = j.size
        y = take(y, j, axis=0, out=y[:lj])
        e = take(e, j, axis=0, out=e[:lj])
        o = take(o, j, axis=0, out=o[:lj])
        a = take(a, j, axis=0, out=a[:lj])
    return y, e, o, a 

def func6(y, e, o, a, ar, n, fo, g):
    ind1 = ar > fo
    if any(ind1):
        g = nanmin((g, nanmin(ar[ind1])))
        
        #OLD
        #ind = where(ind1)[0]
        #y, e, o, a = delete(y, ind, 0), delete(e, ind, 0), delete(o, ind, 0), delete(a, ind, 0)
        
        #NEW
        j = where(logical_not(ind1))[0]
        lj = j.size
        y = take(y, j, axis=0, out=y[:lj])
        e = take(e, j, axis=0, out=e[:lj])
        o = take(o, j, axis=0, out=o[:lj])
        a = take(a, j, axis=0, out=a[:lj])
        ar = ar[j]
    return y, e, o, a, ar, g

def func9(an, n, fo, g):
    ar = [node.key for node in an]
    ind = searchsorted(ar, fo, side='right')
    if ind == len(ar):
        return an, g
    else:
        g = nanmin((g, nanmin(ar[ind])))
        return an[:ind], g

def func5(y, e, o, a, ar, n, nCut, g):
    m = e.shape[0]
    if m > nCut:
        j = m - nCut
        
        # OLD
#        s, q = o[:, 0:n], o[:, n:2*n]
#        tmp = where(q<s, q, s)
#        ind = nanargmax(tmp, 1)
#        values = tmp[arange(m),ind]
#        ind = values.argsort()
        
        # NEW
        ind = ar.argsort()
        
        h = m-j-1
        g = nanmin((ar[h], g))
        ind0 = ind
        #OLD
#        ind = ind0[m-j:]
##        y0 = y.copy()
##        e0 = e.copy()
##        o0 = o.copy()
##        a0 = a.copy()
#        y, e, o, a = delete(y, ind, 0), delete(e, ind, 0), delete(o, ind, 0), delete(a, ind, 0)
        #NEW
        j = ind0[:-j]
        lj = j.size
#        assert all(y == take(y0, j, axis=0))
#        assert all(e == take(e0, j, axis=0))
#        assert all(o == take(o0, j, axis=0))
#        assert all(a == take(a0, j, axis=0))
        y = take(y, j, axis=0, out=y[:lj])
        e = take(e, j, axis=0, out=e[:lj])
        o = take(o, j, axis=0, out=o[:lj])
        a = take(a, j, axis=0, out=a[:lj])
        ar = ar[j]
    return y, e, o, a, ar, g

def func52(an, n, nCut, g):
    m = len(an)
    if m > nCut:
        ar = [node.key for node in an]
        g = nanmin((ar[nCut], g))
        an = an[:nCut]
    return an, g

def func4(y, e, o, a, n, fo):
    centers = 0.5*(y + e)
    s, q = o[:, 0:n], o[:, n:2*n]
    #ind = s > fo
    ind = logical_or(s > fo, isnan(s)) # TODO: assert isnan(s) is same to isnan(a_modL)
    if any(ind):
        y[ind] = centers[ind]
    #ind = q > fo
    ind = logical_or(q > fo, isnan(q))# TODO: assert isnan(q) is same to isnan(a_modU)
    if any(ind):
        e[ind] = centers[ind]
    return y, e

def func3(y, e, o, a, ar, n, maxActiveNodes):
    m = y.shape[0]
    if m <= maxActiveNodes:
        b = array([]).reshape(0, n)
        v = array([]).reshape(0, n)
        z = array([]).reshape(0, 2*n)
        l = array([]).reshape(0, 2*n)
        maxz = array([])
    else:
        #OLD
#        s, q = o[:, 0:n], o[:, n:2*n]
#        tmp = where(q<s, q, s)
#        ind = nanargmax(tmp, 1)
#        values = tmp[arange(m),ind]
#        ind = values.argsort()
        #NEW
        ind = ar.argsort()
        #assert all(ind == ind2)
        
        i1, i2 = ind[:maxActiveNodes], ind[maxActiveNodes:]
        # old
#                ind = i2
#                b, v, z, l = y[ind], e[ind], o[ind], a[ind]
#                y, e, o, a = delete(y, ind, 0), delete(e, ind, 0), delete(o, ind, 0), delete(a, ind, 0)
        
        # new
        ind = i1
        
        i1.sort()
        i2.sort()
        
        #OLD
        #b, v, z, l = delete(y, ind, 0), delete(e, ind, 0), delete(o, ind, 0), delete(a, ind, 0)
        #y, e, o, a = y[ind], e[ind], o[ind], a[ind]
        #NEW
        y_tmp, e_tmp, o_tmp, a_tmp, ar_tmp = y[ind], e[ind], o[ind], a[ind], ar[ind]
        b = take(y, i2, axis=0, out=y[:len(i2)])
        v = take(e, i2, axis=0, out=e[:len(i2)])
        z = take(o, i2, axis=0, out=o[:len(i2)])
        l = take(a, i2, axis=0, out=a[:len(i2)])
        maxz = ar[i2]
        y, e, o, a, ar = y_tmp, e_tmp, o_tmp, a_tmp, ar_tmp
        
    return y, e, o, a, ar, b, v, z, l, maxz

def func32(an, n, maxActiveNodes):
    m = len(an)
    if m > maxActiveNodes:
        an1, _in = an[:maxActiveNodes], an[maxActiveNodes:]
    else:
        an1, _in = an, []
    return an1, _in

def func1(y, e, o, a, n, varTols):
    Case = 1 # TODO: check other
    if Case == -3:
        t = argmin(a, 1) % n
    elif Case == -2:
        t = asarray([itn % n]*m)
    elif Case == -1:
        tmp = a - o
        tmp1, tmp2 = tmp[:, 0:n], tmp[:, n:2*n]
        tmp = tmp1
        ind = where(tmp2>tmp1)
        tmp[ind] = tmp2[ind]
        #tmp = tmp[:, 0:n] + tmp[:, n:2*n]
        t = argmin(tmp, 1) 
    elif Case == 0:
        t = argmin(a - o, 1) % n
    elif Case == 1:
#                a1, a2 = a[:, 0:n], a[:, n:]
#                ind = a1 < a2
#                a1[ind] = a2[ind]
#                t = argmin(a1, 1)

        a = a.copy() # to remain it unchanged in higher stack level funcs
        a[e-y<varTols] = nan
        
        t = nanargmin(a, 1) % n
        if any(isinf(a)):
            # new
#                    a1, a2 = a[:, 0:n], a[:, n:]
#                    
#                    #ind1, ind2 = isinf(a1), isinf(a2)
#                    #ind_any_infinite = logical_or(ind1, ind2)
#                    ind1, ind2 = isinf(a1), isinf(a2)
#                    ind_any_infinite = logical_or(ind1, ind2)
#                    
#                    a_ = where(a1 < a2, a1, a2)
#                    a_[ind_any_infinite] = inf
#                    t = nanargmin(a_, 1) 
#                    ind = isinf(a_[w, t])

##                    #old
            ###t = argmin(a, 1) % n
            #ind = logical_or(all(isinf(a), 1), all(isinf(o), 1))
            ind = all(isinf(a), 1)
            #ind = all(isinf(a), 1)
            
            #print 'itn:', itn
            if any(ind):
                boxShapes = e[ind] - y[ind]
                t[ind] = argmax(boxShapes, 1)
                
    elif Case == 2:
        o1, o2 = o[:, 0:n], o[:, n:]
        ind = o1 > o2
        o1[ind] = o2[ind]                
        t = argmax(o1, 1)
    elif Case == 3:
        # WORST
        t = argmin(o, 1) % n
    elif Case == 4:
        # WORST
        t = argmax(a, 1) % n
    elif Case == 5:
        tmp = where(o[:, 0:n]<o[:, n:], o[:, 0:n], o[:, n:])
        t = argmax(tmp, 1)
    return t


def func2(y, e, t):
    u, en = y.copy(), e.copy()
    m = y.shape[0]
    w = arange(m)
    th = 0.5 * (u[w, t] + en[w, t])
    u[w, t] = th
    en[w, t] = th
    
    u = vstack((y, u))
    en = vstack((en, e))
    
    return u, en


func11 = lambda y, e, o, a, ar: [si(ar[i], y[i], e[i], o[i], a[i]) for i in range(len(ar))]
    
class si:
    def __init__(self, key, *data):
        self.key = key
        self.data = data
    
    __lt__ = lambda self, other: self.key < other.key
    __le__ = lambda self, other: self.key <= other.key
    __gt__ = lambda self, other: self.key > other.key
    __ge__ = lambda self, other: self.key >= other.key
    __eq__ = lambda self, other: self.key == other.key
    

#                N1, N2 = nActivePoints[-2:]
#                t2, t1 = p.iterTime[-1] - p.iterTime[-2], p.iterTime[-2] - p.iterTime[-3]
#                c1 = (t2-t1)/(N2-N1) if N1!=N2 else numpy.nan
#                c2 = t2 - c1* N2
#                print N1, N2, c1*N1, c2
                #IterTime = c1 * nPoints + c2
#                c1 = (t_new - t_prev) / (N_new - N_prev)
#                c2 = t_new - c1* N_new
#                maxActive = amax((15, int(15*c2/c1)))
                
#                #print m, currIterActivePointsNum
#                if (p.iterTime[-1] - p.iterTime[-2])/m > 1.2 * (p.iterTime[-2]-p.iterTime[-3]) /currIterActivePointsNum  and p.iterTime[-1]-p.iterTime[-2] > 0.01:
#                    maxActive = amax((int(maxActive / 1.5), 1))
#                else:
#                    maxActive = amin((maxActive*2, m))
#            else:
#                maxActive = m

#def asdf(m, n):
#    sh1, sh2, inds = [], [], []
#    for i in range(n):
#        sh1+= arange((n+i)*m, (n+i+1)*m).tolist()
#        inds +=  [i]*m
#        sh2 += arange(i*m, (i+1)*m).tolist()
#    return sh1, sh2, inds
#
#def asdf2(T1, T2, Centers, sh1, sh2, inds):
#    T1[sh1, inds] = Centers.T.flatten()
#    T2[sh2, inds] = Centers.T.flatten()


#def Delete(*args, **kwargs):
#    return delete(*args, **kwargs)
#
#def Delete2(*args, **kwargs):
#    return delete(*args, **kwargs)
#    
#def delete3(*args, **kwargs):
#    return delete(*args, **kwargs)
#
#def delete4(*args, **kwargs):
#    return delete(*args, **kwargs)
#
#def delete5(*args, **kwargs):
#    return delete(*args, **kwargs)
