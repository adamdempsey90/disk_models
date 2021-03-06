import numpy as np
import matplotlib.pyplot as plt
import numpy.random as rd
from scipy.interpolate import interp1d
from math import factorial

from disk_density_profiles import *
from disk_external_potentials import *
from disk_other_functions import *
from disk_snapshot import *


def soundspeed(R,csnd0,l,R0):
    return csnd0 * (R/R0)**(-l*0.5)


class disk2d(object):
    def __init__(self, *args, **kwargs):
        #define the properties of the axi-symmetric disk model
        self.sigma_type = kwargs.get("sigma_type")
        self.sigma_disk =  None
        self.sigma_function =  kwargs.get("sigma_function")
        self.sigma_cut = kwargs.get("sigma_cut")
        self.sigma_back = kwargs.get("sigma_back")
        self.sigma_floor = kwargs.get("sigma_floor")
        
        #Temperature profile properties
        self.csndR0 = kwargs.get("csndR0") #reference radius
        self.csnd0 = kwargs.get("csnd0") # soundspeed scaling
        self.l = kwargs.get("l") # temperature profile index

        #thermodynamic parameters
        self.adiabatic_gamma = kwargs.get("adiabatic_gamma")
        self.effective_gamma = kwargs.get("effective_gamma")        
        
        #viscosity
        self.alphacoeff = kwargs.get("alphacoeff")   

        #central object
        self.Mcentral = kwargs.get("Mcentral")
        self.Mcentral_soft = kwargs.get("Mcentral_soft")
        self.quadrupole_correction =  kwargs.get("quadrupole_correction")

        #corrections to density profile by a gap
        self.add_gap = kwargs.get("add_gap")
        if (self.add_gap is True):
            self.gap_center = kwargs.get("gap_center")
            self.gap_width = kwargs.get("gap_width")
            self.gap_depth = kwargs.get("gap_depth")
            self.gap_steep = kwargs.get("gap_steep")

        # other properties
        self.self_gravity = kwargs.get("self_gravity")
        self.central_particle = kwargs.get("central_particle")

        self.constant_accretion = kwargs.get("constant_accretion")

        # axisymmetric perturbations
        self.density_perturbation_function =  kwargs.get("density_perturbation_function")
        
        #set defaults ###############################
        if (self.l is None):
            self.l = 1.0
        if (self.csnd0 is None):
            self.csnd0 = 0.05
        if (self.adiabatic_gamma is None):
            self.adiabatic_gamma = 7.0/5
        if (self.effective_gamma is None):
            self.effective_gamma = 1.0
        if (self.alphacoeff is None):
            self.alphacoeff = 0.01
        if (self.Mcentral is None):
            self.Mcentral = 1.0
        if (self.Mcentral_soft is None):
            self.Mcentral_soft = 0.0
        if (self.quadrupole_correction is None):
            self.quadrupole_correction = 0
        if (self.sigma_type is None):
            self.sigma_type = "powerlaw"
            
        if (self.sigma_type == "powerlaw"):
            self.sigma_disk = powerlaw_disk(**kwargs)
            if (self.csndR0 is None):
                self.csndR0 = self.sigma_disk.R0

        if (self.sigma_type == "powerlaw_zerotorque"):
            self.sigma_disk = powerlaw_zerotorque_disk(**kwargs)
            if (self.csndR0 is None):
                self.csndR0 = self.sigma_disk.R0

        if (self.sigma_type == "similarity"):
            self.sigma_disk = similarity_disk(**kwargs)
            if (self.csndR0 is None):
                self.csndR0 = self.sigma_disk.Rc

        if (self.sigma_type == "powerlaw_cavity"):
            self.sigma_disk = powerlaw_cavity_disk(**kwargs)
            if (self.csndR0 is None):
                self.csndR0 = self.sigma_disk.R_cav
        
        if (self.sigma_type == "similarity_cavity"):
            self.sigma_disk = similarity_cavity_disk(**kwargs)
            if (self.csndR0 is None):
                self.csndR0 = self.sigma_disk.Rc

        if (self.sigma_type is None):
            if (self.sigma_function is not None):
                if not callable(self.sigma_function):
                    print "ERROR: No valid surface density profile provided."
                    exit()
                    
        if (self.self_gravity is None):
            self.self_gravity = False

        if (self.constant_accretion is None):
            self.constant_accretion = False            

        if (self.density_perturbation_function is None):
            self.density_perturbation_function = None
                
        if (self.sigma_cut is None):
            try:
                self.sigma_cut = self.sigma_disk.sigma0 * 1e-7
            except AttributeError:
                self.sigma_cut = None

        if (self.sigma_back is None):
            try:
                self.sigma_back = self.sigma_disk.sigma0 * 1e-7
            except AttributeError:
                self.sigma_back = None
                
        if (self.sigma_floor is None):
            try:
                self.sigma_floor = self.sigma_disk.sigma0 * 1e-7
            except AttributeError:
                self.sigma_floor = None
                
                
        if (self.add_gap is None):
            self.add_gap = False
        if (self.add_gap is True):
            if (self.gap_center is None):
                self.gap_center = 1.0
            if (self.gap_width is None):
                self.gap_width = 0.1
            if (self.gap_depth is None):
                self.gap_depth = 0.01
            if (self.gap_steep is None):
                self.gap_steep = 4


    def sigma_vals(self,rvals):
        if (self.sigma_function is not None) & callable(self.sigma_function):
            sigma = np.vectorize(self.sigma_function)(rvals)
        else:
            sigma = self.sigma_disk.evaluate(rvals)

        return sigma
            
    def evaluate_sigma(self,Rin,Rout,Nvals=1000,scale='log'):
        rvals = self.evaluate_radial_zones(Rin,Rout,Nvals,scale)
        sigma = self.sigma_vals(rvals)
        if (self.add_gap):
            sigma = sigma * gap_profile(rvals,self.gap_center,self.gap_width,self.gap_depth,self.gap_steep)
        try:
            sigma[sigma < self.sigma_floor] = self.sigma_floor
        except TypeError:
            None
        return rvals,sigma
    
    def evaluate_soundspeed(self,Rin,Rout,Nvals=1000,scale='log'):
        rvals = self.evaluate_radial_zones(Rin,Rout,Nvals,scale)
        return rvals,soundspeed(rvals,self.csnd0,self.l,self.csndR0)

    def evaluate_pressure(self,Rin,Rout,Nvals=1000,scale='log'):
        rvals,sigma = self.evaluate_sigma(Rin,Rout,Nvals,scale=scale)
        return rvals, sigma**(self.effective_gamma) * \
            self.evaluate_soundspeed(Rin,Rout,Nvals,scale=scale)[1]**2

    def evaluate_viscosity(self,Rin,Rout,Nvals=1000,scale='log'):
        rvals,csnd =  self.evaluate_soundspeed(Rin,Rout,Nvals,scale=scale)
        Omega_sq = self.Mcentral/rvals**3 * (1 + 3 * self.quadrupole_correction/rvals**2)
        nu = self.alphacoeff * csnd * csnd / np.sqrt(Omega_sq)
        return rvals, nu
    
    def evaluate_pressure_gradient(self,Rin,Rout,Nvals=1000,scale='log'):
        rvals, press = self.evaluate_pressure(Rin,Rout,Nvals,scale=scale)
        _, dPdR = self.evaluate_radial_gradient(press,Rin,Rout,Nvals,scale=scale)
        return rvals,dPdR

    def evaluate_angular_freq_self_gravity(self,Rin,Rout,Nvals=1000,scale='log'):
        rvals, mvals = self.evaluate_enclosed_mass(Rin,Rout,Nvals=2000)
        _ ,sigma = self.evaluate_sigma(Rin,Rout,Nvals,scale=scale)
        '''
        # First guess at the squared angular velocity
        vcircsquared_0 = mvals/rvals
        delta_vcirc,delta_vcirc_old  = 0.0, 1.0e20
        k1 = 1
        x , y = np.meshgrid(rvals,rvals)/Rout
        x[x < y] = 0 # only upper component of the matrix
        while(True):
            integrand1 = sigma[:,None] * x**(2.0*k1+1)
            integrand2 = sigma[:,None] / x**(2.0*k1)
            alpha_k1 = np.pi * (factorial(2*k1)/2.0**(2*k1)/factorial(k1)**2)**2
                
            integral1 = trapz(integrand1,x=xx)
            integral2 = trapz(integrand2,radius/R_disk,1.0)
                
                delta_vcirc+=2.0 * alpha_k1 * G * R_disk *((2*k1+1.0)/(radius/R_disk)**(2*k1+1)* integral1 - 2.0*k1 *(radius/R_disk)**(2*k1) *integral2)
              
                if (k1 > 30):  break
                abstol,reltol = 1.0e-6,1.0e-5
                abserr,relerr = np.abs(delta_vcirc_old-delta_vcirc),np.abs(delta_vcirc_old-delta_vcirc)/np.abs(delta_vcirc_old+vcircsquared_0)
                if (np.abs(delta_vcirc) > abstol/reltol):
                    if (abserr < abstol): break
                else:
                    if (relerr < reltol): break
                    
                delta_vcirc_old = delta_vcirc
                k1 = k1 + 1
     
            selfgravity_vcirc_in_plane = np.append(selfgravity_vcirc_in_plane,vcircsquared_0+delta_vcirc)
        '''
        return rvals, None
       
    def evaluate_rotation_curve(self,Rin,Rout,Nvals=1000,scale='log'):
        rvals = self.evaluate_radial_zones(Rin,Rout,Nvals,scale)
        Omega_sq = self.Mcentral/rvals**3 * (1 + 3 * self.quadrupole_correction/rvals**2)
        if (self.self_gravity):
            _, Omega_sq_sg = self.evaluate_angular_freq_self_gravity(Rin,Rout,Nvals,scale)
            Omega_sq += Omega_sq_sg 
            
        return rvals, np.sqrt(Omega_sq + self.evaluate_pressure_gradient(Rin,Rout,Nvals,scale=scale)[1] / \
            self.evaluate_sigma(Rin,Rout,Nvals,scale=scale)[1]/ rvals)

    def evaluate_radial_velocity(self,Rin,Rout,Nvals=1000,scale='log'):
        if (self.constant_accretion):
            rvals,sigma = self.evaluate_sigma(Rin,Rout,Nvals,scale=scale)
            rvel = -self.constant_accretion / 2.0 / np.pi / rvals / sigma
            # correct for extremely high values
            rvel[rvals < 3 * Rin] *= np.exp(-(2*Rin/rvals[rvals < 3 * Rin])**6)
            return rvals, rvel
        else:
            return self.evaluate_radial_velocity_viscous(Rin,Rout,Nvals,scale=scale)

    def evaluate_radial_velocity_viscous(self,Rin,Rout,Nvals=1000,scale='log'):
        rvals = self.evaluate_radial_zones(Rin,Rout,Nvals,scale)
        Omega = np.sqrt(self.Mcentral/rvals**3 * (1 + 3 * self.quadrupole_correction/rvals**2))
        sigma = (self.evaluate_sigma(Rin,Rout,Nvals,scale)[1])
        _, dOmegadR = self.evaluate_radial_gradient(Omega,Rin,Rout,Nvals,scale=scale)
        
        func1 = (self.evaluate_viscosity(Rin,Rout,Nvals,scale)[1])*\
            (self.evaluate_sigma(Rin,Rout,Nvals,scale)[1])*\
            rvals**3*dOmegadR
        _, dfunc1dR = self.evaluate_radial_gradient(func1,Rin,Rout,Nvals,scale=scale)
        func2 = rvals**2 * Omega
        _, dfunc2dR = self.evaluate_radial_gradient(func2,Rin,Rout,Nvals,scale=scale)

        velr = dfunc1dR / rvals / sigma / dfunc2dR
        if (self.sigma_floor is not None):
            velr[sigma <= self.sigma_floor] = 0


        return rvals,velr

        
    def evaluate_radial_gradient(self,quantity,Rin,Rout,Nvals=1000,scale='log'):
        rvals = self.evaluate_radial_zones(Rin,Rout,Nvals,scale)
        if (scale == 'log'):
            dQdlogR = np.gradient(quantity)/np.gradient(np.log10(rvals))
            dQdR = dQdlogR/rvals/np.log(10)
        elif (scale == 'linear'):
            dQdR = np.gradient(quantity)/np.gradient(rvals)
        return rvals,dQdR

    def evaluate_radial_zones(self,Rin,Rout,Nvals=1000,scale='log'):
        if (scale == 'log'):
            rvals = np.logspace(np.log10(Rin),np.log10(Rout),Nvals)
        elif (scale == 'linear'):
            rvals = np.linspace(Rin,Rout,Nvals)
        else: 
            print "[error] scale type ", scale, "not known!"
            sys.exit()
        return rvals

    def evaluate_enclosed_mass(self,Rin,Rout,Nvals=1000,scale='log'):
        rvals = self.evaluate_radial_zones(Rin,Rout,Nvals,scale)
        def mass_integrand(R):
            sigma = self.sigma_vals(R)
            if (self.sigma_floor is not None):
                if (sigma < self.sigma_floor) : sigma = self.sigma_floor
            return sigma * R * 2 * np.pi
        mass = [quad(mass_integrand,0.0,R)[0] for R in rvals]
        return rvals, mass

    
    def compute_disk_mass(self,Rin,Rout):
        __, mass =  self.evaluate_enclosed_mass(Rin,Rout,Nvals=2)
        return mass[1]


    def add_perturbation(self,function):
        if callable(function):
            self.density_perturbation_function = function
        else:
            print "ERROR: Perturbation function provided not callable"
            
            
