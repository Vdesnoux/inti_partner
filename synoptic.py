# -*- coding: utf-8 -*-
"""
Created on Mon Aug 25 18:47:09 2025

@author: valer
"""

import numpy as np
import matplotlib.pyplot as plt
import cv2 as cv2
import astropy.time
import math
import datetime
from scipy.interpolate import UnivariateSpline

"""
Module de construction de carte synoptique à partir de n tableau image
Appel par :
    carte_syno = syn.make_synoptic (images, B0_list, L0_list, xc_list, yc_list, R_list, norm=20000)
    carte_crop, long_1, long_2, lat_1, lat_2 = syn.format_carte (carte_syno, L0_list, norm=20000)
images : tableau d'images
B0_list : liste des B0 de chque image de la liste images, en degré
L0_list : liste des L0 de chaque image de la liste images, en degré
xc_list, yc_list, R_list : liste des coord centre et rayon du disque dans chaque image de la liste images
norm : valeur moyenne de la carte finale

"""


def pix_to_helio_coords (x_c, y_c, R, B0_deg, L0_deg, ih, iw) :
    """
    Retourne lat & long (degrés) et mask pour une image ih, nyiw
    Image orientée (angle P)
    """

    # Test sur _11_17_45
    B0= np.deg2rad(B0_deg)
    L0 = np.deg2rad(L0_deg)

    x=np.arange(iw)
    y=np.arange(ih)
    x_pixels, y_pixels = np.meshgrid(x,y, indexing='xy')

    x_ = x_pixels-x_c
    y_ = y_pixels-y_c
    r = np.sqrt(x_**2+y_**2)/ R # calcul distance pixel x,y versus centre
    mask = r<=1.0 # mask du disque solaire

    latitude = np.full ((ih,iw), np.nan, dtype=np.float64) # prerempli avec nan
    longitude = np.full ((ih,iw), np.nan, dtype=np.float64)

    # valeurs valides en 1D
    r_valid = r[mask]   # tableau des distances pour pixels dans disque
    x_valid = x_[mask]  # valeurs x, y relatives au centre dans le disque
    y_valid = y_[mask]  # valeurs x, y relatives au centre dans le disque

    rho_s = np.arcsin (r_valid)
    psi = np.arctan2(x_valid, -y_valid)
    sin_theta = np.sin (B0) * np.cos(rho_s)+np.cos(B0)*np.sin(rho_s)*np.cos(psi)
    theta = np.arcsin(sin_theta)

    num = np.sin(rho_s) * np.sin (psi)
    den = np.cos(rho_s) * np.cos(B0)- np.sin(rho_s)*np.sin(B0)*np.cos(psi)
    delta_phi = np.arctan2 (num, den)

    phi = np.mod (L0+delta_phi, 2*np.pi)
    latitude[mask] = np.rad2deg (theta)
    longitude[mask] = np.rad2deg(phi)

    return latitude, longitude, mask, x_pixels, y_pixels

