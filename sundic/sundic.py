################################################################################
# This file contains the functions for the sun-dic analysis.  The functions
# are used to perform local Digital Image Correlation (DIC) analysis.
##
# Author: G Venter
# Date: 2024/06/05
################################################################################

# Import libraries required by the code
import os as os
import natsort as ns
import configparser
import time
import cv2 as cv
import numpy as np
import skimage as sk
import ray as ray
from sundic.util.fast_interp import interp2d

# --------------------------------------------------------------------------------------------
# Constants that does not make sense to set in the settings file
CONFIG_FILENAME = 'settings.ini'   # File that contains the settings
ICLM_LAMBDA_0 = 100              # Initial value for lambda in IC-LM
ICLM_CZNSSD_0 = 4                # Initial value for CZNSSD in IC-LM
AKAZE_MIN_PNTS = 10               # Minimum number of keypoints to detect

# Maximum value for CZNSSD - indicate point has not be set
CNZSSD_MAX = 1000000


# --------------------------------------------------------------------------------------------
def tic():
    """
    Start the timer for measuring elapsed time.
    """
    global startTime_for_tictoc
    startTime_for_tictoc = time.time()


def toc():
    """
    Prints the elapsed time since the start time for the tictoc timer.

    If the start time is not set, it prints a message indicating that the start time is not set.
    """
    if 'startTime_for_tictoc' in globals():
        print("Elapsed time is " + str(time.time() -
              startTime_for_tictoc) + " seconds.")
    else:
        print("Toc: start time not set")


# --------------------------------------------------------------------------------------------
def getImageList(imgSubFolder, debugLevel=0):
    """
    Construct list of images from the specified sub-folder.  The list of images is sorted in
    natural order.

    Parameters:
        - imgSubFolder (string): A string specifying the folder for loading
            planar images.
        - debugLevel (int): Specify what level of debug output is requested.

    Returns:
        - list: A list of filenames of the images loaded from the specified
            folder.  The list of images are sorted naturally.
    """
    # Setup the image folder form the specified subfolder
    image_folder = os.path.join(os.getcwd(), imgSubFolder)

    # Get the filenames of all images in the directory
    files = os.listdir(image_folder)

    # Do a natural sort on the filenames
    files = ns.os_sorted(files)

    # Add the directory back into the filename and store as a list of all files
    image_set = []
    for f in files:
        image_set.append(os.path.join(image_folder, f))

    # Print debug messages based on debug level
    if debugLevel > 1:
        print('\nLoading images from folder: ' + image_folder)
        print('Images loaded, image set:')
        [print('  '+img) for img in image_set]

    # Return the list of filenames
    return image_set


# --------------------------------------------------------------------------------------------
def planarDICLocal(settings):
    """
    Perform local planar (2D) Digital Image Correlation (DIC) analysis.

    This function takes a dictionary of settings as input and performs local DIC analysis 
    based on the specified settings. The analysis involves processing a series of image pairs 
    to obtain displacement and strain data.

    Parameters:
        - settings (dict): A dictionary containing the settings for the DIC analysis. The 
            dictionary should include the following keys:

    Returns:
        - subSetPnts (list): A list of measurement points within the Region of Interest 
            (ROI). This is a 3D matrix where the first plane contains the x-coordinates
            the second plane the y-coordinates and the remaining planes the model
            coefficients.  This array can be processed to obtain displacement and strain 
            data and to generate graphs.

    Raises:
        - ValueError: If the 'ShapeFunctions' value in the settings dictionary is not 'Affine' 
            or 'Quadratic'.
    """
    # Store the debug level
    debugLevel = settings['DebugLevel']

    # Get the images to work with
    imgSet = getImageList(settings['ImageFolder'], debugLevel=debugLevel)

    # Get the Region of Interest (ROI)
    ROI = setupROI(settings['ROI'], imgSet[0], debugLevel=debugLevel)

    # Define measurement points using the settings specified in the config file
    # These are the center points of the subsets
    subSetSize = settings['SubsetSize']
    stepSize = settings['StepSize']
    nDefModCoeff = numShapeFnCoeffs(settings['ShapeFunctions'])
    subSetPnts = setupSubSets(
        subSetSize, stepSize, nDefModCoeff, ROI, debugLevel=debugLevel)
    
    # Get the image pair information
    imgDatum = settings['DatumImage']
    imgTarget = settings['TargetImage']
    imgIncr = settings['Increment']
    imgPairs = int((imgTarget - imgDatum)/imgIncr)

    # Debug output if requested
    if debugLevel > 0:
        print('\nImage Pair Information :')
        print('---------------------------------')
        print('  Number of image pairs: ', imgPairs)

    # Initialize the parallel enviroment if required
    nCpus = settings['CPUCount']
    if nCpus > 1:
        if debugLevel > 0:
            print('\nParallel Run Information :')
            print('---------------------------------')            
            print('  Starting parallel run with {} CPUs'.format(nCpus))
        ray.init(num_cpus=nCpus)

    # Loop through all image pairs to perform the local DIC
    imgDatum = 0
    imgTarget = 1  # ***Hardcoded for now - limit to a single image pair
    for imgPairIdx, img in enumerate(range(imgDatum, imgTarget, imgIncr)):

        # Setup the parallel run and wait for all results
        if nCpus > 1:
            # Turn of debugging temporarily
            nDebugOld = settings['DebugLevel']
            settings['DebugLevel'] = 0

            # Setup the submatrices - match shape to image if possible
            nTotRows, nTotCols, _ = subSetPnts.shape
            mRows, mCols = factorCPUCnt(nCpus)
            if nTotRows > nTotCols:
                mRows, mCols = mCols, mRows
            subMatrices  = __splitMatrix__(subSetPnts, mRows, mCols)

            # Track the processes that are being submitted
            procIDs = []
            for i in range(mRows*mCols):
                iRow, iCol = np.unravel_index( i, (mRows, mCols) )
                procIDs.append(rmt_icOptimization.remote(
                    settings, iRow, iCol, subMatrices[iRow][iCol], imgSet, img))
                if nDebugOld > 0:
                    print("  Starting remote process for submatrix {} {}".
                          format(iRow, iCol))

            # Wait for results - start pulling results from tasks as soon as they are
            # are done
            while len(procIDs):
                done_id, procIDs = ray.wait(procIDs)
                iRow, iCol, rsltMatrix = ray.get(done_id[0])
                (subMatrices[iRow][iCol])[:,:] = rsltMatrix
                if nDebugOld > 0:
                    print("  Submatrix {} {} completed".format(iRow, iCol))

            # Turn debugging back on
            settings['DebugLevel'] = nDebugOld

        # Serial run on one processor
        else :
            # coefficients at convergence for current (i'th) image pair
            subSetPnts = icOptimization(settings, subSetPnts, imgSet, img)

        # ***Measurement point coordinates and ROI for next image pair
        # if imgPairIdx < imgPairs - 1:
        #    subSetPnts = updateSubSets(subSetPnts, incrDefCoeffs)
        #    ROI = updateROI(subSetSize, subSetPnts)

        # Make some debug output
        if (settings['DebugLevel'] > 0):
            print('  \nImage pair {} processed'.format(imgPairIdx))

    # Shutdown the parallel environment if required
    if nCpus > 1:
        ray.shutdown()
    
    return subSetPnts


# --------------------------------------------------------------------------------------------
@ray.remote
def rmt_icOptimization(settings, iRowID, iColID, subSetPnts, imgSet, img):
    """
    Perform the IC optimization for a subset of points in a parallel environment.  This is a
    very thin wrapper for the icOptimization function that allows the function to be called
    from ray and keeps track of the subMatrix indices that are being processed.

    Parameters:
        - settings (dict): The settings for the DIC analysis.
        - iRowID (int): The row index of the submatrix.
        - iColID (int): The column index of the submatrix.
        - subSetPnts (ndarray): The subset points to optimize.
        - imgSet (ndarray): The array of images.
        - img (int): The index of the image to process.
    
    Returns:
        - tuple: A tuple containing the row index, column index, and the updated subset points.
    """
    rslt = icOptimization(settings, subSetPnts, imgSet, img)
    return iRowID, iColID, rslt


