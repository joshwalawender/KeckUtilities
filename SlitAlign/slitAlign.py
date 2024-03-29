#!/usr/env/python

## Import General Tools
import sys
import os
import argparse
import logging

from matplotlib import pyplot as plt

from scipy import ndimage

import numpy as np
from astropy.io import fits
from astropy import units as u
from astropy.modeling import models, fitting, Fittable2DModel, Parameter
from astropy.table import Table
from ccdproc import CCDData, combine, Combiner, flat_correct, trim_image, median_filter


##-------------------------------------------------------------------------
## Create logger object
##-------------------------------------------------------------------------
log = logging.getLogger('MyLogger')
log.setLevel(logging.DEBUG)
## Set up console output
LogConsoleHandler = logging.StreamHandler()
LogConsoleHandler.setLevel(logging.DEBUG)
LogFormat = logging.Formatter('%(asctime)s %(levelname)8s: %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')
LogConsoleHandler.setFormatter(LogFormat)
log.addHandler(LogConsoleHandler)
## Set up file output
# LogFileName = None
# LogFileHandler = logging.FileHandler(LogFileName)
# LogFileHandler.setLevel(logging.DEBUG)
# LogFileHandler.setFormatter(LogFormat)
# log.addHandler(LogFileHandler)

##-------------------------------------------------------------------------
## mosfireAlignmentBox
##-------------------------------------------------------------------------
class mosfireAlignmentBox(Fittable2DModel):
    amplitude = Parameter(default=1)
    x_0 = Parameter(default=0)
    y_0 = Parameter(default=0)
    x_width = Parameter(default=1)
    y_width = Parameter(default=1)

    @staticmethod
    def evaluate(x, y, amplitude, x_0, y_0, x_width, y_width):
        '''MOSFIRE Alignment Box.
        
        Typical widths are 22.5 pix horizontally and 36.0 pix vertically.
        
        Angle of slit relative to pixels is 3.78 degrees.
        '''
        slit_angle = -3.7 # in degrees
        x0_of_y = x_0 + (y-y_0)*np.sin(slit_angle*np.pi/180)
        
        x_range = np.logical_and(x >= x0_of_y - x_width / 2.,
                                 x <= x0_of_y + x_width / 2.)
        y_range = np.logical_and(y >= y_0 - y_width / 2.,
                                 y <= y_0 + y_width / 2.)
        result = np.select([np.logical_and(x_range, y_range)], [amplitude], 0)

        if isinstance(amplitude, u.Quantity):
            return Quantity(result, unit=amplitude.unit, copy=False)
        else:
            return result

    @property
    def input_units(self):
        if self.x_0.unit is None:
            return None
        else:
            return {'x': self.x_0.unit,
                    'y': self.y_0.unit}

    def _parameter_units_for_data_units(self, inputs_unit, outputs_unit):
        return OrderedDict([('x_0', inputs_unit['x']),
                            ('y_0', inputs_unit['y']),
                            ('x_width', inputs_unit['x']),
                            ('y_width', inputs_unit['y']),
                            ('amplitude', outputs_unit['z'])])


##-------------------------------------------------------------------------
## Transformations (copied from CSU initializer code)
##-------------------------------------------------------------------------
def pad(x):
    '''Pad array for affine transformation.
    '''
    return np.hstack([x, np.ones((x.shape[0], 1))])


def unpad(x):
    '''Unpad array for affine transformation.
    '''
    return x[:,:-1]

def slit_to_bars(slit):
    '''Given a slit number (1-46), return the two bar numbers associated
    with that slit.
    '''
    return (slit*2-1, slit*2)

def bar_to_slit(bar):
    '''Given a bar number, retun the slit associated with that bar.
    '''
    return int((bar+1)/2)

def pixel_to_physical(x):
    '''Using the affine transformation determined by `fit_transforms`,
    convert a set of pixel coordinates (X, Y) to physical coordinates (mm,
    slit).
    '''
    Apixel_to_physical = [[ -1.30490576e-01,  8.06611058e-05, 0.00000000e+00],
                          [ -4.19125389e-04, -2.25757176e-02, 0.00000000e+00],
                          [  2.73934450e+02,  4.66399772e+01, 1.00000000e+00]]
    x = np.array(x)
    result = unpad(np.dot(pad(x), Apixel_to_physical))
    return result