def projection_une_image (image, latitude, longitude, mask, x_pixels, y_pixels, x_c, y_c, R, n_lat=180, n_long= 360) :
    """
    Projection: on mappe chaque pixel du disque sur un indice de grille en lat et long
    on trie et on garde la meilleure contribution par case (poids minimal)
    Retour : carte (n_lat, n_long) et poids (n_lat, n_long)
    """

    # grille lat/long
    lat_vals = np.linspace(-90, 90, n_lat)
    long_vals = np.linspace(0,360, n_long)
    dlat = lat_vals[1] - lat_vals[0]
    dlong = long_vals[1] - long_vals[0]
    
    # extrait les pixels valides
    lat_1D = latitude [mask]
    long_1D = longitude [mask]
    vals_1D = image[mask]

    # indices entiers sur la grille
    lat_idx = np.floor((lat_1D-lat_vals[0]) / dlat).astype (np.uint32)
    long_idx = np.floor((long_1D-long_vals[0]) / dlong).astype (np.uint32)

    # garder indices dans limites (sécurité)
    valid_idx_mask = (lat_idx >= 0) & (lat_idx < n_lat) & (long_idx >=0 ) & (long_idx < n_long)
    if not np.all(valid_idx_mask) :
        lat_idx = lat_idx[valid_idx_mask]
        long_idx = long_idx[valid_idx_mask]
        vals_1D = vals_1D[valid_idx_mask]

    # indice plat
    flat_idx = lat_idx.astype(np.int64) * np.int64(n_long) +long_idx.astype(np.int64)

    # poids : distance normalisée au centre (poids petit = meilleur)
    r_pix = np.sqrt((x_pixels-x_c)**2+(y_pixels-y_c)**2) / float(R)
    poids_1D = r_pix[mask]
    if not np.all (valid_idx_mask) :
        poids_1D = poids_1D[valid_idx_mask]

    # tri par (flat_idx, poids)
    order = np.lexsort ((poids_1D, flat_idx))
    flat_sorted = flat_idx[order]
    vals_sorted = vals_1D[order]
    poids_sorted = poids_1D[order]

    # trouver la première occurence de chaque flat_idx (meilleur poids du au tri)
    # np.unique sur flat_sorted avec return_index renvoie index du premier element de chaque groupe
    unique_flat, first_pos = np.unique (flat_sorted, return_index=True)

    best_flat = unique_flat # indices plats
    best_vals = vals_sorted[first_pos]
    best_poids = poids_sorted[first_pos]

    # construit tableau plat de sortie
    carte_flat = np.full ((n_lat *n_long), np.nan, dtype=np.float64)
    poids_flat = np.full ((n_lat *n_long), np.inf, dtype=np.float64)

    carte_flat[best_flat] = best_vals
    poids_flat[best_flat] = best_poids

    # reshape
    carte = carte_flat.reshape(n_lat, n_long)
    poids = poids_flat.reshape(n_lat, n_long)

    return carte, poids

def carte_synoptique (images, B0_list, L0_list, xc_list, yc_list, R_list, n_lat=180, n_long=360) :
    """
    construit carte synomptique avec images
    """
    carte_globale =  np.full ((n_lat ,n_long), np.nan, dtype=np.float64)
    poids_globaux =  np.full ((n_lat ,n_long), np.inf, dtype=np.float64)

    for img, B0, L0, x_c, y_c, R in zip(images, B0_list, L0_list, xc_list, yc_list, R_list) :
        ny, nx = img.shape

        lat, long, mask, x_pix, y_pix = pix_to_helio_coords (x_c, y_c, R, B0, L0, ny, nx)
        carte_part, poids_part = projection_une_image (img, lat, long, mask, x_pix, y_pix, x_c, y_c, R,
                                                       n_lat=n_lat, n_long=n_long)

        # sécurité
        assert carte_part.shape == (n_lat, n_long)
        assert poids_part.shape == (n_lat, n_long)
        assert poids_globaux.shape == (n_lat, n_long)
        assert carte_globale.shape == (n_lat, n_long)

        # fusion
        better = (~np.isnan (carte_part)) & (poids_part < poids_globaux)
        carte_globale[better] = carte_part[better]
        poids_globaux [better] = poids_part[better]
    
    return carte_globale, poids_globaux

def remove_limb_darkening(img, x_c, y_c, R, nbins=100, smooth=10):
    ny, nx = img.shape
    yy, xx = np.meshgrid(np.arange(ny), np.arange(nx), indexing='ij')
    r = np.sqrt((xx - x_c)**2 + (yy - y_c)**2) / float(R)  # 0..1
    mask = r <= 0.95

    r_vals = r[mask]
    img_vals = img[mask]

    # bins radiaux
    bins = np.linspace(0, 1.0, nbins)
    inds = np.digitize(r_vals, bins) - 1
    medians = np.array([np.nanmedian(img_vals[inds == i]) if np.any(inds==i) else np.nan for i in range(len(bins))])

    # garder bins valides
    good = ~np.isnan(medians)
    if good.sum() < 10:
        return img.copy()

    # spline lisse du profil radial
    spline = UnivariateSpline(bins[good], medians[good], s=smooth)
    profile = spline(r)  # profil évalué pour chaque pixel

    # éviter division par zéro
    profile = np.where(profile <= 0, 1.0, profile)

    img_corr = img.astype(float) / profile
    return img_corr