# --------------------------------------------------------------------------------------------
def setupROI(ROI, img0, debugLevel=0):
    """
    Get the Region of Interest (ROI) based on the settings provided by the user.

    Parameters:
        - ROI (int[]): An integer array of four values from the settings file.
        - img0 (str): The path to the reference image file.
        - debugLevel (int): The level of debug output to print.

    Returns:
        - ROI (int[]): An int array representing the ROI with four elements [XStart, YStart,
            XLength, YLength].
    """
    # If xLength or yLength is zero, use full image based on image size
    # of first image
    if (ROI[2] == 0 or ROI[3] == 0):

        # Read the image and determine the size
        img = cv.imread(img0, cv.IMREAD_GRAYSCALE)
        height, width = img.shape

        # Set the x-width
        if (ROI[2] == 0):
            ROI[2] = width - ROI[0]

        # Set the y height
        if (ROI[3] == 0):
            ROI[3] = height - ROI[1]

    # Debug print out
    if debugLevel > 0:
        print('\nROI : ')
        print('---------------------------------')
        print('  XStart  = '+str(ROI[0]))
        print('  YStart  = '+str(ROI[1]))
        print('  XLength = '+str(ROI[2]))
        print('  YLength = '+str(ROI[3]))

    return ROI


# --------------------------------------------------------------------------------------------
def setupSubSets(subSetSize, stepSize, nDefModCoeff, ROI, debugLevel=0):
    """
    Calculate the center points of subsets within a given region of interest (ROI) based on 
    the subset size and step size.

    Parameters:
    - subSetSize (int): The size of each subset.
    - stepSize (int): The step size between subsets.
    - nDefModCoeff (int): The number of deformation model coefficients.
    - ROI (tuple): A tuple containing the origin coordinates (xOrigin, yOrigin)
        and the dimensions (width, height) of the ROI.
    - debugLevel (int): The level of debug output to print.

    Returns:
    - subSetPnts (ndarray): An array of shape (nRows, nCols, nVals) where nRows are the number
        of rows in the point grid (y-values), nCols is the number of columns (x-values) and 
        nVals are the number of values stored for each point.  These are the x,y coordinates
        followed by the model coeficients.
    """
    # Get DIC bounds to work with based on the ROI definition
    xOrigin = ROI[0]
    yOrigin = ROI[1]
    xBound = xOrigin + ROI[2]
    yBound = yOrigin + ROI[3]

    # Now setup the measurement point coordidnates: defined in the reference image,
    # i.e subset centres
    y0, x0 = np.meshgrid(np.arange(int(yOrigin + subSetSize/2),
                                   int(yBound - subSetSize/2),
                                   stepSize),

                         np.arange(int(xOrigin + subSetSize/2),
                                   int(xBound - subSetSize/2),
                                   stepSize),

                         indexing='ij')

    # The number of rows and columns in the subset grid
    nRows, nCols = y0.shape

    # Allocate the memory for the subset points
    subSetPnts = np.zeros((nRows, nCols, 2 + nDefModCoeff + 1))

    # Store the x and y coordinates in the subSetPnts
    subSetPnts[:, :, 0] = x0
    subSetPnts[:, :, 1] = y0

    # Print debug output if requested
    if debugLevel > 0:
        nSubSets = nRows * nCols
        print('\nSubset Information : ')
        print('---------------------------------')
        print('  Number of subsets defined :'+str(nSubSets))
        print('  Number of rows in subset grid :'+str(nRows))
        print('  Number of columns in subset grid :'+str(nCols))

    return subSetPnts


# --------------------------------------------------------------------------------------------
def relativeCoords(subSetSize):
    """
    Generate relative/local coordinates of pixels within the subset.  The coordinates are
    generated based on the subset size with one point for each pixel in the subset.

    Parameters:
    - subSetSize (int): The size of the subset.

    Returns:
    - tuple: A tuple containing the xsi and eta coordinates as numpy arrays.
    """
    # Relative/local coordinates of pixels within the subset (the same for all subsets)
    [eta, xsi] = np.meshgrid(np.linspace(-0.5*(subSetSize-1),
                                         0.5*(subSetSize-1),
                                         subSetSize),
                             np.linspace(-0.5*(subSetSize-1),
                                         0.5 * (subSetSize-1),
                                         subSetSize),
                             indexing='ij')

    # Flatten local coordinates to vectors
    xsi = xsi.reshape(-1, order='F')
    eta = eta.reshape(-1, order='F')

    return xsi, eta


# --------------------------------------------------------------------------------------------
def updateSubSets(subSetPnts, incrCoeffs):
    """
    Update the subset points based on the calculated displacement values as we move from one
    image pair to the next.

    Parameters:
        - subSetPnts (numpy.ndarray): An current array of subset points.
        - incrCoeffs (numpy.ndarray): An array of displacement coefficients.

    Returns:
        - numpy.ndarray: An updated array of subset points.
    """
    # The x and y displacement values for all subsets
    nCoeffs = incrCoeffs.shape[0]
    u = incrCoeffs[0, :]
    v = incrCoeffs[int(nCoeffs/2), :]

    # Update the measurement points to be at the old points plus the
    # displacement values
    return subSetPnts + np.vstack((u, v))


# --------------------------------------------------------------------------------------------
def updateROI(subSetSize, subSetPnts):
    """
    Update the region of interest (ROI) based on the new subset points.

    Parameters:
        - subSetSize (int): The size of the subset.
        - subSetPnts (ndarray): An array of subset points.

    Returns:
        - tuple: A tuple representing the updated ROI, in the
            format (xMin, yMin, width, height).
    """

    # Current subset center points values and subset size
    xo = subSetPnts[0, :]
    yo = subSetPnts[1, :]

    # ROI of new reference image
    xMin = np.min(xo) - (subSetSize-1)/2
    xMax = np.max(xo) + (subSetSize-1)/2

    yMin = np.min(yo) - (subSetSize-1)/2
    yMax = np.max(yo) + (subSetSize-1)/2

    # The new ROI
    ROI = (xMin, yMin, xMax-xMin, yMax-yMin)

    return ROI


