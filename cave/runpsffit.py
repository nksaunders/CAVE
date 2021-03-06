import aperturefit as af
import numpy as np
import matplotlib.pyplot as pl
import psffit as pf
import simulateK2
from datetime import datetime
from tqdm import tqdm
from everest import detrender


class PSFrun(object):

    def __init__(self):

        # self.ID = input("Enter EPIC ID: ")
        self.ID = 205998445
        self.startTime = datetime.now()

        sK2 = simulateK2.Target(int(self.ID), 355000.0)
        self.trn = sK2.Transit()
        print("Simulating K2 target...")
        self.fpix, target, self.ferr = sK2.GeneratePSF()
        self.t = np.linspace(0,90,len(self.fpix))

        self.aft = af.ApertureFit(self.trn)
        c_pix, c_det = self.aft.Crowding(self.fpix,target)


        self.xpos = sK2.xpos
        self.ypos = sK2.ypos
        self.fit = pf.PSFFit(self.fpix,self.ferr)

    def FindFit(self):

        amp = [345000.0,(352000.0 / 2)]
        x0 = [2.6,3.7]
        y0 = [2.3,4.2]
        sx = [.4]
        sy = [.6]
        rho = [0.01]
        background = [1000]
        index = 200
        guess = np.concatenate([amp,x0,y0,sx,sy,rho,background])
        answer = self.fit.FindSolution(guess, index=index)
        invariant_vals = np.zeros((len(answer)))
        self.n_fpix = np.zeros((len(self.fpix),5,5))
        self.subtracted_fpix = np.zeros((len(self.fpix),5,5))


        for i,v in enumerate(answer):
            if i == 0:
                invariant_vals[i] = 0
            elif i == 2:
                invariant_vals[i] = v - self.xpos[index]
            elif i == 4:
                invariant_vals[i] = v - self.ypos[index]
            else:
                invariant_vals[i] = v

        print("Subtracting neighbor...")
        for cadence in tqdm(range(len(self.fpix))):
            n_vals = np.zeros((len(invariant_vals)))
            for i,v in enumerate(invariant_vals):
                if i == 2:
                    n_vals[i] = v + self.xpos[cadence]
                elif i == 4:
                    n_vals[i] = v + self.ypos[cadence]
                else:
                    n_vals[i] = v

            neighbor_cad = self.fit.PSF(n_vals)
            self.n_fpix[cadence] = neighbor_cad
            self.subtracted_fpix[cadence] = self.fpix[cadence] - neighbor_cad


        self.answerfit = self.fit.PSF(answer)
        self.neighborfit = self.fit.PSF(invariant_vals)
        self.subtraction = self.answerfit - self.neighborfit
        self.residual = self.fpix[200] - self.answerfit
        self.subtracted_flux = self.aft.FirstOrderPLD(self.subtracted_fpix)[0]
        return self.subtraction

    def Plot(self):

        fig, ax = pl.subplots(1,3, sharey=True)
        fig.set_size_inches(17,5)

        meanfpix = np.mean(self.fpix,axis=0)
        ax[0].imshow(self.fpix[200],interpolation='nearest',origin='lower',cmap='viridis',vmin=np.min(self.answerfit),vmax=np.max(self.answerfit));
        ax[1].imshow(self.answerfit,interpolation='nearest',origin='lower',cmap='viridis',vmin=np.min(self.answerfit),vmax=np.max(self.answerfit));
        ax[2].imshow(self.subtraction,interpolation='nearest',origin='lower',cmap='viridis',vmin=np.min(self.answerfit),vmax=np.max(self.answerfit));
        ax[0].set_title('Data');
        ax[1].set_title('Model');
        ax[2].set_title('Neighbor Subtraction');
        ax[1].annotate(r'$\mathrm{Max\ Residual\ Percent}: %.4f $' % (np.max(np.abs(self.residual))/np.max(self.fpix[200])),
                        xy = (0.05, 0.05),xycoords='axes fraction',
                        color='w', fontsize=12);


        unsub_flux = self.aft.FirstOrderPLD(self.fpix)[0]
        fig, ax = pl.subplots(2,1)
        ns_depth = self.aft.RecoverTransit(self.subtracted_flux)
        ax[0].plot(self.t,np.mean(unsub_flux)*self.trn,'r')
        ax[0].plot(self.t,unsub_flux,'k.')
        ax[0].set_title('No Subtraction, 1st Order PLD')
        ax[1].plot(self.t,np.mean(self.subtracted_flux)*self.trn,'r')
        ax[1].plot(self.t,self.subtracted_flux,'k.')
        ax[1].set_title('Neighbor Subtraction, 1st Order PLD')

        ax[0].annotate(r'$\mathrm{Recovered\ Depth}: %.4f$' % (self.aft.RecoverTransit(unsub_flux)),
                        xy = (0.05, 0.05),xycoords='axes fraction',
                        color='k', fontsize=12);
        ax[1].annotate(r'$\mathrm{Recovered\ Depth}: %.4f$' % (ns_depth),
                        xy = (0.05, 0.05),xycoords='axes fraction',
                        color='k', fontsize=12);

        print("Run time:")
        print(datetime.now() - self.startTime)
        print("RTD: %.4f,   Subtracted RTD: %.4f" % (self.aft.RecoverTransit(unsub_flux),ns_depth))
        pl.show()

r = PSFrun()
sub = r.FindFit()
r.Plot()