def make_synoptic (images, B0_list, L0_list, xc_list, yc_list, R_list, norm) :
    images2 =[]
    for img, x_c, y_c, R  in zip(images, xc_list, yc_list, R_list) :
        
        nx, ny = img.shape
        
        yy,xx = np.meshgrid (np.arange(ny),np.arange(nx), indexing='ij')
        r= np.sqrt((xx - x_c)**2 + (yy-y_c)**2)
        mask_disk = r <=R 
        
        
        img = remove_limb_darkening(img, x_c, y_c, R)       
        med = np.nanmean(img[mask_disk])
        if med == 0 or np.isnan(med):
            pass
        else :
            img = (img.astype(float) / float(med))*norm
        images2.append(img)
  
    carte, poids = carte_synoptique (images2, B0_list, L0_list, xc_list, yc_list, R_list, n_lat=360, n_long=720)
    
    carte = np.nan_to_num(carte, nan=0.0)
    
    return  carte

def format_carte (carte, L0_list, norm) :
    n_lat=360
    n_long=720
    norm2= norm//2
    
    L0_central =int(( max(L0_list)-min(L0_list) )//2)
    delta_long =180 - L0_central
    shift_pixels = int((delta_long / 360) * 360)
    carte = np.roll(carte, shift=shift_pixels, axis=1)
    
    profil_x = np.median(carte, axis=0)
    x_1 = np.where(profil_x>norm2)[0][0]
    x_2 = np.where(profil_x>norm2)[0][-1]
    profil_y = np.median(carte, axis=1)
    y_1 = np.where(profil_y>norm2)[0][0]
    y_2 = np.where(profil_y>norm2)[0][-1]

    
    carte_crop = carte [y_1:y_2,x_1:x_2]
    
    j,i = x_1, y_1
    lat_1 = np.round(-90 + i * 180 / (n_lat - 1))
    long_1 = j * 360 / n_long
    
    j,i = x_2, y_2
    lat_2 = np.round(-90 + i * 180 / (n_lat - 1))
    long_2 = j * 360 / n_long
    
    return carte_crop, long_1, long_2, lat_1, lat_2


"""
if __name__ == "__main__" :
    # data Sunscan Olivier Garde
    # nx, ny = 1100, 1100
    # R = 410
    # x_c, y_c = 550 , 550

    # prepare data
    images =[]
    B0_list = []
    L0_list = []
    xc_list = []
    yc_list = []
    R_list=[]

    nim=[]
    nlog=[]
    
    for i in range(1,9) :
        nf = 'C:\\Users\\valer\\Desktop\\Demo - Partner\\Olivier synoptic\\a'+str(i)+'_d.png'
        nim.append(nf)
        nl = 'C:\\Users\\valer\\Desktop\\Demo - Partner\\Olivier synoptic\\a'+str(i)+'_log.txt'
        nlog.append(nl)
        _,dateutc = ip.get_time_from_log(nl)
        mydate=dateutc[0]+'T'+dateutc[1]
        angP, paramB0, longL0, RotCarr = ip.angle_P_B0(mydate)
        B0_list.append(float(paramB0))
        L0_list.append(float(longL0))
        img= cv2.imread(nf, cv2.IMREAD_UNCHANGED)
        images.append(img)
        R_list.append(410)
        xc_list.append(550)
        yc_list.append(550)
    
    carte_syno = syn.make_synoptic (images, B0_list, L0_list, xc_list, yc_list, R_list, norm=20000)
    carte_crop, long_1, long_2, lat_1, lat_2 = syn.format_carte (carte_syno, L0_list, norm=20000)


    fig1 = plt.figure (figsize=(10,5))
    ax1 = fig1.add_subplot(1,1,1)
    ax1.imshow(carte_crop, extent=[long_1,long_2,lat_1,lat_2], origin = 'lower', aspect='auto', cmap='gray')
    ax1.set_xlabel('Longitude (°)')
    ax1.set_ylabel('Latitude (°)')
    ax1.set_title ('Carte synoptique')
    plt.show()
"""

