from numpy import tile, isnan, array, atleast_1d, asarray, logical_and, all, logical_or, any, nan, isinf, \
arange, vstack, inf, where, logical_not, take, argmax, argmin, abs, hstack, empty, insert, isfinite, append, atleast_2d, \
prod, sqrt, int32, int64, log2, log
from FuncDesigner import ooPoint
from interalgT import *

try:
    from bottleneck import nanargmin, nanmin, nanargmax, nanmax
except ImportError:
    from numpy import nanmin, nanargmin, nanargmax, nanmax
    
def func10(y, e, vv):
    m, n = y.shape
    LB = [[] for i in range(n)]
    UB = [[] for i in range(n)]

    r4 = (y + e) / 2
    
    # TODO: remove the cycle
    #T1, T2 = tile(y, (2*n,1)), tile(e, (2*n,1))
    
    for i in range(n):
        t1, t2 = tile(y[:, i], 2*n), tile(e[:, i], 2*n)
        #t1, t2 = T1[:, i], T2[:, i]
        #T1[(n+i)*m:(n+i+1)*m, i] = T2[i*m:(i+1)*m, i] = r4[:, i]
        t1[(n+i)*m:(n+i+1)*m] = t2[i*m:(i+1)*m] = r4[:, i]
        
        if vv[i].domain is bool:
            indINQ = y[:, i] != e[:, i]
            tmp = t1[(n+i)*m:(n+i+1)*m]
            tmp[indINQ] = 1
            tmp = t2[i*m:(i+1)*m]
            tmp[indINQ] = 0
            
#        if vv[i].domain is bool:
#            t1[(n+i)*m:(n+i+1)*m] = 1
#            t2[i*m:(i+1)*m] = 0
#        else:
#            t1[(n+i)*m:(n+i+1)*m] = t2[i*m:(i+1)*m] = r4[:, i]
        
        LB[i], UB[i] = t1, t2


####        LB[i], UB[i] = T1[:, i], T2[:, i]

#    sh1, sh2, inds = [], [], []
#    for i in range(n):
#        sh1+= arange((n+i)*m, (n+i+1)*m).tolist()
#        inds +=  [i]*m
#        sh2 += arange(i*m, (i+1)*m).tolist()

#    sh1, sh2, inds = asdf(m, n)
#    asdf2(T1, T2, r4, sh1, sh2, inds)
    
    #domain = dict([(v, (T1[:, i], T2[:, i])) for i, v in enumerate(vv)])
    domain = dict([(v, (LB[i], UB[i])) for i, v in enumerate(vv)])
    
    domain = ooPoint(domain, skipArrayCast = True)
    domain.isMultiPoint = True
    return domain

def func8(domain, func, dataType):
    TMP = func.interval(domain, dataType)
    #assert TMP.lb.dtype == dataType
    return asarray(TMP.lb, dtype=dataType), asarray(TMP.ub, dtype=dataType)