class disk_mesh2d(object):
    def __init__(self, *args, **kwargs):

        self.mesh_type=kwargs.get("mesh_type")
        self.Rin = kwargs.get("Rin")
        self.Rout = kwargs.get("Rout")
        self.Rbreak = kwargs.get("Rbreak")
        self.NR = kwargs.get("NR")
        self.Nphi = kwargs.get("Nphi")
        self.NR1 = kwargs.get("NR1")
        self.Nphi1 = kwargs.get("Nphi1")
        self.NR2 = kwargs.get("NR2")
        self.Nphi2 = kwargs.get("Nphi2")
        self.Nphi_inner_bound = kwargs.get("Nphi_inner_bound")
        self.Nphi_outer_bound = kwargs.get("Nphi_outer_bound")
        self.BoxSize = kwargs.get("BoxSize")
        self.mesh_alignment = kwargs.get("mesh_alignment")
        self.N_inner_boundary_rings = kwargs.get("N_inner_boundary_rings")
        self.N_outer_boundary_rings = kwargs.get("N_outer_boundary_rings") 
        self.fill_box = kwargs.get("fill_box")
        self.fill_center = kwargs.get("fill_center")
        self.fill_box_Nmax = kwargs.get("fill_box_Nmax")

        
        # set default values
        if (self.mesh_type is None):
            self.mesh_type="polar"
        if (self.Rin is None):
            self.Rin = 1
        if (self.Rout is None):
            self.Rout = 10
        if (self.NR is None):
            self.NR = 800
        if (self.Nphi is None):
            self.Nphi = 600
        if (self.Nphi_inner_bound is None):
            self.Nphi_inner_bound = self.Nphi
        if (self.Nphi_outer_bound is None):
            self.Nphi_outer_bound = self.Nphi
        if (self.N_inner_boundary_rings is None):
            self.N_inner_boundary_rings = 1
        if (self.N_outer_boundary_rings is None):
            self.N_outer_boundary_rings = 1            
            
        if (self.BoxSize is None):
            self.BoxSize = 1.2 * 2* self.Rout
            
        if (self.fill_box is None):
            self.fill_box = False
        if (self.fill_center is None):
            self.fill_center = False
        if (self.fill_box_Nmax is None):
            self.fill_box_Nmax = 64

        self.Ncells = self.NR * self.Nphi
            
    def create(self,*args,**kwargs):
        
        if (self.mesh_type == "polar"):

            if (self.Rbreak is None) & (self.NR1 is None) & (self.Nphi1 is None) \
               & (self.NR2 is None) & (self.Nphi2 is None):
                
                rvals = np.logspace(np.log10(self.Rin),np.log10(self.Rout),self.NR+1)
                rvals = rvals[:-1] + 0.5 * np.diff(rvals)
                self.deltaRin,self.deltaRout = rvals[1]-rvals[0],rvals[-1]-rvals[-2]
                # Add cells outside the inner boundary
                for kk in range(self.N_inner_boundary_rings): rvals=np.append(rvals[0]-self.deltaRin, rvals)
                # Add cells outside the outer boundary
                for kk in range(self.N_outer_boundary_rings): rvals=np.append(rvals,rvals[-1]+self.deltaRout)
                
                phivals = np.linspace(0,2*np.pi,self.Nphi+1)
                R,phi = np.meshgrid(rvals,phivals)
                
                if (self.mesh_alignment == "interleaved"):
                    phi[:-1,4*self.N_inner_boundary_rings:-2*self.N_outer_boundary_rings:2] = phi[:-1,4*self.N_inner_boundary_rings:-2*self.N_outer_boundary_rings:2] + 0.5*np.diff(phi[:,4*self.N_inner_boundary_rings:-2*self.N_outer_boundary_rings:2],axis=0)
                    
                phi = phi[:-1,:]
                R = R[:-1,:]
                rvals = R.mean(axis=0)
            
                R, phi = R.flatten(),phi.flatten()

            elif (self.Rbreak is not None) & (self.NR1 is not None) & (self.Nphi1 is not None) \
                 & (self.NR2 is not None) & (self.Nphi2 is not None):

                rvals1 = np.logspace(np.log10(self.Rin),np.log10(self.Rbreak),self.NR1+1)
                rvals1 = rvals1[:-1] + 0.5 * np.diff(rvals1)
                phivals1 = np.linspace(0,2*np.pi,self.Nphi1+1)
                R1,phi1 = np.meshgrid(rvals1,phivals1)
                if (self.mesh_alignment == "interleaved"):
                    phi1[:-1,::2] = phi1[:-1,::2] + 0.5 * np.diff(phi1[:,::2],axis=0)
                
                rvals2 = np.logspace(np.log10(self.Rbreak),np.log10(self.Rout),self.NR2+1)
                rvals2 = rvals2[:-1] + 0.5 * np.diff(rvals2)
                phivals2 = np.linspace(0,2*np.pi,self.Nphi2+1)
                R2,phi2 = np.meshgrid(rvals2,phivals2)
                if (self.mesh_alignment == "interleaved"):
                    phi2[:-1,::2] = phi2[:-1,::2] + 0.5 * np.diff(phi2[:,::2],axis=0)

                R = np.append(R1.flatten(),R2.flatten())
                phi = np.append(phi1.flatten(),phi2.flatten())
                plt.plot(R,phi,'k.')
                plt.axis([self.Rin,self.Rout,0,2*np.pi])
                plt.show()
                self.deltaRin = np.sort(np.unique(R))[1] - np.sort(np.unique(R))[0]
                self.deltaRout = np.sort(np.unique(R))[-1] - np.sort(np.unique(R))[-2]
                
            if (self.Nphi_inner_bound != self.Nphi):
                rvals_add = rvals[rvals <= rvals[2 * self.N_inner_boundary_rings - 1]]
                rvals_add = np.linspace(rvals_add[0],rvals_add[-1],2 * self.N_inner_boundary_rings)
                ind = R[:] > np.round(rvals[1],4)
                R, phi = R[ind], phi[ind]
                R_add, phi_add = np.meshgrid(rvals_add, np.linspace(0, 2*np.pi, self.Nphi_inner_bound + 1))
                R = np.append(R,R_add[:-1,:].flatten())
                phi = np.append(phi,phi_add[:-1,:].flatten())
                                
            if (self.Nphi_outer_bound != self.Nphi):
                rvals_add = np.sort(np.unique(R))[-2 * self.N_outer_boundary_rings:]
                #rvals[rvals >= rvals[-2 * self.N_outer_boundary_rings]]
                rvals_add = np.linspace(rvals_add[0],rvals_add[-1],2 * self.N_outer_boundary_rings)
                ind = R[:] < rvals_add.min()#-2 * self.N_outer_boundary_rings]
                R, phi = R[ind], phi[ind]
                R_add, phi_add = np.meshgrid(rvals_add, np.linspace(0, 2*np.pi, self.Nphi_outer_bound + 1))
                R = np.append(R,R_add.flatten())
                phi = np.append(phi,phi_add.flatten())



                
            if (self.fill_box == True):
                rvals = np.array([R.max()+self.deltaRout,R.max()+2* self.deltaRout])
                phivals = np.arange(0,2*np.pi,2*np.pi/(0.5*self.Nphi))
                Rback,phiback = np.meshgrid(rvals,phivals)
                R = np.append(R,Rback.flatten())
                phi = np.append(phi,phiback.flatten())

                extent = 0.5 * self.BoxSize - 2*self.deltaRout
                interval = 4*self.deltaRout
                if (self.BoxSize/interval > self.fill_box_Nmax):
                    interval = self.BoxSize/self.fill_box_Nmax
                xback,yback = np.meshgrid(np.arange(-extent + 0.5 * interval, extent,interval),
                                          np.arange(-extent + 0.5 * interval, extent,interval))
                xback,yback = xback.flatten(),yback.flatten()
                Rback = np.sqrt(xback**2+yback**2)
                phiback = np.arctan2(yback,xback)
                ind = Rback > R.max()+2.5 * self.deltaRout
                Rback, phiback = Rback[ind], phiback[ind]

                R = np.append(R,Rback)
                phi = np.append(phi,phiback)

            if (self.fill_center == True):
                rvals = np.array([R.min()-3* self.deltaRin,R.min()-self.deltaRin])
                phivals = np.arange(0,2*np.pi,2*np.pi/(0.5*self.Nphi))
                Rcenter,phicenter = np.meshgrid(rvals,phivals)
                R = np.append(R,Rcenter.flatten())
                phi = np.append(phi,phicenter.flatten())

                extent = self.Rin 
                interval = 3* self.deltaRin
                xcenter,ycenter= np.meshgrid(np.arange(-extent + 0.5 * interval, extent,interval),
                                          np.arange(-extent + 0.5 * interval, extent,interval))
                xcenter,ycenter = xcenter.flatten(),ycenter.flatten()
                Rcenter = np.sqrt(xcenter**2+ycenter**2)
                phicenter = np.arctan2(ycenter,xcenter)
                ind = Rcenter < R.min() - 2* self.deltaRin
                Rcenter, phicenter = Rcenter[ind], phicenter[ind]

                R = np.append(R,Rcenter)
                phi = np.append(phi,phicenter)

            plt.plot(R,phi,'k.')
            plt.axis([self.Rin,self.Rout,0,2*np.pi])
            plt.show()
            return R,phi

