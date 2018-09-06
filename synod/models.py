import batman
import numpy as np
from . import bliss
from . import utils
from . import krdata as kr
from statsmodels.robust import scale
import matplotlib.pyplot as plt
import numpy.linalg as linear
# Global constants.
y,x = 0,1
ppm = 1e6
day_to_seconds = 86400
zero = 0.0

def transit_model_func(model_params, times, init_t0=0.0, ldtype='quadratic', transitType='primary'):
    """
        Args:
            model_params: Parameters() object with orbital properties for a given exoplanet.
            times: array of dates in units of days utilized for the photometry time series.
            init_t0: transit center time.
            ldtype: transit model type.
            transitType: 'primary' for transit, 'secondary' for eclipse.
        Returns:
            The Dark Knight phase curve model.
    """
    # Transit Parameters
    u1 = model_params['u1'].value
    u2 = model_params['u2'].value

    bm_params = batman.TransitParams() # object to store transit parameters
    
    if 'edepth' in model_params.keys() and model_params['edepth'] > 0:
        bm_params.t_secondary = model_params['deltaTc'] + init_t0 + 0.5*model_params['period'] + model_params['deltaEc']
        # model_params['period']*delta_phase
    else:
        model_params.add('edepth', 0.0, False)
    
    rprs = np.sqrt(model_params['tdepth'].value)
    bm_params.per = model_params['period'].value            # orbital period
    bm_params.t0 = model_params['deltaTc'].value + init_t0  # time of inferior conjunction
    bm_params.inc = model_params['inc'].value               # inclunaition in degrees
    bm_params.a = model_params['aprs'].value                # semi-major axis (in units of stellar radii)
    bm_params.rp = rprs                                     # planet radius (in units of stellar radii)
    bm_params.fp = model_params['edepth'].value             # planet radius (in units of stellar radii)
    bm_params.ecc = model_params['ecc'].value               # eccentricity
    bm_params.w = model_params['omega'].value               # longitude of periastron (in degrees)
    bm_params.limb_dark = ldtype                            # limb darkening model # NEED TO FIX THIS
    bm_params.u = [u1, u2]                                  # limb darkening coefficients # NEED TO FIX THIS
    m_eclipse = batman.TransitModel(bm_params, times, transittype=transitType) # initializes model
    
    # oot_offset = model_params['night_flux'].value if transitType.lower() == 'secondary' else 0.0
    # print(transitType, oot_offset)
    return m_eclipse.light_curve(bm_params)# + oot_offset

def line_model_func_multi(model_params, ntransits, transit_indices, times):
    intercepts = []
    coeffs_line_list = []
    
    for k in range(ntransits):
        intercepts.append(model_params['intcept{}'.format(k)] if 'intcept{}'.format(k) in model_params.keys() else 1.0 )
        slope = model_params['slope{}'.format(k)] if 'slope{}'.format(k) in model_params.keys() else 0.0
        crvtur = model_params['crvtur{}'.format(k)] if 'crvtur{}'.format(k) in model_params.keys() else 0.0
        coeffs_line_list.append([slope, crvtur])
    
    total_line = []
    for ki, intcpt in enumerate(intercepts):
        times_now = times[transit_indices[ki][0]:transit_indices[ki][1]]
        times_now = times_now - times_now.mean()
        # Flat line
        line_model = np.array([intcpt for x in np.zeros(len(times_now))])
        # slope * [times-shift] + curvatue * [times-shift]**2
        for kc,c_now in enumerate(coeffs_line_list[ki]):
            if c_now != zero:
                slant = float(c_now)*(times_now-times_now.mean())**(kc+1)
                
            else:
                slant = 0*times_now
        line_model = line_model + slant

        total_line = total_line + list(line_model)

    return np.array(total_line)

def line_model_func(model_params, times):
    intercept = model_params['intercept'] if 'intercept' in model_params.keys() else 1.0
    slope = model_params['slope'] if 'slope' in model_params.keys() else 0.0
    curvature = model_params['curvature'] if 'curvature' in model_params.keys() else 0.0
    
    line_model = intercept
    line_model = line_model + slope*(times-times.mean()) if slope is not 0.0 else line_model
    line_model = line_model + curvature*(times-times.mean())**2 if curvature is not 0.0 else line_model
    
    return line_model

