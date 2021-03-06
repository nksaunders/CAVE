import numpy as np
import matplotlib.pyplot as pl
import everest
from everest.math import SavGol
from intrapix import PixelFlux
import simulateK2 as sk
from random import randint
from astropy.io import fits
import pyfits
from everest import Transit
import k2plr
from k2plr.config import KPLR_ROOT
from everest.config import KEPPRF_DIR
import os
from sklearn.decomposition import PCA
from itertools import combinations_with_replacement as multichoose

class ApertureFit(object):

    def __init__(self, trn):

        # initialize variables
        self.trn = trn

        # mask transits
        self.naninds = np.where(self.trn < 1)
        self.M = lambda x: np.delete(x, self.naninds, axis = 0)

    def compute_crowding(self, fpix, target):
        '''
        Calculates and returns pixel crowding (c_pix) and detector crowding (c_det)
        Crowding defined by F_target / F_total
        '''

        # crowding parameter for each pixel
        self.c_pix = np.zeros((len(fpix),5,5))

        # crowding parameter for entire detector
        self.c_det = np.zeros((len(fpix)))

        for c in range(len(fpix)):
            for i in range(5):
                for j in range(5):
                    if np.isnan(fpix[c][i][j]):
                        continue
                    else:
                        self.c_pix[c][i][j] = target[c][i][j] / fpix[c][i][j]

            self.c_det[c] = np.nansum(target[c]) / np.nansum(fpix[c])

        return self.c_det, self.c_pix

    def perform_PLD(self, fpix, motion, mask):
        '''
        Perform first order PLD on a light curve
        Returns: detrended light curve, raw light curve
        '''

        outM = lambda x: np.delete(x,mask,axis=0)
        # hack
        naninds = np.where(np.isnan(fpix))
        fpix[naninds] = 0

        #  generate flux light curve
        fpix = outM(fpix)
        fpix_rs = fpix.reshape(len(fpix),-1)
        flux = np.sum(fpix_rs,axis=1)

        # First order PLD
        f1 = fpix_rs / flux.reshape(-1,1)
        pca = PCA(n_components = 20)
        X1 = pca.fit_transform(f1)

        # Second order PLD
        f2 = np.product(list(multichoose(f1.T, 2)), axis = 1).T
        pca = PCA(n_components = 10)
        X2 = pca.fit_transform(f2)

        X10 = np.load('masks/larger_aperture/X10_%i.npz'%motion)['X']
        X10crop = []
        for i in X10:
            X10crop.append(i[1:])
        X10crop = np.array(outM(X10crop))

        # Combine them and add a column vector of 1s for stability
        X3 = np.hstack([np.ones(X1.shape[0]).reshape(-1, 1), X1, X2])
        X = np.concatenate((X3,X10crop),axis=1)

        # np.savez(('masks/larger_aperture/X10_%i'%motion),X=X)
        MX = self.M(X)

        A = np.dot(MX.T, MX)
        B = np.dot(MX.T, self.M(flux))
        C = np.linalg.solve(A, B)

        # compute detrended light curve
        model = np.dot(X, C)

        detrended = flux - model + np.nanmean(flux)

        # folded
        # D = (detrended - np.dot(C[1:], X[:,1:].T) + np.nanmedian(detrended)) / np.nanmedian(detrended)
        # T = (t - 5.0 - per / 2.) % per - per / 2.

        return detrended, flux

    def recover_transit(self, lightcurve_in):
        '''
        Solve for depth of transit in detrended lightcurve
        Returns: recovered depth of transit in light curve
        '''

        detrended = lightcurve_in
        depth = 0.01

        # normalize transit model
        transit_model = (self.trn - 1) / depth

        # create relevant arrays
        X = np.array(([],[]), dtype = float).T
        for i in range(len(detrended)):
            rowx = np.array([[1.,transit_model[i]]])
            X = np.vstack((X, rowx))
        Y = detrended / np.nanmedian(detrended)

        # solve for recovered transit depth
        A = np.dot(X.T, X)
        B = np.dot(X.T, Y)
        C = np.linalg.solve(A, B)
        rec_depth = C[1]

        return rec_depth

    def perform_aperture_PLD(self, aperture, fpix):
        '''
        Performs PLD on only a desired region of the detector
        Takes parameters: light curve (fpix), and aperture containing desired region
        Returns: aperture, detrendended light curve, raw light curve in aperture
        '''

        aperture = [aperture for i in range(len(fpix))]

        fpix_rs = (fpix*aperture).reshape(len(fpix),-1)
        fpix_ap = np.zeros((len(fpix),len(np.delete(fpix_rs[0],np.where(np.isnan(fpix_rs[0]))))))

        for c in range(len(fpix_rs)):
            naninds = np.where(np.isnan(fpix_rs[c]))
            fpix_ap[c] = np.delete(fpix_rs[c],naninds)

        flux = np.sum(fpix_ap,axis=1)
        X = fpix_ap / flux.reshape(-1,1)
        MX = self.M(fpix_ap) / self.M(flux).reshape(-1,1)

        # perform first order PLD
        A = np.dot(MX.T, MX)
        B = np.dot(MX.T, self.M(flux))
        C = np.linalg.solve(A, B)

        # compute detrended light curve
        model = np.dot(X, C)
        detrended = flux - model + np.nanmean(flux)

        return aperture, detrended, flux