def getr4Values(vv, y, e, tnlh, func, C, contol, dataType):
    n = y.shape[1]
    # TODO: rework it wrt nlh
    #cs = dict([(key, asarray((val[0]+val[1])/2, dataType)) for key, val in domain.items()])
    if tnlh is None:
        cs = dict([(oovar, asarray((y[:, i]+e[:, i])/2, dataType)) for i, oovar in enumerate(vv)])
    else:
        tnlh = tnlh.copy()
        tnlh[tnlh==0] = 1e-300
        tnlh[atleast_1d(isnan(tnlh))] = inf #- check it!
        tnlh_l_inv, tnlh_u_inv = 1.0 / tnlh[:, :n], 1.0 / tnlh[:, n:]
        wr4 = (y * tnlh_l_inv + e * tnlh_u_inv) / (tnlh_l_inv + tnlh_u_inv)
        ind = tnlh_l_inv == tnlh_u_inv # especially important for tnlh_l_inv == tnlh_u_inv = 0
        wr4[ind] = (y[ind] + e[ind]) / 2
        #tmp = y + (e-y) * (tnlh_u_inv-tnlh_l_inv) / (tnlh_l_inv + tnlh_u_inv)
        #assert all(y <= wr4+1e-10) and all(wr4 <= e+1e-10)
        cs = dict([(oovar, asarray(wr4[:, i], dataType)) for i, oovar in enumerate(vv)])
        
        #OLD
        cs = dict([(oovar, asarray((y[:, i]+e[:, i])/2, dataType)) for i, oovar in enumerate(vv)])
        wr4 = (y + e) / 2

        
    cs = ooPoint(cs, skipArrayCast = True)
    cs.isMultiPoint = True
    
    # TODO: improve it
    #V = domain.values()
    #m = V[0][0].size if type(V) == list else next(iter(V))[0].size
    m = y.shape[0]
    if len(C) != 0:
        r15 = empty(m, bool)
        r15.fill(True)
        for f, r16, r17 in C:
            c = f(cs)
            ind = logical_and(c  >= r16, c <= r17) # here r16 and r17 are already shifted by required tolerance
            r15 = logical_and(r15, ind)
    else:
        r15 = True
    if not any(r15):
        F = empty(m, dataType)
        F.fill(2**31-2 if dataType in (int32, int64, int) else nan) 
    elif all(r15):
        F = func(cs)
    else:
        cs = dict([(oovar, (y[r15, i] + e[r15, i])/2) for i, oovar in enumerate(vv)])
        cs = ooPoint(cs, skipArrayCast = True)
        cs.isMultiPoint = True
        tmp = func(cs)
        F = empty(m, dataType)
        #F.fill(nanmax(tmp)+1) 
        F.fill(2**31-15 if dataType in (int32, int64, int) else nan)
        F[r15] = tmp
    return atleast_1d(F), ((y+e) / 2 if tnlh is None else wr4)

def r2(PointVals, PointCoords, dataType):
    r23 = nanargmin(PointVals)
    if isnan(r23):
        r23 = 0
    # TODO: check it , maybe it can be improved
    #bestCenter = cs[r23]
    #r7 = array([(val[0][r23]+val[1][r23]) / 2 for val in domain.values()], dtype=dataType)
    #r8 = atleast_1d(r3)[r23] if not isnan(r23) else inf
    r7 = array(PointCoords[r23], dtype=dataType)
    r8 = atleast_1d(PointVals)[r23] 
    return r7, r8
    
def func3(an, maxActiveNodes):
    m = len(an)
    if m > maxActiveNodes:
        an1, _in = an[:maxActiveNodes], an[maxActiveNodes:]
    else:
        an1, _in = an, array([], object)
    return an1, _in

def func1(tnlhf, tnlhf_curr, y, e, o, a, _s_prev, p, Case, r9 = None):
    m, n = y.shape
    w = arange(m)

    if Case != 'IP':
        if p.solver.dataHandling == 'sorted':
            _s = func13(o, a, Case)
            t = nanargmin(a, 1) % n
            d = nanmax([a[w, t] - o[w, t], 
                    a[w, n+t] - o[w, n+t]], 0)
            
            ## !!!! Don't replace it by (_s_prev /d- 1) to omit rounding errors ###
            #ind = 2**(-n) >= (_s_prev - d)/asarray(d, 'float64')
            
            #NEW
            ind = d  >= 2 ** (1/n) * _s_prev
            ###################################################
        elif p.solver.dataHandling == 'raw':
            tnlh_1, tnlh_2 = tnlhf[:, 0:n], tnlhf[:, n:]
            PointCoordsTNHLF_max =  where(logical_or(tnlh_1 < tnlh_2, isnan(tnlh_1)), tnlh_2, tnlh_1)
            TNHLF_min =  where(logical_or(tnlh_1 > tnlh_2, isnan(tnlh_1)), tnlh_2, tnlh_1)
            _s = nanmin(TNHLF_min, 1)
            
            tnlh_curr_1, tnlh_curr_2 = tnlhf_curr[:, 0:n], tnlhf_curr[:, n:]
            TNHL_curr_min =  where(logical_or(tnlh_curr_1 < tnlh_curr_2, isnan(tnlh_curr_2)), tnlh_curr_1, tnlh_curr_2)
            #1
            t = nanargmin(TNHL_curr_min, 1)
            
            
            #2
            #t = nanargmin(tnlhf, 1) % n
            #3
            #t = nanargmin(a, 1) % n
            
            d = nanmin(vstack(([tnlhf[w, t], tnlhf[w, n+t]])), 0)
            
            #OLD
            #!#!#!#! Don't replace it by _s_prev - d <= ... to omit inf-inf = nan !#!#!#
            #ind = _s_prev  <= d + ((2**-n / log(2)) if n > 15 else log2(1+2**-n)) 
            #ind = _s_prev - d <= ((2**-n / log(2)) if n > 15 else log2(1+2**-n)) 
            
            #NEW
            ind = _s_prev  <= d + 1.0/n
            
            #print _s_prev - d
            ###################################################
            #d = ((tnlh[w, t]* tnlh[w, n+t])**0.5)
        else:
            assert 0
    else:
        tmp = a[:, 0:n]-o[:, 0:n]+a[:, n:]-o[:, n:]
        _s = nanmax(tmp, 1)
        t = nanargmin(tmp,1)
        d = tmp[w, t]
        ind = 2**(-n) >= (_s_prev - d)/asarray(d, 'float64')
    
    #ind = d * (1.0 + max((1e-15, 2 ** (-n)))) >= _s_prev
    
    if r9 is not None:
        ind = logical_or(ind, r9)
    if any(ind):
        #print('ind length: %d' % len(where(ind)[0]))
        bs = e[ind] - y[ind]
        t[ind] = nanargmax(bs, 1) # ordinary numpy.argmax can be used as well
        
    return t, _s
    