# --------------------------------------------------------------------------------------------
def icOptimization(settings, subSetPnts, imgSet, img):
    """
    Perform IC (inverse compositional update) optimization for image correlation.  Currently
    two optimization algorithms are supported - IC-GN (Gauss Newton) or 
    IC-LM (Levenberg-Marquardt).

    Parameters:
        - settings (dict): Dictionary containing the optimization settings.
        - subSetPnts (ndarray): 3D Array of subset point information.
        - imgSet (ndarray): Array of reference images.
        - img (int): Target image - index into the imgSet array.

    Returns:
        - subSetPnts: 3D Array of updated subSetPnt information (shape function coefficients).

    Raises:
        - ValueError: If an invalid optimization algorithm is specified.
    """
    # Setup subset info
    subSetSize = settings['SubsetSize']
    imgIncr = settings['Increment']
    nSubSets = subSetPnts.shape[0]*subSetPnts.shape[1]

    # Setup the GaussBlur parameters
    gbSize = settings['GaussianBlurSize']
    gbStdDev = settings['GaussianBlurStdDev']

    # The number of GQ starting points and the background cutoff value
    nBGCutOff = settings['BackgroundCutoff']
    nGPPoints = settings['StartingPoints']

    # Initialize the last entry for each subset point to the max CZNSSD value
    subSetPnts[:, :, -1] = CNZSSD_MAX

    # Detect algorithm to use
    isICGN = True
    isNormalized = False
    algorithm = settings['OptimizationAlgorithm']
    # IC-GN algorithm
    if algorithm == 'IC-GN':
        isICGN = True
        isNormalized = False
    # IC-LM algorithm
    elif algorithm == 'IC-LM':
        isICGN = False
        isNormalized = True
    else:
        raise ValueError(
            'Invalid optimizationAlgorithm specified. Only supported values are: IC-GN | IC-LM')

    # Process reference and target images for current image pair
    # delF: dFdy = delF[0], dFdx = delF[1]
    # Process the two images
    # slow - 1s
    F, FInter, delF, FMax = processImage(imgSet, img, [gbSize, gbStdDev],
                                         isDatumImg=True, isNormalized=isNormalized)
    
    # fast
    G, GInter, _, _ = processImage(imgSet, img+imgIncr, [gbSize, gbStdDev],
                                   isDatumImg=False, isNormalized=isNormalized)
    
    # ***Adjust the BGCutOff value - this is currently a very crude way to do this
    # Should most probably look at difference in intensity values
    if algorithm == 'IC-LM':
        nBGCutOff = nBGCutOff/FMax

    # Get the local coordinates for a subset
    xsi, eta = relativeCoords(subSetSize)
    
    # Get the starting point for the optimization
    # slow 2.5 s
    nextPnt, subSetPnts = getStartingPnt(subSetPnts, nGPPoints, xsi, eta, subSetSize,
                                         F, G, FInter, GInter, nBGCutOff,
                                         shapeFns=settings['ShapeFunctions'])

    # Boolean array to indicate which points have been analyzed - initially all are false
    analyze = np.zeros_like(subSetPnts[:,:,0], dtype=bool)

    # Print debug info if requested
    if settings['DebugLevel'] > 0:
        print('\nStarting IC Optimization for Image Pair: '+str(img))
        print('---------------------------------')
  
    # Loop through all subset points, determine the model coefficients
    # for each subset independently - the order is determined by the next best
    # point to optimize
    for iSubSet in range(0, nSubSets):

        # Subset centre coordinates for current subset
        x0 = int(subSetPnts[nextPnt[0], nextPnt[1], 0])
        y0 = int(subSetPnts[nextPnt[0], nextPnt[1], 1])

        # Intensity data for reference subset
        f, f_mean, f_tilde, dfdx, dfdy = referenceSubSetInfo(
            F, delF, x0, y0, subSetSize)

        # Hessian and Jacobian operators for GuassNewton optimization routine,
        # derived from the reference subset intensity gradient data
        H, J = getHessianInfo(dfdx, dfdy, xsi, eta, subSetSize,
                              shapeFns=settings['ShapeFunctions'],
                              isNormalized=isNormalized)

        # Current subset model shape function coefficients
        iRow, iCol = nextPnt
        shapeFnCoeffs_i = subSetPnts[iRow, iCol, 2:]

        # Initial estimate for the incremental update of the model coefficients
        # in the current iteration - initial estimate set to 0 for all coefficients
        deltaP = np.zeros_like(shapeFnCoeffs_i)

        # Perform optimisation routine - IC-GN or IC-LM
        iter = 0
        while iter < settings['MaxIterations']:

            # Check for convergence, otherwise update the model coefficients
            if iter > 0 and isConverged(settings['ConvergenceThreshold'], deltaP, subSetSize,
               shapeFns=settings['ShapeFunctions']):
                break
            else:

                # Relative deformed subset coordinates, based on current
                # iteration of deformation model
                xsi_d, eta_d = relativeDeformedCoords(
                    shapeFnCoeffs_i, xsi, eta, shapeFns=settings['ShapeFunctions'])

                # Intensity data for reference subset
                g, g_mean, g_tilde = deformedSubSetInfo(
                    GInter, x0, y0, xsi_d, eta_d)

                # Calculate and store the current CZNSSD value
                shapeFnCoeffs_i[-1] = calcCZNSSD(nBGCutOff,
                                                 f, f_mean, f_tilde, g, g_mean, g_tilde)

                # Check if CZNSSD is at maximum value - indicates point is not found
                if shapeFnCoeffs_i[-1] == CNZSSD_MAX:
                    iter = settings['MaxIterations']
                    break

                # Calculate the residuals
                res = f-f_mean-(f_tilde/g_tilde)*(g-g_mean)

                # The right hand side of the update equation
                b = -np.dot(J.T, res)

                # Perform IC-GN update
                if isICGN:

                    # Get the new deltaP
                    deltaP = np.squeeze(np.linalg.solve(H, b))

                    # Update the model coefficients
                    shapeFnCoeffs_i[:-1] = modelCoeffUpdate(shapeFnCoeffs_i, deltaP,
                                                            shapeFns=settings['ShapeFunctions'])

                # Perform IC-LM update
                else:
                    # Delta p deformation applied to the original image
                    xsi_df, eta_df = relativeDeformedCoords(
                        deltaP, xsi, eta, shapeFns=settings['ShapeFunctions'])

                    df, df_mean, df_tilde = deformedSubSetInfo(
                        FInter, x0, y0, xsi_df, eta_df)

                    # Get he current CZNSSD value
                    cznssd = calcCZNSSD(nBGCutOff,
                                        df, df_mean, df_tilde, g, g_mean, g_tilde)

                    # Initialize the lambda and cznssd_0 values
                    if iter == 0:
                        cznssd_0 = ICLM_CZNSSD_0
                        lam = ICLM_LAMBDA_0 ** (cznssd/ICLM_CZNSSD_0) - 1.

                    # Identity matrix with lambda value on diagonals
                    lamI = lam*np.identity(H.shape[0])

                    # Solve for the normalized detlaP
                    deltaP = np.squeeze(np.linalg.solve((H+lamI), b))

                    # Convert to the non-normalized deltaP
                    K = 0.5*(subSetSize-1)
                    if settings['ShapeFunctions'] == 'Affine':
                        M = np.diag([1., 1./K, 1./K, 1., 1./K, 1./K])
                    elif settings['ShapeFunctions'] == 'Quadratic':
                        M = np.diag([1., 1./K, 1./K, 1./(K*K), 1./(K*K), 1./(K*K),
                                     1., 1./K, 1./K, 1./(K*K), 1./(K*K), 1./(K*K)])

                    deltaP = np.dot(M, deltaP)

                    # Update lambda
                    if cznssd >= cznssd_0:
                        lam = 10.*lam
                    else:
                        lam = 0.1*lam

                        # Update the model coefficients
                        shapeFnCoeffs_i[:-1] = modelCoeffUpdate(shapeFnCoeffs_i, deltaP,
                                                                shapeFns=settings['ShapeFunctions'])

                        # Update cznssd_0
                        cznssd_0 = cznssd

            iter += 1

        # If we do not converge the point is not found and se will add nan to the shape
        # function coefficients
        if iter == settings['MaxIterations']:
            shapeFnCoeffs_i[:] = np.nan
            shapeFnCoeffs_i[-1] = CNZSSD_MAX

        # Print debug output if requested
        if settings['DebugLevel'] > 1:
            print("  Subset {0:6d} of {1:6d}: ID ({2:4d},{3:4d})  Iteration Cnt {4:3d}".
                  format(iSubSet, nSubSets, iRow, iCol, iter))

        elif settings['DebugLevel'] > 0 and iSubSet % 100 == 0:
            print("  Subset {0:6d} of {1:6d}: ID ({2:4d},{3:4d})  Iteration Cnt {4:3d}".
                  format(iSubSet, nSubSets, iRow, iCol, iter))

        # Mark the current point as analyzed
        analyze[nextPnt] = True

        # Find the next point to iterate to
        nextPnt, subSetPnts = getNextPnt(nextPnt, subSetPnts, analyze, xsi, eta,
                                         F, G, FInter, GInter, nBGCutOff,
                                         shapeFns=settings['ShapeFunctions'])

    return subSetPnts