'''
class snapshot():

    def __init__(self,*args,**kwargs):
        self.pos=kwargs.get("pos")
        self.vel=kwargs.get("vel")
        self.dens=kwargs.get("dens")
        self.utherm=kwargs.get("utherm")
        self.ids=kwargs.get("ids")

    def create(self,disk,disk_mesh):
        
        R,phi,dens,vphi,vr,press,ids = self.assign_primitive_variables(disk,disk_mesh)
        
        self.load(R,phi,dens,vphi,vr,press,ids,disk_mesh.BoxSize,disk.adiabatic_gamma)

    def load(self,R,phi,dens,vphi,vr,press,ids,BoxSize,adiabatic_gamma):
        
        x = R * np.cos(phi) + 0.5 * BoxSize
        y = R * np.sin(phi) + 0.5 * BoxSize
        z = np.zeros(x.shape[0])
        
        vx = vr * np.cos(phi) - vphi * np.sin(phi)
        vy = vr * np.sin(phi) + vphi * np.cos(phi)
        vz = np.zeros(vx.shape[0])
        
        self.dens = dens
        self.pos = np.array([x,y,z]).T
        self.vel = np.array([vx,vy,vz]).T
        self.utherm = press/self.dens/(adiabatic_gamma - 1)
        self.ids = ids
    
    
     

    def extract(self,index):
        self.pos=self.pos[index,:]
        self.vel=self.vel[index,:]
        self.dens=self.dens[index]
        self.utherm=self.utherm[index]
        self.ids=self.ids[index]

    def append(self,snapshot):
        self.pos=np.concatenate([self.pos,snapshot.pos],axis=0)
        self.vel=np.concatenate([self.vel,snapshot.vel],axis=0)
        self.dens=np.append(self.dens,snapshot.dens)
        self.utherm=np.append(self.utherm,snapshot.utherm)
        self.ids=np.append(self.ids,snapshot.ids)
        self.ids[self.ids > 0] = np.arange(1,1+self.ids[self.ids > 0].shape[0])

    def write_snapshot(self,disk,disk_mesh,filename="disk.dat.hdf5",time=0):
        
       
        
        Ngas = self.pos.shape[0]
        f=ws.openfile(filename)
        npart=np.array([Ngas,0,0,0,0,0], dtype="uint32")
        massarr=np.array([0,0,0,0,0,0], dtype="float64")
        header=ws.snapshot_header(npart=npart, nall=npart, massarr=massarr, time=time,
                              boxsize=disk_mesh.BoxSize, double = np.array([1], dtype="int32"))

        
        ws.writeheader(f, header)
        ws.write_block(f, "POS ", 0, self.pos)
        ws.write_block(f, "VEL ", 0, self.vel)
        ws.write_block(f, "MASS", 0, self.dens)
        ws.write_block(f, "U   ", 0, self.utherm)
        ws.write_block(f, "ID  ", 0, self.ids)
        ws.closefile(f)
        

    def summary(self,disk,disk_mesh):

        print("Created snapshot with NR=%i, Nphi=%i and a total of Ncells=%i" \
              % (disk_mesh.NR,disk_mesh.Nphi,self.pos.shape[0]))
        print("SUMMARY:")
        print("\t Rin=%f Rout=%f" %( disk_mesh.Rin, disk_mesh.Rout))
'''


if __name__=="__main__":


    d = disk()
    m = disk_mesh(d)
    m.create()
    ss = snapshot()
    ss.create(d,m)
    ss.write_snapshot(d,m)
    