def physical_to_pixel(x):
    '''Using the affine transformation determined by `fit_transforms`,
    convert a set of physical coordinates (mm, slit) to pixel coordinates
    (X, Y).
    '''
    Aphysical_to_pixel = [[ -7.66328913e+00, -2.73804045e-02, 0.00000000e+00],
                          [  1.42268848e-01, -4.42948641e+01, 0.00000000e+00],
                          [  2.09260502e+03,  2.07341206e+03, 1.00000000e+00]]
    x = np.array(x)
    result = unpad(np.dot(pad(x), Aphysical_to_pixel))
    return result


def fit_transforms(pixels, targets):
    '''Given a set of pixel coordinates (X, Y) and a set of target
    coordinates (X, Y), fit the affine transformations (forward and
    backward) to convert between the two coordinate systems.
    
    '''
    if type(pixels) == list:
        pixels = np.array(pixels)
    if type(targets) == list:
        targets = np.array(targets)
    assert pixels.shape[1] == 2
    assert targets.shape[1] == 2
    assert pixels.shape[0] == targets.shape[0]

    # Pad the data with ones, so that our transformation can do translations too
    n = pixels.shape[0]
    pad = lambda x: np.hstack([x, np.ones((x.shape[0], 1))])
    unpad = lambda x: x[:,:-1]
    X = pad(pixels)
    Y = pad(targets)

    # Solve the least squares problem X * A = Y
    # to find our transformation matrix A
    A, res, rank, s = np.linalg.lstsq(X, Y, rcond=None)
    A[np.abs(A) < 1e-10] = 0

    # Check Scale
    thetas = np.array([np.arcsin(A[0,1])*180/np.pi, np.arcsin(A[1,0])*-180/np.pi])
    thetadiff = np.abs(thetas[0] - thetas[1])
    Sx = A[0,0]/np.cos(np.mean(thetas)*np.pi/180)
    Sy = A[1,1]/np.cos(np.mean(thetas)*np.pi/180)

    print(f"Scale Factor: {Sx:.4f}, {Sy:.4f}")
    off_X = -A[2,0]
    off_Y = -A[2,1]
    off_R = -np.mean(thetas)
    err_R = thetadiff/2

    return (off_X, off_Y, off_R, err_R, A)



##-------------------------------------------------------------------------
## Fit CSU Edges (copied from CSU initializer code)
##-------------------------------------------------------------------------
def fit_CSU_edges(profile):
    fitter = fitting.LevMarLSQFitter()

    amp1_est = profile[profile == min(profile)][0]
    mean1_est = np.argmin(profile)
    amp2_est = profile[profile == max(profile)][0]
    mean2_est = np.argmax(profile)
    
    g_init1 = models.Gaussian1D(amplitude=amp1_est, mean=mean1_est, stddev=2.)
    g_init1.amplitude.max = 0
    g_init1.amplitude.min = amp1_est*0.9
    g_init1.stddev.max = 3
    g_init2 = models.Gaussian1D(amplitude=amp2_est, mean=mean2_est, stddev=2.)
    g_init2.amplitude.min = 0
    g_init2.amplitude.min = amp2_est*0.9
    g_init2.stddev.max = 3

    model = g_init1 + g_init2
    fit = fitter(model, range(0,profile.shape[0]), profile)
    
    # Check Validity of Fit
    if abs(fit.stddev_0.value) <= 3 and abs(fit.stddev_1.value) <= 3\
       and fit.amplitude_0.value < -1 and fit.amplitude_1.value > 1\
       and fit.mean_0.value > fit.mean_1.value:
        x = [fit.mean_0.value, fit.mean_1.value]
        x1 = int(np.floor(min(x)-1))
        x2 = int(np.ceil(max(x)+1))
    else:
        x1 = None
        x2 = None

    return x1, x2


##-------------------------------------------------------------------------
## Create Master Flat
##-------------------------------------------------------------------------
def create_master_flat(filepath='../../../KeckData/MOSFIRE_FCS/',
                       flatfiles = ['m180130_0320.fits',
                                    'm180130_0321.fits',
                                    'm180130_0322.fits',
                                    'm180130_0323.fits',
                                    'm180130_0324.fits',],
                       darkfile = 'm180130_0001.fits',
                      ):
    dark = CCDData.read(os.path.join(filepath, darkfile), unit='adu')
    flats = []
    for i,file in enumerate(flatfiles):
        flat = CCDData.read(os.path.join(filepath, file), unit='adu')
        flat = flat.subtract(dark)
        flats.append(flat)

    flat_combiner = Combiner(flats)
    flat_combiner.sigma_clipping()
    scaling_func = lambda arr: 1/np.ma.average(arr)
    flat_combiner.scaling = scaling_func
    masterflat = flat_combiner.median_combine()

    masterflat.write('masterflat.fits', overwrite=True)