def func13(o, a, case = 2): 
    m, n = o.shape
    n /= 2
    if case == 1:
        U1, U2 = a[:, :n].copy(), a[:, n:] 
        #TODO: mb use nanmax(concatenate((U1,U2),3),3) instead?
        U1 = where(logical_or(U1<U2, isnan(U1)),  U2, U1)
        return nanmin(U1, 1)
        
    L1, L2, U1, U2 = o[:, :n], o[:, n:], a[:, :n], a[:, n:] 
    if case == 2:
        U = where(logical_or(U1<U2, isnan(U1)),  U2, U1)
        L = where(logical_or(L2<L1, isnan(L1)), L2, L1)
        return nanmax(U-L, 1)
#    elif case == 'IP': # IP
#        return nanmax(U1-L1+U2-L2, 1)
    else: 
        raise('bug in interalg kernel')

def func2(y, e, t, vv):
    new_y, en = y.copy(), e.copy()
    m, n = y.shape
    w = arange(m)
    
    # TODO: omit or imporove it for all-float problems    
    th = (new_y[w, t] + en[w, t]) / 2
    BoolVars = [v.domain is bool for v in vv]
    if any(BoolVars):
        indBool = where(BoolVars)[0]
        if len(indBool) != n:
            new_y[w, t] = th
            en[w, t] = th
            new_y[indBool, t] = 1
            en[indBool, t] = 0
        else:
            new_y[w, t] = 1
            en[w, t] = 0
    else:
        new_y[w, t] = th
        en[w, t] = th
    
    new_y = vstack((y, new_y))
    en = vstack((en, e))
    
    return new_y, en