def phase_curve_func(model_params, times, init_t0):
    
    if 'period' not in model_params.keys(): raise Exception('`period` not included in `model_params`')
    
    if 'deltaTc' in model_params.keys() and 'deltaEc' in model_params.keys():
        t_secondary = init_t0 + model_params['deltaTc'] + 0.5*model_params['period'] + model_params['deltaEc']
    else:
        t_secondary = init_t0 + 0.5*model_params['period']
    
    ang_freq = 2*np.pi / model_params['period']
    if 'cosPhase' in model_params.keys() and 'cosAmp' in model_params.keys():
        half = 0.5 # necessary because the "amplitude" of a cosine is HALF the "amplitude"" of the phase curve
        phase_curve = half*model_params['cosAmp']*np.cos(ang_freq * (times - t_secondary) + model_params['cosPhase'])
    elif 'sinAmp' in model_params.keys() and 'cosAmp' in model_params.keys():
        phase_curve = model_params['cosAmp']*np.cos(ang_freq * (times - t_secondary)) + model_params['sinAmp']*np.sin(ang_freq * (times - t_secondary))
    elif 'sinAmp1' in model_params.keys() and 'cosAmp1' in model_params.keys():
        if 'sinAmp2' in model_params.keys() and 'cosAmp2' in model_params.keys():
            phase_curve = model_params['cosAmp1']*np.cos(ang_freq * (times - t_secondary)) + model_params['sinAmp1']*np.sin(ang_freq * (times - t_secondary)) + \
                   model_params['cosAmp2']*np.cos(2*ang_freq * (times - t_secondary)) + model_params['sinAmp2']*np.sin(2*ang_freq * (times - t_secondary))
        else:
            phase_curve = model_params['cosAmp1']*np.cos(ang_freq * (times - t_secondary)) + model_params['sinAmp1']*np.sin(ang_freq * (times - t_secondary))
    else:
        phase_curve = np.array(0)
    
    # The `+ 1.0 - phase_curve.min()` term is required because the "phase curve" minimizes to 1.0;
    #   but the cosine function minimizes at -cos_amplitude / 2
    # 
    # This form ensures that the minimum phase curve will always be exactly 1.0
    # print(model_params['night_flux'].value,model_params['edepth'].value, model_params['night_flux'].value/model_params['edepth'].value)
    
    return phase_curve + 1.0 - phase_curve.min() + model_params['night_flux'].value

def trapezoid_model(model_params, times, init_t0, include_transit = True, 
                        include_eclipse = True, include_phase_curve = True, 
                        include_polynomial = True, subtract_edepth = True, 
                        return_case = None):
    
    eclipse_model = transit_model_func(model_params, times, init_t0, transitType='secondary') if include_eclipse else 1.0
    
    ecl_bottom = eclipse_model == eclipse_model.min()
    in_eclipse = eclipse_model < eclipse_model.max()
    
    eclipse0 = in_eclipse * (times < times.mean())
    eclipse1 = in_eclipse * (times > times.mean())
    
    t1_0 = np.where(eclipse0)[0][0]
    t2_0 = np.where(eclipse0*ecl_bottom)[0][0]
    t3_0 = np.where(eclipse0*ecl_bottom)[0][-1]
    t4_0 = np.where(eclipse0)[0][-1]
    
    t1_1 = np.where(eclipse1)[0][0]
    t2_1 = np.where(eclipse1*ecl_bottom)[0][0]
    t3_1 = np.where(eclipse1*ecl_bottom)[0][-1]
    t4_1 = np.where(eclipse1)[0][-1]
    
    trap_model = np.ones(times.size) + model_params['edepth'].value
    
    y1 = 1.0 + model_params['edepth'].value
    y2 = 1 #- model_params['edepth'].value
    y3 = 1 #- model_params['edepth'].value
    y4 = 1.0 + model_params['edepth'].value
    
    x1_0 = times[t1_0]
    x2_0 = times[t2_0]
    x1_1 = times[t1_1]
    x2_1 = times[t2_1]
    x3_0 = times[t3_0]
    x4_0 = times[t4_0]
    x3_1 = times[t3_1]
    x4_1 = times[t4_1]    
    
    ingress_slope_0 = (y2 - y1) / (x2_0 - x1_0)
    ingress_slope_1 = (y2 - y1) / (x2_1 - x1_1)
    
    egress_slope_0 = (y3 - y4) / (x3_0 - x4_0)
    egress_slope_1 = (y3 - y4) / (x3_1 - x4_1)
    
    trap_model[t2_0:t3_0] = y2
    trap_model[t2_1:t3_1] = y2
    
    trap_model[t1_0:t2_0] = ingress_slope_0 * (times[t1_0:t2_0]-x2_0) + y2
    trap_model[t1_1:t2_1] = ingress_slope_1 * (times[t1_1:t2_1]-x2_1) + y2
    trap_model[t3_0:t4_0] = egress_slope_0 * (times[t3_0:t4_0]-x3_0) + y3
    trap_model[t3_1:t4_1] = egress_slope_1 * (times[t3_1:t4_1]-x3_1) + y3
    
    return trap_model

