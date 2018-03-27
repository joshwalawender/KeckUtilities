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
from ccdproc import CCDData, combine, Combiner, flat_correct, trim_image

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
## add options
# p.add_argument("--input", dest="input", type=str,
#     help="The input.")
## add arguments
# p.add_argument('argument', type=int,
#                help="A single argument")
# p.add_argument('allothers', nargs='*',
#                help="All other arguments")
args = p.parse_args()


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
        x1 = fit.mean_0.value
        x2 = fit.mean_1.value
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
def reduce_image(imagefile, darkfile = 'm180130_0001.fits',
                 filepath='../../../KeckData/MOSFIRE_FCS/',
                ):
    if not os.path.exists('masterflat.fits'):
        create_master_flat()
    masterflat = CCDData.read('masterflat.fits', unit='adu')
    dark = CCDData.read(os.path.join(filepath, darkfile), unit='adu')
    im = CCDData.read(os.path.join(filepath, imagefile), unit='adu')
    im = im.subtract(dark)
    im = flat_correct(im, masterflat)
    return im
    

##-------------------------------------------------------------------------
## Main Program
##-------------------------------------------------------------------------
def fit_alignment_box(im, boxat=[821, 1585], box_size=30, plot=False):
    
    fits_section = f'[{boxat[0]-box_size:d}:{boxat[0]+box_size:d}, {boxat[1]-box_size:d}:{boxat[1]+box_size:d}]'
    region = trim_image(im, fits_section=fits_section)
    
    # Estimate center of alignment box
    threshold_pct = 70
    window = region.data > np.percentile(region.data, threshold_pct)
    alignment_box_position = ndimage.measurements.center_of_mass(window)
    
    # Detect box edges
    gradx = np.gradient(region.data, axis=1)
    horizontal_profile = np.sum(gradx, axis=0)
    h_edges = fit_CSU_edges(horizontal_profile)
    grady = np.gradient(region.data, axis=0)
    vertical_profile = np.sum(grady, axis=1)
    v_edges = fit_CSU_edges(vertical_profile)
    
    # Estimate stellar position
    maxr = region.data.max()
    starloc = (np.where(region.data == maxr)[0][0],
               np.where(region.data == maxr)[1][0])
    
    # Build model of sky, star, & box
    boxamplitude = 1 #np.percentile(region.data, 90)
    star_amplitude = region.data.max() - boxamplitude
    
    box = mosfireAlignmentBox(boxamplitude, alignment_box_position[1], alignment_box_position[0],\
                       abs(h_edges[0]-h_edges[1]), abs(v_edges[0]-v_edges[1]))
    box.amplitude.fixed = True
    box.x_width.min = 10
    box.y_width.min = 10
    
    star = models.Gaussian2D(star_amplitude, starloc[1], starloc[0])
    star.amplitude.min = 0
    star.x_stddev.min = 1
    star.x_stddev.max = 8
    star.y_stddev.min = 1
    star.y_stddev.max = 8
    
    sky = models.Const2D(np.percentile(region.data, 90))
    sky.amplitude.min = 0
    
    model = box*(sky + star)
    
    fitter = fitting.LevMarLSQFitter()
    y, x = np.mgrid[:2*box_size+1, :2*box_size+1]
    fit = fitter(model, x, y, region.data)
    print(fitter.fit_info['message'])
    for i,name in enumerate(fit.param_names):
        print(f"{name:15s} = {fit.parameters[i]:.2f}")
    
    pixelscale = u.pixel_scale(0.1798*u.arcsec/u.pixel)
    FWHMx = 2*(2*np.log(2))**0.5*fit.x_stddev_2 * u.pix
    FWHMy = 2*(2*np.log(2))**0.5*fit.y_stddev_2 * u.pix
    FWHM = (FWHMx**2 + FWHMy**2)**0.5/2**0.5
    stellar_flux = 2*np.pi*fit.amplitude_2.value*fit.x_stddev_2.value*fit.y_stddev_2.value

    boxpos_x = boxat[1] - box_size + fit.x_0_0.value
    boxpos_y = boxat[0] - box_size + fit.y_0_0.value

    starpos_x = boxat[1] - box_size + fit.x_mean_2.value
    starpos_y = boxat[0] - box_size + fit.y_mean_2.value

    print(f"Sky Brightness = {fit.amplitude_1.value:.0f} ADU")
    print(f"Box X Center = {boxpos_x:.0f}")
    print(f"Box Y Center = {boxpos_y:.0f}")
    print(f"Stellar FWHM = {FWHM.to(u.arcsec, equivalencies=pixelscale):.2f}")
    print(f"Stellar Xpos = {starpos_x:.0f}")
    print(f"Stellar Xpos = {starpos_y:.0f}")
    print(f"Stellar Amplitude = {fit.amplitude_2.value:.0f} ADU")
    print(f"Stellar Flux (fit) = {stellar_flux:.0f} ADU")
    
    if plot == True:
        modelim = np.zeros((61,61))
        fitim = np.zeros((61,61))
        for i in range(0,60):
            for j in range(0,60):
                modelim[j,i] = model(i,j)
                fitim[j,i] = fit(i,j)
        resid = region.data-fitim
        plt.figure(figsize=(16,24))
        plt.subplot(1,4,1)
        plt.imshow(region.data, vmin=fit.amplitude_1.value*0.9, vmax=fit.amplitude_1.value+fit.amplitude_2.value)
        plt.subplot(1,4,2)
        plt.imshow(modelim, vmin=fit.amplitude_1.value*0.9, vmax=fit.amplitude_1.value+fit.amplitude_2.value)
        plt.subplot(1,4,3)
        plt.imshow(fitim, vmin=fit.amplitude_1.value*0.9, vmax=fit.amplitude_1.value+fit.amplitude_2.value)
        plt.subplot(1,4,4)
        plt.imshow(resid, vmin=-1000, vmax=1000)
        plt.show()
    
if __name__ == '__main__':
    im = reduce_image('/Users/jwalawender/KeckData/MOSFIRE_FCS/m180210_0254.fits')

    # Get info about alignment box positions
    hdul = fits.open('/Users/jwalawender/KeckData/MOSFIRE_FCS/m180210_0254.fits')
    slits = Table(hdul[3].data)
    slits = slits.group_by('Target_Priority')
    assert float(min(slits['Target_Priority'])) == -1.0
    alignment_boxes = slits.groups[0]

    

    boxes = [[1372, 1900],
             [821, 1585],
             [1542, 965],
             [792, 920],
             [1268, 302],
             ]
    for box in boxes:
        fit_alignment_box(im, boxat=box, plot=True)