# --------------------------------------------------------------------------------------------
def processImage(imgSet, img, gaussBlur, isDatumImg=True, isNormalized=False):
    """
    Process an image to obtain DIC specific parameters.  If this is the datum image
    the gradient of the image is also calculated.  Otherwise, only the image and
    the interpolated image is calculated.

    Paramters:
        - imgSet (list): A list of image paths.
        - img (int): The index of the image to process.
        - gaussBlur (tuple): Gauss blur size and std dev.
        - isDatumImg (bool, optional): Indicates whether the image is the
            reference image. Defaults to True.
        - isNormalized (bool, optional): Indicates whether the image should be
            normalized. Defaults to False.

    Returns:
        tuple: A tuple containing the processed image and related data.
            - F (numpy.ndarray): The processed image.
            - F_interpolated (numpy.ndarray): The interpolated image.
            - delF (numpy.ndarray or None): The gradient of the image in the
                x and y directions, or None if isDatumImg is False.
            - Fmax (int): The maximum value of the image.
    """
    # Pre-blur filter parameters from settings file
    gfSize, gfStdDev = gaussBlur

    # Read the image as grayscale
    F = cv.imread(imgSet[img], cv.IMREAD_GRAYSCALE)

    # Blur image with gaussian filter - if specified in settings
    if (gfSize > 0):
        F = cv.GaussianBlur(F, (gfSize, gfSize), gfStdDev)

    # Normalize the image if requested
    Fmax = np.max(F)
    if isNormalized:
        F = F/Fmax

    # Setup the interpolator for this image - needs to pass double precision values
    # for interpolation to work
    FInter = fastInterpolation(F.astype('double'))

    # Setup the gradients, but only if this is a reference image
    delF = None
    if (isDatumImg):
        # Gradient of the image in the x and y directions
        # delF = np.gradient(F)
        delF = np.gradient(F)

    return F, FInter, delF, Fmax


# --------------------------------------------------------------------------------------------
def getNextPnt(currentPnt, subSetPnts, analyzed, xsi, eta, F, G, FInter, GInter, 
               nBGCutOff, shapeFns='Affine'):
    """
    Get the next point to analyze in the optimization algorithm.  The next point is
    selected based on updated, estimated CZNSSD values for points the current point and the 
    current deformation model.

    Parameters:
        - currentPnt (tuple): The index of the current point - tuple with iRow and ICol.
        - subSetPnts (numpy.ndarray): The subSetPnts data strucutre - 3D array that contains
            coordinates of the center points and deformation model coefficients.
        - analyzed (numpy.ndarray): A boolean array indicating which points have been analyzed.
        - xsi (numpy.ndarray): The local x-coordinates of the subset.
        - eta (numpy.ndarray): The local y-coordinates of the subset.
        - F (numpy.ndarray): The query image.
        - G (numpy.ndarray): The train image.
        - FInter (numpy.ndarray): The interpolated query image.
        - GInter (numpy.ndarray): The interpolated train image.
        - nBGCutOff (int): The cutoff value to detect all black backgrounds.
        - shapeFns (str): The type of shape functions used in the deformation model.

    Returns:
        - tuple: The iRow, iCol index of the next point to analyze.
        - numpy.ndarray: The updated subSetPnts array.
    """
    # Get the matrix position of the current point
    iRow, iCol = currentPnt

    # Get the four neighbors of the current point
    maxRow = subSetPnts.shape[0] - 1
    maxCol = subSetPnts.shape[1] - 1    
    neighbors = np.zeros((4,2), dtype=int)
    neighbors[0, 0] = iRow - 1 if iRow > 0 else iRow
    neighbors[0, 1] = iCol
    neighbors[1, 0] = iRow + 1 if iRow < maxRow else iRow
    neighbors[1, 1] = iCol
    neighbors[2, 0] = iRow
    neighbors[2, 1] = iCol - 1 if iCol > 0 else iCol
    neighbors[3, 0] = iRow
    neighbors[3, 1] = iCol + 1 if iCol < maxCol else iCol

    # Apply the current deformation model to the neighbors and calculate the resulting CZNSSD value
    # Update the CZNSSD value and the shape function parameters if the new CZNSSD value is smaller
    for pnt in neighbors:

        # Current pnt row and col value
        iRow, iCol = pnt

        # Skip this point if it has already been analyzed
        if analyzed[iRow, iCol]:
            continue

        # The current point and its coordinates
        x0 = int(subSetPnts[iRow, iCol, 0])
        y0 = int(subSetPnts[iRow, iCol, 1])

        # Impose the deformation model on the subset and get the reference and deformed
        # subset information
        xsi_d, eta_d = relativeDeformedCoords(
            subSetPnts[iRow, iCol, 2:-1], xsi, eta, shapeFns=shapeFns)
        f, f_mean, f_tilde = deformedSubSetInfo(FInter, x0, y0, xsi, eta)
        g, g_mean, g_tilde = deformedSubSetInfo(GInter, x0, y0, xsi_d, eta_d)

        # Get the CZNSSD value for the current point
        oldCZNSSD = subSetPnts[iRow, iCol, -1]
        newCZNSSD = calcCZNSSD(nBGCutOff, f, f_mean,
                               f_tilde, g, g_mean, g_tilde)

        # Store the CZNSSD value in the last element of the parameter vector
        if newCZNSSD < oldCZNSSD:
            subSetPnts[iRow, iCol, 2:] = subSetPnts[currentPnt[0], currentPnt[1], 2:]
            subSetPnts[iRow, iCol, -1] = newCZNSSD

    # Find the index of the best point that has not been analyzed yet using a masked
    # array to ignore the analyzed points
    maskedArray = np.ma.masked_array(subSetPnts[:,:,-1], mask=analyzed)
    nextPnt = np.unravel_index(np.argmin(maskedArray), maskedArray.shape)

    # Return the next point to analyze
    return nextPnt, subSetPnts


# --------------------------------------------------------------------------------------------
def getStartingPnt(subSetPnts, nGQPoints, xsi, eta, subSetSize, F, G, FInter, GInter,
                   nBGCutOff, shapeFns='Affine'):
    """
    Get the starting point for the optimization algorithm.  This is done by detecting
    keypoints in a selection of subset points located at Gauss Quadrature points spread
    over the image.  The keypoints are matched and used to estimate the
    deformation from the reference to the deformed image to calcluate the CZNSSD parameter
    for each.  The point the smallest CZNSSD is selected as the starting point.  This 
    should provide a good starting point for the optimization algorithm for these points.

    Parameters:
        - subSetPnts (numpy.ndarray): 3D Array of subSetPoint information - center point 
            coordinates and model coefficients.
        - nGQPoints (int): The number of Gauss Quadrature points to use as starting points.
        - xsi (numpy.ndarray): The local x-coordinates of the subset.
        - eta (numpy.ndarray): The local y-coordinates of the subset.
        - subSetSize (int): The size of each subset.
        - F (numpy.ndarray): The query image.
        - G (numpy.ndarray): The train image.
        - FInter (numpy.ndarray): The interpolated query image.
        - GInter (numpy.ndarray): The interpolated train image.
        - nBGCutOff (int): The cutoff value to detect all black backgrounds.
        - shapeFns (str): The type of shape functions used in the deformation model.

    Returns:
        - (iRow, iCol): The index of the best starting point.
        - subSetPnts: Updated with the deformation model coefficients for each starting point.
    """
    # Get the Gauss points
    gqPnts, _ = np.polynomial.legendre.leggauss(nGQPoints)

    # Scale the points to the desired ranges in terms of the rows and cols
    # int the subSetPnts matrix
    nRow = subSetPnts.shape[0]
    nCol = subSetPnts.shape[1]
    xPnts = np.round(((nCol/2 - 1) * (1 + gqPnts))).astype(int)
    yPnts = np.round(((nRow/2 - 1) * (1 + gqPnts))).astype(int)

    # Extract the points to use in the Akaze detect
    # Do broadcasting to get all the required points not just a diagonal
    # Note: We are now using fancy indexing so we have a copy of the data in adPoints
    adPoints = subSetPnts[yPnts[:, np.newaxis], xPnts, :]

    # Do the Akaze detect for all the test points and get back the parameter
    # vector
    adPoints = akazeDetect(adPoints, subSetSize, F, G)

    # Store the parameters with the CZNSSD value in the shapeFnCoeff matrix
    it = np.nditer([adPoints[:, :, 0], adPoints[:, :, 1]],
                   flags=['multi_index'])
    for x0, y0 in it:

        # Impose the deformation model on the subset and get the reference and deformed
        # subset information
        iRow = it.multi_index[0]
        iCol = it.multi_index[1]

        xsi_df, eta_df = relativeDeformedCoords(
            adPoints[iRow, iCol, 2:-1], xsi, eta, shapeFns=shapeFns)
        f, f_mean, f_tilde = deformedSubSetInfo(FInter, x0, y0, xsi, eta)
        g, g_mean, g_tilde = deformedSubSetInfo(GInter, x0, y0, xsi_df, eta_df)

        # Get the current CZNSSD value
        cznssd = calcCZNSSD(nBGCutOff, f, f_mean, f_tilde, g, g_mean, g_tilde)

        # Store the CZNSSD value in the last element of the parameter vector
        adPoints[iRow, iCol, -1] = cznssd

    # Update the original data structure - remember adPoints was a copy due to fancy
    # indexing
    subSetPnts[yPnts[:, np.newaxis], xPnts, :] = adPoints

    # We can actually setup a mask to search as we do for the getNextPoint operation, 
    # however it seems faster to just directly search for the minimum value and it is
    # only done once
    startIdx = np.unravel_index(
        np.argmin(subSetPnts[:, :, -1]), subSetPnts[:, :, -1].shape)

    return startIdx, subSetPnts