##-------------------------------------------------------------------------
## Reduce Image
##-------------------------------------------------------------------------
def reduce_image(imagefile, dark=None, flat=None):
    im = CCDData.read(imagefile, unit='adu')
    if dark is not None:
        dark = CCDData.read(dark, unit='adu')
        im = im.subtract(dark)
    if flat is not None:
#         masterflat = CCDData.read(flat, unit='adu')
        hdul = fits.open(flat)
        masterflat = CCDData(data=hdul[0].data, uncertainty=None, meta=hdul[0].header, unit='adu')
        im = flat_correct(im, masterflat)
    return im

#     im = fits.open(imagefile)
#     if dark is not None:
#         masterdark = fits.open(dark)
#         im[0].data -= masterdark[0].data
#     if flat is not None:
#         masterflat = fits.open(flat)
#         norm = np.nanmedian(masterflat[0].data)
#         im[0].data /= (masterflat[0].data / norm)
#     return im


##-------------------------------------------------------------------------
## fit_alignment_box
##-------------------------------------------------------------------------
def fit_alignment_box(region, box_size=30, verbose=False, seeing=None,
                      medfilt=False):
    pixelscale = u.pixel_scale(0.1798*u.arcsec/u.pixel)
    if medfilt is True:
        region = median_filter(region, size=(3,3))

    # Estimate center of alignment box
    threshold_pct = 80
    window = region.data > np.percentile(region.data, threshold_pct)
    alignment_box_position = ndimage.measurements.center_of_mass(window)

    offset_val = np.median(region.data[~window])
    offset = models.Const2D(offset_val)

    # Determine fluctuations in sky
    sky_amplitude = np.median(region.data[window])
    sky_fluctuations = np.std(region.data[window])

    # Detect box edges
    gradx = np.gradient(region.data, axis=1)
    horizontal_profile = np.sum(gradx, axis=0)
    h_edges = fit_CSU_edges(horizontal_profile)
    grady = np.gradient(region.data, axis=0)
    vertical_profile = np.sum(grady, axis=1)
    v_edges = fit_CSU_edges(vertical_profile)

    # Estimate stellar position
    maxr = np.max(region.data)
    starloc = (np.where(region == maxr)[0][0],
               np.where(region == maxr)[1][0])

    # Build model of sky, star, & box
    boxamplitude = 1

    box = mosfireAlignmentBox(boxamplitude, alignment_box_position[1], alignment_box_position[0],\
                       abs(h_edges[0]-h_edges[1]), abs(v_edges[0]-v_edges[1]))
    box.amplitude.fixed = True
    box.x_width.min = 10
    box.y_width.min = 10

    sky = models.Const2D(sky_amplitude)
    sky.amplitude.min = 0

    star_amplitude = maxr - sky_amplitude
    star_sigma = star_amplitude / sky_fluctuations
    if star_sigma < 5:
        if verbose: print(f'No star detected.  sigma={star_sigma:.1f}')
        return [None]*4
    else:
        if verbose: print(f'Detected peak pixel {star_sigma:.1f} sigma above sky.')
    star = models.Gaussian2D(amplitude=star_amplitude,
                             x_mean=starloc[1], y_mean=starloc[0],
                             x_stddev=2, y_stddev=2)
#     print(h_edges)
#     print(v_edges)
#     star.y_mean.min = v_edges[0]
#     star.y_mean.max = v_edges[1]
#     star.x_mean.min = h_edges[0]
#     star.x_mean.max = h_edges[1]
    star.amplitude.min = 5*sky_fluctuations
    star.x_stddev.min = 1 # FWHM = 2.355*stddev = 0.42 arcsec FWHM
    star.x_stddev.max = 4 # FWHM = 2.355*stddev = 1.47 arcsec FWHM
    star.y_stddev.min = 1
    star.y_stddev.max = 4

    if seeing is not None and seeing > 0:
        sigma = (seeing / 2.355 * u.arcsec).to(u.pixel, equivalencies=pixelscale)
        star.x_stddev.min = max(2, sigma.value-1)
        star.y_stddev.min = max(2, sigma.value-1)
        star.x_stddev.max = min(sigma.value+1, 4)
        star.y_stddev.max = min(sigma.value+1, 4)