def compute_sensitivity_map(model_params, method, xcenters, ycenters, residuals, knots, nearIndices, xBinSize, yBinSize, ind_kdtree, gw_kdtree, pld_intensities, model):
    if method == 'bliss' :
        normFactor = (1/xBinSize) * (1/yBinSize)
        sensitivity_map = bliss.BLISS(xcenters, ycenters, residuals, knots, nearIndices, xBinSize=xBinSize, yBinSize=xBinSize, normFactor=normFactor)
    elif method == 'krdata':
        sensitivity_map  = np.sum(residuals[ind_kdtree]  * gw_kdtree, axis=1)
    elif method == 'pld':
        PLDcoeffs = sorted([val for key, val in model_params.items() if 'pld' in key.lower()])
        sensitivity_map = np.dot(PLDcoeffs, pld_intensities)
    else:
        print('INVALID METHOD: ABORT')
    
    nSig = 10
    vbad_sm = np.where(abs(sensitivity_map - np.median(sensitivity_map)) > nSig*scale.mad(sensitivity_map))[0]
    if len(sensitivity_map)-1 in vbad_sm:
        vbad_sm = list(set(vbad_sm) - set([len(sensitivity_map)-1]))
        end_corner_case = True
    else:
        end_corner_case = False
    if 0 in vbad_sm:
        vbad_sm = list(set(vbad_sm) - set([0]))
        start_corner_case = True
    else:
        start_corner_case = False

    vbad_sm = np.array(vbad_sm)
    sensitivity_map[vbad_sm] = 0.5*(sensitivity_map[vbad_sm-1] + sensitivity_map[vbad_sm+1])

    if end_corner_case: sensitivity_map[-1] = sensitivity_map[2]
    if start_corner_case: sensitivity_map[0] = sensitivity_map[1]

    return sensitivity_map

def add_line_params(model_params, phase, times, transitType='primary'):

    transit_phase = 0.1
    if transitType == 'primary':
        ph_transits = np.where(abs(phase) < transit_phase)[0]
    elif transitType == 'secondary':
        ph_transits = np.where(abs(phase-0.5) < transit_phase)[0]

    day_to_seconds = 86400
    ph_diff_times = np.diff(times[ph_transits] * day_to_seconds)
    med_ph_diff_times = np.median(ph_diff_times)
    std_ph_diff_times = np.std(ph_diff_times)

    nSig = 10
    ph_where_transits = np.where(abs(ph_diff_times) > nSig * std_ph_diff_times)[0]

    if len(ph_where_transits) == len(ph_transits) - 1 or ph_where_transits == []:
        print('There is probably only 1 transit in this data set')
        print('\tWe will store *only* the phase range equivalent to that single transit')
        ph_where_transits = [len(ph_transits) - 1]
        single_transit = True
    else:
        single_transit = False
    ntransits = len(ph_where_transits)
    print('Found {} transits'.format(ntransits))
    transit_indices = []
    idx_start = ph_transits[0]
    for kt in range(ntransits):
        idx_end = ph_transits[ph_where_transits[kt]]
        transit_indices.append([idx_start,idx_end+1])
        model_params.add_many(('intcept{}'.format(kt), 1.0, True))
        model_params.add_many(('slope{}'.format(kt), 0.0, True))
        model_params.add_many(('crvtur{}'.format(kt), 0.0, False))
        if not single_transit and idx_end != len(ph_transits) - 1:
            idx_start = ph_transits[ph_where_transits[kt] + 1]
        else:
            # CORNER CASE
            error_messages = {True: "There is probably only one eclipses in this data",
                              False: "The eclipse probably meets the end of the data"}

            print(error_messages[single_transit])

            ph_transits[-1]

    if not single_transit and idx_start != len(ph_transits) - 1:
        '''Catch the last ocurrence'''
        kt = kt + 1  #
        model_params.add_many(('intcept{}'.format(kt), 1.0, True))
        model_params.add_many(('slope{}'.format(kt), 0.0, True))
        model_params.add_many(('crvtur{}'.format(kt), 0.0, False))
        idx_end = ph_transits[-1]
        transit_indices.append([idx_start,idx_end+1])

    return model_params, transit_indices