def func12(an, maxActiveNodes, p, solutions, r6, vv, varTols, fo, Case):
    if len(an) == 0:
        return array([]), array([]), array([]), array([])
    _in = an
    if r6.size != 0:
        r11, r12 = r6 - varTols, r6 + varTols
    y, e, S = [], [], []
    N = 0
    maxSolutions = p.maxSolutions
    
    while True:
        an1Candidates, _in = func3(_in, maxActiveNodes)

        yc, ec, oc, ac, SIc = asarray([t.y for t in an1Candidates]), \
        asarray([t.e for t in an1Candidates]), \
        asarray([t.o for t in an1Candidates]), \
        asarray([t.a for t in an1Candidates]), \
        asarray([t._s for t in an1Candidates])
        
        
        
        tnlhf = asarray([t.tnlhf for t in an1Candidates]) if p.solver.dataHandling == 'raw' else None
        tnlhf_curr = asarray([t.tnlh_curr for t in an1Candidates]) if p.solver.dataHandling == 'raw' else None
        
        if p.probType != 'IP': 
            nlhc = asarray([t.nlhc for t in an1Candidates])
            yc, ec = func4(yc, ec, oc, ac, nlhc, fo)
        t, _s = func1(tnlhf, tnlhf_curr, yc, ec, oc, ac, SIc, p, Case)
        yc, ec = func2(yc, ec, t, vv)
        _s = tile(_s, 2)
        
        if maxSolutions == 1 or len(solutions) == 0: 
            y, e = yc, ec
            break
        
        # TODO: change cycle variable if len(solutions) >> maxActiveNodes
        for i in range(len(solutions)):
            ind = logical_and(all(yc >= r11[i], 1), all(ec <= r12[i], 1))
            if any(ind):
                j = where(logical_not(ind))[0]
                lj = j.size
                yc = take(yc, j, axis=0, out=yc[:lj])
                ec = take(ec, j, axis=0, out=ec[:lj])
                _s = _s[j]
        y.append(yc)
        e.append(ec)
        S.append(_s)
        N += yc.shape[0]
        if len(_in) == 0 or N >= maxActiveNodes: 
            y, e, _s = vstack(y), vstack(e), hstack(S)
            break
        
    return y, e, _in, _s

Fields = ['key', 'y', 'e', 'nlhf','nlhc', 'o', 'a', '_s']
#FuncValFields = ['key', 'y', 'e', 'nlhf','nlhc', 'o', 'a', '_s','r18', 'r19']
IP_fields = ['key', 'y', 'e', 'o', 'a', '_s','F', 'volume', 'volumeResidual']

def func11(y, e, nlhc, o, a, _s, p): 
    m, n = y.shape
    if p.probType == "IP":
        w = arange(m)
        # TODO: omit recalculation from func1
        ind = nanargmin(a[:, 0:n] - o[:, 0:n] + a[:, n:] - o[:, n:], 1)
        sup_inf_diff = a[w, ind] - o[w, ind] + a[w, n+ind] - o[w, n+ind]
        
        # DEBUG
        #tmp3 = nanmin(a[:, 0:n]-o[:, 0:n]+a[:, n:]-o[:, n:],1)
        #assert all(tmp2==tmp3)
        
        volume = prod(e-y, 1)
        volumeResidual = volume * sup_inf_diff
#        initVolumeResidual = volume * 

    else:
        o_modL, o_modU = o[:, 0:n], o[:, n:2*n]
        Tmp = nanmax(where(o_modU<o_modL, o_modU, o_modL), 1)
#        a_modL, a_modU = a[:, 0:n], a[:, n:2*n]
#        uu = nanmax(where(logical_or(a_modU>a_modL, isnan(a_modU)), a_modU, a_modL), 1)
#        ll = nanmin(where(logical_or(o_modU>o_modL, isnan(o_modU)), o_modL, o_modU), 1)
#        nlhf = log2(uu-ll)
        nlhf = log2(a-o)

    if p.probType == 'IP':
        F = 0.25 * (a[w, ind] + o[w, ind] + a[w, n+ind] + o[w, n+ind])
        return [si(IP_fields, sup_inf_diff[i], y[i], e[i], o[i], a[i], _s[i], F[i], volume[i], volumeResidual[i]) for i in range(m)]
    else:
        assert p.probType in ('GLP', 'NLP', 'NSP', 'SNLE', 'NLSP')
        return [si(Fields, Tmp[i], y[i], e[i], nlhf[i], nlhc[i] if nlhc is not None else None, o[i], a[i], _s[i]) for i in range(m)]
    
#    else:
#        r18, r19 = r3[:, :n], r3[:, n:]
#        return [si(FuncValFields, Tmp[i], y[i], e[i], nlhf[i], nlhc[i] if nlhc is not None else None, o[i], a[i], _s[i], r18[i], r19[i]) for i in range(m)]

class si:
    def __init__(self, fields, *args, **kwargs):
        for i in range(len(fields)):
            setattr(self, fields[i], args[i])
    