# --------------------------------------------------------------------------------------------
def akazeDetect(adPoints, subSetSize, F, G):
    """
    Detects keypoints and computes descriptors using the AKAZE algorithm for the specified
    subsets (in adPoints) in the given images.  The keypoints are matched and used to 
    estimate the deformation from the reference to the deformed image.  This should provide 
    a good starting point for the optimization algorithm for these points.

    Parameters:
        - adPoints (numpy.ndarray): The subset of points to use as starting points from the
            subSetPnts data structure.
        - subSetSize (int): The size of each subset.
        - F (numpy.ndarray): The query image.
        - G (numpy.ndarray): The train image.

    Returns:
        - adPoints: The adPoints updated with the estimated deformation model coefficients.
    """
    # Number of model cofficients
    # Subtract the columns for x and y coordinates and the CZNSSD value
    nCoeffs = adPoints.shape[2] - 3

    # Normalize the images to be in the range 0-255 - this is needed for
    # the AKAZE algorithm
    origTrainImg = cv.normalize(
        G, None, 0, 255, cv.NORM_MINMAX).astype('uint8')
    origQueryImg = cv.normalize(
        F, None, 0, 255, cv.NORM_MINMAX).astype('uint8')

    # Now detect the keypoints in each subset and compute the descriptors for the
    # query image and train image for all the subsets
    # Loop through all the points and perform Akaze detection for each
    iCnt = 0
    it = np.nditer([adPoints[:, :, 0], adPoints[:, :, 1]],
                   flags=['multi_index'])
    for x, y in it:

        # Factor needed to increase size of image if needed to get enough keypoints
        nSizeFactor = 1

        # Get the keypoints in the query image - keep increasing the subset size until
        # we have enough keypoints
        for i in range(0, AKAZE_MIN_PNTS):

            # Setup the subset bounds - we use twice the subset size to
            # increase the number of keypoints we detect
            yMin = max(0, int(y - nSizeFactor*(subSetSize-1)/2))
            yMax = min(int(y + nSizeFactor*(subSetSize-1)/2),
                       origQueryImg.shape[0])
            xMin = max(0, int(x - nSizeFactor*(subSetSize-1)/2))
            xMax = min(int(x + nSizeFactor*(subSetSize-1)/2),
                       origQueryImg.shape[1])

            # Slice the query image around the current subset from F
            trainImg = origTrainImg[yMin:yMax, xMin:xMax]
            queryImg = origQueryImg[yMin:yMax, xMin:xMax]

            # Setup the akaze detector and the training image - only once
            akaze = cv.AKAZE_create()
            kpG, descG = akaze.detectAndCompute(trainImg, None)

            # Detect the keypoints and compute the descriptors
            kpQ, descQ = akaze.detectAndCompute(queryImg, None)

            # If we have found at least the minimum number of keypoints, we can
            # break out of the loop
            if (len(kpQ) > AKAZE_MIN_PNTS) and (len(kpG) > AKAZE_MIN_PNTS):
                break

            # Otherwise, increase the subset size factor and try again
            nSizeFactor += 1

        # Setup the matcher to detect keypoint matches in the query and G images
        matcher = cv.BFMatcher(cv.NORM_HAMMING, crossCheck=True)
        matches = matcher.match(descQ, descG)  # query then train

        # Store the x and y coordinates of the keypoints
        nTop = len(matches)
        coordQ = np.zeros([2, nTop])
        coordG = np.zeros([2, nTop])
        for idx, m in enumerate(matches[:nTop]):
            coordQ[:, idx] = kpQ[m.queryIdx].pt[:]
            coordG[:, idx] = kpG[m.trainIdx].pt[:]

        # Do a ransac to find the best affine transformation based on the
        # keypoint coordinates stored in coordQ and coordG
        try:
            model_robust, _ = sk.measure.ransac((coordQ.T, coordG.T), sk.transform.AffineTransform,
                                                min_samples=3, residual_threshold=2,
                                                max_trials=100)

            # Get the affine transformation homography coefficients
            iRow = it.multi_index[0]
            iCol = it.multi_index[1]
            adPoints[iRow, iCol, 2+0] = model_robust.params[0][2]
            adPoints[iRow, iCol, 2+1] = model_robust.params[0][0] - 1.0
            adPoints[iRow, iCol, 2+2] = model_robust.params[0][1]

            adPoints[iRow, iCol, 2+int(nCoeffs/2)] = model_robust.params[1][2]
            adPoints[iRow, iCol, 2+int(nCoeffs/2) +
                     1] = model_robust.params[1][0]
            adPoints[iRow, iCol, 2+int(nCoeffs/2) +
                     2] = model_robust.params[1][1] - 1.0

        except:
            pass

        # Increment the counter
        iCnt = iCnt + 1

    return adPoints


# --------------------------------------------------------------------------------------------
def referenceSubSetInfo(F, delF, x0, y0, subSetSize):
    """
    Extracts subset information from the reference image that is needed as part of the
    optimizatn run.  This inclue the subset intensity values, the mean intensity, the
    normalized sum of squared differences, and the gradient information.

    Parameters:
    - F: numpy.ndarray
        The mother image.
    - delF: tuple of numpy.ndarray
        The gradient information of the mother image. delF[0] represents the gradient in 
        the y-direction (Fy), and delF[1] represents the gradient in the x-direction (Fx).
    - x0: int
        The x-coordinate of the subset center.
    - y0: int
        The y-coordinate of the subset center.
    - subSetSize: int
        The size of the subset.

    Returns:
    - f: numpy.ndarray
        The reference subset intensity values extracted from the mother image.
    - f_mean: float
        The average subset intensity.
    - f_tilde: float
        The normalized sum of squared differences of the subset intensity values.
    - dfdx: numpy.ndarray
        The gradient in the x-direction (Fx) of the subset.
    - dfdy: numpy.ndarray
        The gradient in the y-direction (Fy) of the subset.
    """
    # Get the upper and lower bound that define the subset in the
    # reference image
    bound = int(0.5*(subSetSize-1))

    # Extract  refrence subset intensity values, f, from mother image, F,
    f = F[y0-bound:y0+bound+1, x0-bound:x0+bound+1]
    f = f.reshape(-1, 1, order='F')

    # Extract the gradient information
    # Note: Fy = delF[0], Fx = delF[1]
    dfdy = delF[0][y0-bound:y0+bound+1, x0-bound:x0+bound+1]
    dfdy = dfdy.reshape(-1, order='F')

    dfdx = delF[1][y0-bound:y0+bound+1, x0-bound:x0+bound+1]
    dfdx = dfdx.reshape(-1, order='F')

    # Average subset intensity, and normalised sum of squared differences
    f_mean = f.mean()
    f_tilde = np.linalg.norm(f-f_mean)

    return f, f_mean, f_tilde, dfdx, dfdy