#         print(f"Using seeing value {seeing} arcsec. sigma limits {star.x_stddev.min}, {star.x_stddev.max} pix")

    model = box*(sky + star) + offset

#     modelim = np.zeros((61,61))
#     fitim = np.zeros((61,61))
#     for i in range(0,60):
#         for j in range(0,60):
#             modelim[j,i] = model(i,j)
#             fitim[j,i] = model(i,j)
#     residuals = region.data-fitim
#     residualsum = np.sum(residuals)
#     import pdb ; pdb.set_trace()

    fitter = fitting.LevMarLSQFitter()
    y, x = np.mgrid[:2*box_size+1, :2*box_size+1]
    fit = fitter(model, x, y, region.data)

    FWHMx = 2*(2*np.log(2))**0.5*fit.x_stddev_2.value * u.pix
    FWHMy = 2*(2*np.log(2))**0.5*fit.y_stddev_2.value * u.pix
    FWHM = (FWHMx**2 + FWHMy**2)**0.5/2**0.5
    FWHMarcsec = FWHM.to(u.arcsec, equivalencies=pixelscale)
    sky_amplitude = fit.amplitude_1.value
    star_flux = 2*np.pi*fit.amplitude_2.value*fit.x_stddev_2.value*fit.y_stddev_2.value
    star_amplitude = fit.amplitude_2.value
    boxpos_x = fit.x_0_0.value
    boxpos_y = fit.y_0_0.value
    star_x = fit.x_mean_2.value
    star_y = fit.y_mean_2.value

    if verbose: print(f"  Box X Center = {boxpos_x:.0f}")
    if verbose: print(f"  Box Y Center = {boxpos_y:.0f}")
    if verbose: print(f"  Sky Brightness = {fit.amplitude_1.value:.0f} ADU")
    if verbose: print(f"  Stellar FWHM = {FWHMarcsec:.2f}")
    if verbose: print(f"  Stellar Xpos = {star_x:.0f}")
    if verbose: print(f"  Stellar Xpos = {star_y:.0f}")
    if verbose: print(f"  Stellar Amplitude = {star_amplitude:.0f} ADU")
    if verbose: print(f"  Stellar Flux (fit) = {star_flux:.0f} ADU")

    result = {'Star X': star_x,
              'Star Y': star_y,
              'Star Amplitude': star_amplitude,
              'Sky Amplitude': sky_amplitude,
              'FWHM pix': FWHM.value,
              'FWHM arcsec': FWHMarcsec,
              'Box X': boxpos_x,
              'Box Y': boxpos_y,
#               'Residuals': residuals,
             }
    return result


def analyze_image(imagefile, dark=None, flat=None, box_size=30, medfilt=False,
                  plot=False, seeing=0, pixelscale=0.1798, verbose=False):
    im = reduce_image(imagefile, dark=dark, flat=flat)
    hdul = fits.open(imagefile)

    # Get info about alignment box positions
    alignment_box_table = Table(hdul[4].data)

    if plot == True:
        plt.figure(figsize=(16,6))

    pixels = []
    targets = []
    for i,box in enumerate(alignment_box_table):
        result = None
        slitno = int(box['Slit_Number'])
        bar_nos = slit_to_bars(slitno)
        bar_pos = [hdul[0].header.get(f'B{b:02d}POS') for b in bar_nos]
        box_pos = np.mean(bar_pos)
        box_pix = physical_to_pixel([[box_pos, slitno]])[0]
        boxat = [int(box_pix[0]), int(box_pix[1])]
        fits_section = f'[{boxat[0]-box_size:d}:{boxat[0]+box_size:d}, '\
                       f'{boxat[1]-box_size:d}:{boxat[1]+box_size:d}]'
        region = trim_image(im, fits_section=fits_section)

        targ_pos = float(box['Target_to_center_of_slit_distance'])/pixelscale

        if plot == True:
            plt.subplot(1,len(alignment_box_table),i+1, aspect='equal')
            plt.title(f"Alignment Box {i+1}\n{fits_section}")
            plt.imshow(region.data, origin='lower',
                       vmin=np.percentile(region.data, 85)*0.95,
                       vmax=region.data.max()*1.02)