def add_pld_params(model_params, fluxes, pld_intensities, n_pld = 9):
    pld_coeffs = np.linalg.lstsq(pld_intensities.T, fluxes)[0]
    print(pld_coeffs)
    for k in range(n_pld):
        model_params.add_many(('pld{}'.format(k), pld_coeffs[k], True))
    return model_params

## FROM KBS MODELS

def sincos(rampparams, t, etc = []):
   """
  This function creates a model that fits a sinusoid.

  Parameters
  ----------
    a/b:    amplitude
    p1/p2:    period
    t1/t2:  phase/time offset
    c:      vertical offset
    t:        Array of time/phase points

  Returns
  -------
    This function returns an array of y values...

  Revisions
  ---------
  2010-08-01    Kevin Stevenson, UCF 
                kevin218@knights.ucf.edu
                Original version
   """

   a     = rampparams[0]
   p1    = rampparams[1]
   t1    = rampparams[2]
   b     = rampparams[3]
   p2    = rampparams[4]
   t2    = rampparams[5]
   c     = rampparams[6]
   pi    = np.pi

   return ne.evaluate('a*sin(2*pi*(t-t1)/p1) + b*cos(2*pi*(t-t2)/p2) + c')

def sincos2(rampparams, t, etc = []):
    """
    This function creates a model that fits a sinusoid.

    Parameters
    ----------
    c#a/s#a     : amplitude
    c#o/s#o     : phase/time offset
    p           : period
    c           : vertical offset
    t           : Array of time/phase points

    Returns
    -------
    This function returns an array of values.

    Revisions
    ---------
    2013-11-22    Kevin Stevenson 
                kbs@uchicago.edu
                Modified from sincos.py
    """

    c1a   = rampparams[0]
    c1o   = rampparams[1]
    c2a   = rampparams[2]
    c2o   = rampparams[3]
    s1a   = rampparams[4]
    s1o   = rampparams[5]
    s2a   = rampparams[6]
    s2o   = rampparams[7]
    p     = rampparams[8]
    c     = rampparams[9]
    midpt = rampparams[10]
    t14   = rampparams[11]
    t12   = rampparams[12]
    pi    = np.pi
    
    flux = ne.evaluate('c1a*cos(2*pi*(t-c1o)/p) + c2a*cos(4*pi*(t-c2o)/p) + s1a*sin(2*pi*(t-s1o)/p) + s2a*sin(4*pi*(t-s2o)/p) + c')
    
    #Flatten sin/cos during eclipse
    iecl = np.where(np.bitwise_or((t-midpt)%p >= p-(t14-t12)/2.,(t-midpt)%p <= (t14-t12)/2.))
    #print(iecl)
    #flux[iecl] = np.mean(flux[iecl])
    flux[iecl] = c1a*np.cos(2*pi*(midpt-c1o)/p) + c2a*np.cos(4*pi*(midpt-c2o)/p) + s1a*np.sin(2*pi*(midpt-s1o)/p) + s2a*np.sin(4*pi*(midpt-s2o)/p) + c
    
    return flux