# --------------------------------------------------------------------------------------------
def getHessianInfo(dfdx, dfdy, xsi, eta, subSetSize, shapeFns='Affine', isNormalized=False):
    """
    Calculate the Hessian matrix and Jacobian array based on the given inputs.

    Parameters:
    - dfdx (numpy.ndarray): Array of partial derivatives of the function with respect to x.
    - dfdy (numpy.ndarray): Array of partial derivatives of the function with respect to y.
    - xsi (numpy.ndarray): Array of xsi values.
    - eta (numpy.ndarray): Array of eta values.
    - shapeFns (str): Type of shape functions to use. Default is 'Affine'.
    - isNormalized (bool): Indicates whether the coordinates are normalized. Default is False.

    Returns:
    - hessian (numpy.ndarray): The Hessian matrix.
    - jacobian (numpy.ndarray): The Jacobian array.
    """

    # Normalize the coordinates if requested
    if isNormalized:
        K = 0.5*(subSetSize-1)
        xsi = xsi/K
        eta = eta/K

    # Affine transformation
    if shapeFns == 'Affine':
        jacobian = np.array([dfdx,
                             dfdx*xsi,
                             dfdx*eta,
                             dfdy,
                             dfdy*xsi,
                             dfdy*eta]).T

    elif shapeFns == 'Quadratic':
        jacobian = np.array([dfdx,
                             dfdx*xsi,
                             dfdx*eta,
                             dfdx*0.5*xsi**2,
                             dfdx*xsi*eta,
                             dfdx*0.5*eta**2,
                             dfdy,
                             dfdy*xsi,
                             dfdy*eta,
                             dfdy*0.5*xsi**2,
                             dfdy*xsi*eta,
                             dfdy*0.5*eta**2]).T
    else:
        raise ValueError(
            'Invalid ShapeFunctions value. Only supported values are: Affine | Quadratic')

    # Setup the Hessian as the dot product of the Jacobian array with its transpose
    hessian = np.dot(jacobian.T, jacobian)

    return hessian, jacobian


# --------------------------------------------------------------------------------------------
def relativeDeformedCoords(p, xsi, eta, shapeFns='Affine'):
    """
    Calculates the relative deformed image subset coordinates based on the given 
    shape functions at the current iteration.

    Parameters:
     - p (list): The subset warp coefficients.
     - xsi (float): The local xsi coordinate.
     - eta (float): The locla eta coordinate.
     - shapeFns (str, optional): The type of deformation model. Defaults to 'Affine'.

    Returns:
     - tuple: The calculated xsi_d and eta_d coordinates.

    Raises:
     - ValueError: If an invalid shapeFns value is provided.
    """
    # Check for invalid models
    if np.isnan(p).any():
        xsi_d = xsi
        eta_d = eta

    # Affine model
    elif shapeFns == 'Affine':
        # Displacement, stretch and shear subset in xy-coordinates (Affine):
        # Order of SFP's p[j]: 0  1   2   3   4   5
        #                      u  ux  uy  v   vx  vy
        xsi_d = (1+p[1])*xsi + p[2]*eta + p[0]
        eta_d = p[4]*xsi + (1+p[5])*eta + p[3]

    # Quadratic model
    elif shapeFns == 'Quadratic':
        # order of SFP's p[j]: 0  1   2   3    4    5    6  7   8   9    10   11
        #                      u  ux  uy  uxx  uxy  uyy  v  vx  vy  vxx  vxy  vyy
        xsi_d = 0.5*p[3]*xsi**2 + p[4]*xsi*eta + 0.5 * \
            p[5]*eta**2 + (1+p[1])*xsi + p[2]*eta + p[0]
        eta_d = 0.5*p[9]*xsi**2 + p[10]*xsi*eta + 0.5 * \
            p[11]*eta**2 + p[7]*xsi + (1+p[8])*eta + p[6]

    # Invalid model
    else:
        raise ValueError(
            'Invalid ShapeFunctions value. Only supported values are: Affine | Quadratic')

    return xsi_d, eta_d


# --------------------------------------------------------------------------------------------
def deformedSubSetInfo(GInter, x0, y0, xsi_d, eta_d):
    """
    Calculate deformed subset intensity information.

    Parameters:
    - GInter: A function that interpolates the intensity values from the mother 
        image at sub-pixel coordinates.
    - x0: The x-coordinate of the original subset.
    - y0: The y-coordinate of the original subset.
    - eta_d: The displacement in the y-direction of the deformed subset.
    - xsi_d: The displacement in the x-direction of the deformed subset.

    Returns:
    - g: The deformed subset intensity values.
    - g_mean: The average intensity value of the deformed subset.
    - g_tilde: The normalized sum of squared differences of the deformed subset.
    """
    # Deformed subset coordinates
    yd = y0 + eta_d
    xd = x0 + xsi_d

    # Extract  deformed subset intensity values, g, from mother image
    # at sub-pixel coordinates using interpolation
    nRows = yd.shape[0]
    # --------------------------------------------------------------
    # -- Build-in interpolation function in Python
    # g = GInter.ev(yd.reshape(nRows, 1), xd.reshape(nRows, 1))
    # --------------------------------------------------------------
    g = GInter(yd.reshape(nRows, 1), xd.reshape(nRows, 1))

    # Determine average intensity value of subset g,
    # and normalised sum of squared differences of subset, g_tilde
    g_mean = g.mean()
    g_tilde = np.linalg.norm(g-g_mean)

    return g, g_mean, g_tilde


# --------------------------------------------------------------------------------------------
def isConverged(convergenceThreshold, deltaP, subSetSize, shapeFns='Affine'):
    """
    Check if the optimizatin has converged based on the given convergence criteria,
    current data_p and shape functions.

    Parameters:
     - convergenceThreshold (float): The threshold value for convergence.
     - delta_p (float): The change in displacement field.
     - subSetSize (int): The size of the subset.
     - shapeFns (str, optional): The type of shape functions to use. Defaults to 'Affine'.

    Returns:
     - bool: True if the optimizatin field has converged, False otherwise.
    """

    # hw is the half-width of the subset
    hw = 0.5*(subSetSize-1)
    if shapeFns == 'Affine':
        hw_vector = np.array([1, hw, hw,
                              1, hw, hw])

    elif shapeFns == 'Quadratic':
        hw_vector = np.array([1, hw, hw, 0.5*hw**2, hw**2, 0.5*hw**2,
                              1, hw, hw, 0.5*hw**2, hw**2, 0.5*hw**2])

    else:
        raise ValueError(
            'Invalid ShapeFunctions value. Only supported values are: Affine | Quadratic')

    # Now check for convergence
    exitCriteria = np.linalg.norm(deltaP*hw_vector)
    if (exitCriteria < convergenceThreshold):
        return True
    else:
        return False