#         try:
        result = fit_alignment_box(region, box_size=box_size, verbose=False,
                                   seeing=seeing, medfilt=medfilt)
        star_pix = np.array([result['Star X']+boxat[0]-box_size,
                             result['Star Y']+boxat[1]-box_size])
        fitted_box_pix = np.array([result['Box X']+boxat[0]-box_size,
                                   result['Box Y']+boxat[1]-box_size])
        slitang = 0.22*np.pi/180
        targ_pix_im = (result['Box X']-np.sin(slitang)*targ_pos,
                       result['Box Y']+np.cos(slitang)*targ_pos)
        targ_pix = np.array([targ_pix_im[0]+boxat[0]-box_size,
                             targ_pix_im[1]+boxat[1]-box_size])
        pixels.append(list(star_pix))
        targets.append(list(targ_pix))
        pix_err = targ_pix - star_pix
        pos_err = pix_err*pixelscale

        if plot == True:
            cxy = (result['Star X'], result['Star Y'])
            c = plt.Circle(cxy, result['FWHM pix'], linewidth=2, ec='g', fc='none', alpha=0.3)
            ax = plt.gca()
            ax.add_artist(c)
            plt.plot(result['Star X'], result['Star Y'], 'g.')
#             plt.plot(result['Box X'], result['Box Y'], 'y+', alpha=0.5, ms=10)
            plt.plot(targ_pix_im[0], targ_pix_im[1], 'rx', alpha=0.5)

        if verbose:
            print(f"Alignment Box {i+1} results:")
            print(f"  Sky Amplitude: {result['Sky Amplitude']:.0f} ADU")
            print(f"  Star Amplitude: {result['Star Amplitude']:.0f} ADU")
            print(f"  Star FWHM: {result['FWHM arcsec']:.2f}")
            print(f"  Star Position: {star_pix[0]:.1f}, {star_pix[1]:.1f}")
            print(f"  Target Position: {targ_pix[0]:.1f}, {targ_pix[1]:.1f}")
            print(f"  Position Error: {pos_err[0]:+.2f}, {pos_err[1]:+.2f} arcsec")
#         except:
#             print(f'Alignment Box {i+1} failed: {result}')

        if plot == True:
            plt.xticks([], [])
            plt.yticks([], [])

    # Calculate Transformation
    off_Xpix, off_Ypix, off_R, err_R, A = fit_transforms(pixels, targets)

    off_X = off_Xpix * pixelscale
    off_Y = off_Ypix * pixelscale
    th_XY = 0.10
    th_R = 0.030
    send_X = off_X if abs(off_X) > th_XY else 0
    send_Y = off_Y if abs(off_Y) > th_XY else 0
    send_R = off_R if abs(off_R) > th_R else 0
    print()
    print(f"       Calculated   Err  Send        (Threshold)")
    print(f"Offset X =  {off_X:+.2f}       {send_X:+.2f} arcsec ({th_XY:.2f})")
    print(f"Offset Y =  {off_Y:+.2f}       {send_Y:+.2f} arcsec ({th_XY:.2f})")
    print(f"Rotation = {off_R:+.3f} {err_R:.3f} {send_R:+.3f} deg   ({th_R:.3f})")

    if plot == True:
        plt.show()


if __name__ == '__main__':
    ##-------------------------------------------------------------------------
    ## Parse Command Line Arguments
    ##-------------------------------------------------------------------------
    ## create a parser object for understanding command-line arguments
    p = argparse.ArgumentParser(description='''
    ''')
    ## add flags
    p.add_argument("-v", "--verbose", dest="verbose",
        default=False, action="store_true",
        help="Be verbose! (default = False)")
    p.add_argument("-m", "--medfilt", dest="medfilt",
        default=False, action="store_true",
        help="Median filter images?")
    p.add_argument("-p", "--plot", dest="plot",
        default=False, action="store_true",
        help="Generate plots?")
    ## add options
    p.add_argument("-d", "--dark", dest="dark", type=str,
        help="Dark file to use.")
    p.add_argument("-f", "--flat", dest="flat", type=str,
        help="Master flat file to use.")
    p.add_argument("-s", "--seeing", dest="seeing", type=float,
        default=0,
        help="Seeing in arcsec.")
    ## add arguments
    p.add_argument('image', type=str,
                   help="Image file to analyze")
    # p.add_argument('allothers', nargs='*',
    #                help="All other arguments")
    args = p.parse_args()

    if args.dark is not None:
        args.dark = os.path.expanduser(args.dark)
    if args.flat is not None:
        args.flat = os.path.expanduser(args.flat)
    args.image = os.path.expanduser(args.image)

    analyze_image(args.image, dark=args.dark, flat=args.flat, box_size=30,
                  medfilt=args.medfilt, plot=args.plot, seeing=args.seeing)