# --------------------------------------------------------------------------------------------
def modelCoeffUpdate(p, dp, shapeFns='Affine'):
    """
    Update the model coefficients based on the results from the current Gauss Newton  or
    Levenberg-Marquardt iteration.

    Parameters:
    - p: array-like
        Current estimate of the model coefficients.
    - dp: array-like
        Update to the model coefficients.
    - shapeFns: str, optional
        Type of shape functions to use. Default is 'Affine'.

    Returns:
    - subset_coefficients: array-like
        Updated model coefficients.

    Raises:
    - ValueError: If the `shapeFns` value is not 'Affine' or 'Quadratic'.
    """

    # Update the model coefficients based on the current estimate and the shape functions
    if shapeFns == 'Affine':
        # w of current estimate of SFPs
        # order of SFP's P[1]: 0  1   2   3  4   5
        #                      u  ux  uy  v  vx  vy
        w_P = np.array([[1+p[1],   p[2], p[0]],
                        [p[4], 1+p[5], p[3]],
                        [0,      0,    1]]).astype('double')

        # w of current delta_p
        w_dP = np.array([[1+dp[1],   dp[2], dp[0]],
                         [dp[4], 1+dp[5], dp[3]],
                         [0,       0,    1]]).astype('double')

        # p coefficients compositional update matrix
        up = np.linalg.solve(w_dP, w_P)

        # extract updated coefficients from p update/up matrix
        subset_coefficients = np.array([up[0, 2],
                                        up[0, 0]-1,
                                        up[0, 1],
                                        up[1, 2],
                                        up[1, 0],
                                        up[1, 1]-1])

    elif shapeFns == 'Quadratic':
        # order of SFP's P[j]: 0  1   2   3    4    5    6  7   8   9    10   11
        #                      u  ux  uy  uxx  uxy  uyy  v  vx  vy  vxx  vxy  vyy
        A1 = 2*p[1] + p[1]**2 + p[0]*p[3]
        A2 = 2*p[0]*p[4] + 2*(1+p[1])*p[2]
        A3 = p[2]**2 + p[0]*p[5]
        A4 = 2*p[0]*(1+p[1])
        A5 = 2*p[0]*p[2]
        A6 = p[0]**2
        A7 = 0.5*(p[6]*p[3] + 2*(1+p[1])*p[7] + p[0]*p[9])
        A8 = p[2]*p[7] + p[1]*p[8] + p[6]*p[4] + p[0]*p[10] + p[8] + p[1]
        A9 = 0.5*(p[6]*p[5] + 2*(1+p[8])*p[2] + p[0]*p[11])
        A10 = p[6] + p[6]*p[1] + p[0]*p[7]
        A11 = p[0] + p[6]*p[2] + p[0]*p[8]
        A12 = p[0]*p[6]
        A13 = p[7]**2 + p[6]*p[9]
        A14 = 2*p[6]*p[10] + 2*p[7]*(1+p[8])
        A15 = 2*p[8] + p[8]**2 + p[6]*p[11]
        A16 = 2*p[6]*p[7]
        A17 = 2*p[6]*(1+p[8])
        A18 = p[6]**2

        # entries of w for update
        dA1 = 2*dp[1] + dp[1]**2 + dp[0]*dp[3]
        dA2 = 2*dp[0]*dp[4] + 2*(1+dp[1])*dp[2]
        dA3 = dp[2]**2 + dp[0]*dp[5]
        dA4 = 2*dp[0]*(1+dp[1])
        dA5 = 2*dp[0]*dp[2]
        dA6 = dp[0]**2
        dA7 = 0.5*(dp[6]*dp[3] + 2*(1+dp[1])*dp[7] + dp[0]*dp[9])
        dA8 = dp[2]*dp[7] + dp[1]*dp[8] + dp[6] * \
            dp[4] + dp[0]*dp[10] + dp[8] + dp[1]
        dA9 = 0.5*(dp[6]*dp[5] + 2*(1+dp[8])*dp[2] + dp[0]*dp[11])
        dA10 = dp[6] + dp[6]*dp[1] + dp[0]*dp[7]
        dA11 = dp[0] + dp[6]*dp[2] + dp[0]*dp[8]
        dA12 = dp[0]*dp[6]
        dA13 = dp[7]**2 + dp[6]*dp[9]
        dA14 = 2*dp[6]*dp[10] + 2*dp[7]*(1+dp[8])
        dA15 = 2*dp[8] + dp[8]**2 + dp[6]*dp[11]
        dA16 = 2*dp[6]*dp[7]
        dA17 = 2*dp[6]*(1+dp[8])
        dA18 = dp[6]**2

        # order of SFP's P[j]: 0,  1,  2,   3,   4,   5,  6,  7,  8,   9,   10,    11
        #                     u   ux  uy  uxx  uxy  uyy  v   vx  vy  vxx   vxy   vyy
        # w of current estimate of SFP's
        w_P = np.array([[1+A1,    A2,        A3,     A4,     A5,   A6],
                        [A7,  1+A8,        A9,    A10,    A11,  A12],
                        [A13,   A14,     1+A15,    A16,    A17,  A18],
                        [0.5*p[3],  p[4],  0.5*p[5], 1+p[1],   p[2], p[0]],
                        [0.5*p[9], p[10], 0.5*p[11],   p[7], 1+p[8], p[6]],
                        [0,     0,         0,      0,      0,    1]
                        ]).astype('double')

        # w of current deltaP
        w_dP = np.array([[1+dA1,    dA2,        dA3,     dA4,     dA5,   dA6],
                         [dA7,  1+dA8,        dA9,    dA10,    dA11,  dA12],
                         [dA13,   dA14,     1+dA15,    dA16,    dA17,  dA18],
                         [0.5*dp[3],  dp[4],  0.5*dp[5], 1+dp[1],   dp[2], dp[0]],
                         [0.5*dp[9], dp[10], 0.5*dp[11],   dp[7], 1+dp[8], dp[6]],
                         [0,      0,          0,       0,       0,     1]
                         ]).astype('double')

        # P update matrix
        up = np.linalg.solve(w_dP, w_P)
        subset_coefficients = np.array([up[3, 5],
                                        up[3, 3]-1,
                                        up[3, 4],
                                        2*up[3, 0],
                                        up[3, 1],
                                        2*up[3, 2],
                                        up[4, 5],
                                        up[4, 3],
                                        up[4, 4]-1,
                                        2*up[4, 0],
                                        up[4, 1],
                                        2*up[4, 2]])

    else:
        raise ValueError(
            'Invalid ShapeFunctions value. Only supported values are: Affine | Quadratic')

    return subset_coefficients


# --------------------------------------------------------------------------------------------
def fastInterpolation(image):
    """
    Setup the interpolation model for the given image.  A special
    interpolation method is called that is optimized for interpolation
    of images (that is regular grids).  This integrator is sinificantly
    faster than the scipy methods, eg map_coordinates.

    Parameters:
    - image (ndarray): The input image to be interpolated.

    Returns:
    - imgInter (interp2d): The interpolation model that can be called in
        the future for interpolation.
    """
    # Image dimensions
    ny = image.shape[0]
    nx = image.shape[1]

    # Setup the interpolation model that can be called in future whenever
    # interpolation is required
    # --------------------------------------------------------------
    # -- Build in interpolator from scipy
    # X = np.arange(0, nx)
    # Y = np.arange(0, ny)
    # imgInter = RectBivariateSpline(Y, X, image, kx=3, ky=3)
    # --------------------------------------------------------------
    imgInter = interp2d([0, 0], [ny-1, nx-1], [1, 1], image,
                        k=3, p=[False, False], c=[True, True], e=[1, 1])

    return imgInter


# --------------------------------------------------------------------------------------------
def loadSettings():
    """
    Load the DIC settings from a configuration file and return them as a dictionary.
    The settings file name is obtained from the constant CONFIG_FILENAME.

    Returns:
        - settings(dict): A dictionary containing the DIC settings.

    Raises:
        - ValueError: If the settings file contains invalid values.

    """
    # Load the configuration file containing the DIC settings
    cp = configparser.ConfigParser(converters={'intlist': lambda x: [
                                   int(i.strip()) for i in x.split(',')] if len(x) > 0 else []})
    cp.read(CONFIG_FILENAME)

    # Setup the settings dictionary
    settings = dict()

    # -- General -----------------------------------------------------------------------------
    settings['DebugLevel'] = cp.getint('General', 'DebugLevel', fallback=0)
    if settings['DebugLevel'] < 0:
        settings['DebugLevel'] = 0
        print('WARNING: Config Parser - DebugLevel set to minimum value of 0')
    if settings['DebugLevel'] > 2:
        settings['DebugLevel'] = 2
        print('WARNING: Config Parser - DebugLevel set to maximum value of 2')

    settings['ImageFolder'] = cp.get(
        'General', 'ImageFolder', fallback='images')
    if not os.path.isdir(settings['ImageFolder']):
        raise ValueError('Config Parser:  Image folder does not exist')
    
    settings['CPUCount'] = cp.get(
        'General', 'CPUCount', fallback='1').lower()
    if settings['CPUCount'] == 'auto':
        settings['CPUCount'] = os.cpu_count()
    else: 
        settings['CPUCount'] = int(settings['CPUCount'])

    if int(settings['CPUCount']) < 1:
        raise ValueError('Config Parser:  CPUCount must be greater than 0')

    settings['DICType'] = cp.get('General', 'DICType', fallback='Planar')
    if settings['DICType'] not in ['Planar', 'Stereo']:
        raise ValueError('Config Parser:  DICType must be Planar or Stereo')

    # -- DICSettings -------------------------------------------------------------------------
    settings['SubsetSize'] = cp.getint(
        'DICSettings', 'SubSetSize', fallback=33)
    if settings['SubsetSize'] < 1:
        raise ValueError('Config Parser:  Subset size must be greater than 0')
    if settings['SubsetSize'] % 2 == 0:
        raise ValueError('Config Parser:  Subset size must be an odd number')

    settings['StepSize'] = cp.getint('DICSettings', 'StepSize', fallback=5)
    if settings['StepSize'] < 1:
        raise ValueError('Config Parser:  Step size must be greater than 0')
    if settings['StepSize'] % 2 == 0:
        raise ValueError('Config Parser:  Step size must be an odd number')

    settings['ShapeFunctions'] = cp.get(
        'DICSettings', 'ShapeFunctions', fallback='Affine')
    if settings['ShapeFunctions'] not in ['Affine', 'Quadratic']:
        raise ValueError(
            'Config Parser:  ShapeFunctions must be Affine or Quadratic')

    settings['ReferenceStrategy'] = cp.get(
        'DICSettings', 'ReferenceStrategy', fallback='Incremental')
    if settings['ReferenceStrategy'] not in ['Incremental', 'Absolute']:
        raise ValueError(
            'Config Parser:  ReferenceStrategy must be Incremental or Absolute')

    settings['StartingPoints'] = cp.getint(
        'DICSettings', 'StartingPoints', fallback=4)
    if settings['StartingPoints'] < 1:
        raise ValueError(
            'Config Parser:  StartingPoints be greater than 0')

    # -- PreProcess --------------------------------------------------------------------------
    settings['GaussianBlurSize'] = cp.getint(
        'PreProcess', 'GaussianBlurSize', fallback=5)
    if settings['GaussianBlurSize'] < 0:
        raise ValueError(
            'Config Parser:  GaussianBlurSize must be greater than or equal to 0')
    if settings['GaussianBlurSize'] % 2 == 0 and settings['GaussianBlurSize'] > 0:
        raise ValueError(
            'Config Parser:  GaussianBlurSize must be an odd number')

    settings['GaussianBlurStdDev'] = cp.getfloat(
        'PreProcess', 'GaussianBlurStdDev', fallback=0.0)
    if settings['GaussianBlurStdDev'] < 0:
        raise ValueError(
            'Config Parser:  GaussianBlurStdDev must be greater than or equal to 0.0')

    # -- ImageSetDefinition ------------------------------------------------------------------
    settings['DatumImage'] = cp.getint(
        'ImageSetDefinition', 'DatumImage', fallback=0)
    if settings['DatumImage'] < 0:
        raise ValueError(
            'Config Parser:  DatumImage must be greater than or equal to 0')

    settings['TargetImage'] = cp.getint(
        'ImageSetDefinition', 'TargetImage', fallback=1)
    if settings['TargetImage'] < settings['DatumImage']:
        raise ValueError(
            'Config Parser:  TargetImage must be greater than DatumImage')

    settings['Increment'] = cp.getint(
        'ImageSetDefinition', 'Increment', fallback=1)
    if settings['Increment'] < 1:
        raise ValueError('Config Parser:  Increment must be greater than 0')

    settings['ROI'] = cp.getintlist(
        'ImageSetDefinition', 'ROI', fallback=[0, 0, 0, 0])
    if min(settings['ROI']) < 0:
        raise ValueError(
            'Config Parser:  ROI values must be greater than or equal to 0')

    settings['BackgroundCutoff'] = cp.getint(
        'ImageSetDefinition', 'BackgroundCutoff', fallback=25)
    if settings['BackgroundCutoff'] < 0:
        raise ValueError(
            'Config Parser:  BackgroundCutoff value must be greater than or equal to 0')

    # -- Optimization ------------------------------------------------------------------------
    # Initialization of optimisation routine
    settings['OptimizationAlgorithm'] = cp.get(
        'Optimisation', 'OptimizationAlgorithm', fallback='IC-GN')
    if settings['OptimizationAlgorithm'] not in ['IC-GN', 'IC-LM']:
        raise ValueError(
            'Config Parser:  OptimizationAlgorithm must be IC-GN or IC-LM')

    settings['MaxIterations'] = cp.getint(
        'Optimisation', 'MaxIterations', fallback=50)
    if settings['MaxIterations'] < 1:
        raise ValueError(
            'Config Parser:  MaxIterations must be greater than 0')

    settings['ConvergenceThreshold'] = cp.getfloat(
        'Optimisation', 'ConvergenceThreshold', fallback=0.0001)
    if settings['ConvergenceThreshold'] < 0:
        raise ValueError(
            'Config Parser:  ConvergenceThreshold must be greater than or equal to 0')

    # Perform Debug output if requested - print all values in dictionary
    if settings['DebugLevel'] > 1:
        print('\nInitial settings:')
        print('---------------------------------')
        [print("  %20s : %s" % (key, value))
         for key, value in settings.items()]

    return settings


# --------------------------------------------------------------------------------------------
def numShapeFnCoeffs(shapeFns='Affine'):
    """
    Calculate the number of coefficients required for the given shape functions.

    Parameters:
    - shapeFns (str): The type of shape functions to use.

    Returns:
    - int: The number of coefficients required for the given shape functions.

    Raises:
    - ValueError: If the provided shapeFns value is invalid.
    """
    if shapeFns == 'Affine':
        return 6
    elif shapeFns == 'Quadratic':
        return 12
    else:
        raise ValueError(
            'Invalid ShapeFunctions value. Only supported values are: Affine | Quadratic')


# --------------------------------------------------------------------------------------------
def calcCZNSSD(nBGCutOff, f, f_mean, f_tilde, g, g_mean, g_tilde):
    """
    Calculate the CZNSSD value for the given subset intensity values.

    Parameters:
        - nBGCutOff (int): The background cutoff value.
        - f (numpy.ndarray): The reference subset intensity values.
        - f_mean (float): The average intensity value of the reference subset.
        - f_tilde (float): The normalized sum of squared differences of the reference subset.
        - g (numpy.ndarray): The deformed subset intensity values.
        - g_mean (float): The average intensity value of the deformed subset.
        - g_tilde (float): The normalized sum of squared differences of the deformed subset.

    Returns:
        - float: The CZNSSD value for the given subset intensity values.
    """
    # Deal with cases where the image is all black
    if (f_mean < nBGCutOff) or (g_mean < nBGCutOff):
        cznssd = CNZSSD_MAX

    # Otherwise calculate the CZNSSD value
    else:
        tmpArray = np.squeeze((f-f_mean)/f_tilde) - \
            np.squeeze((g-g_mean)/g_tilde)
        cznssd = np.dot(tmpArray, tmpArray)

    return cznssd

# -----------------------------------------------------------------------------
def factorCPUCnt(c: int):
    """Calculate the closest two factors of c.
    
    Returns:
      [int, int]: The two factors of c that are closest; in other words, the
        closest two integers for which a*b=c. If c is a perfect square, the
        result will be [sqrt(c), sqrt(c)]; if c is a prime number, the result
        will be [1, c]. The first number will always be the smallest, if they
        are not equal.
    """
    if c//1 != c:
        raise TypeError("c must be an integer.")

    a, b, i = 1, c, 0
    while a < b:
        i += 1
        if c % i == 0:
            a = i
            b = c//a

    return [b, a]

# -----------------------------------------------------------------------------
def __splitMatrix__(matrix, rowSplit, colSplit):
    """
    Splits a matrix into submatrices based on the given number of rows and 
    colums to split into.

    Args:
        matrix (numpy.ndarray): The input matrix to be split.
        rowSplit (int): The number of splits to be made along the rows.
        colSplit (int): The number of splits to be made along the columns.

    Returns:
        list: A list of submatrices obtained after splitting the input matrix.
    """
    subMatrices = []

    # Split the rows
    rows = np.array_split(matrix, rowSplit, axis=0)

    # Now loop through all the rows and split the columns
    for r in rows:
        cols = np.array_split(r, colSplit, axis=1)
        subMatrices.append(cols)

    return subMatrices
