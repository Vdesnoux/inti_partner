# -*- coding: utf-8 -*-
"""
Created on Wed Apr 13 23:22:13 2022

@author: chris
"""

import numpy as np
import cv2
import os
import sys
from astropy.io import fits
import yaml
import shutil


#======================================================
# LOAD_FITS_IMAGE
#======================================================
def load_fits_image(image_name, fits_ext):
    """  
    Lecture d'une image 2D au format FITS
  
    Parameters
    ----------
    image_name: string
        Chemin et nom du fichier image (sans l'extension)
    fits_ext: string
        Extension du fichier FITS
   
    Returns
    -------
    array_like
        Tableau 2D contenant les valeurs de l'image
    array_like
        Entête de l'image FITS venant d'être lue
                
    Examples
    --------
    >>>load_fits_ilmage(name, '.fits')
    """
    name = image_name +  fits_ext
    try:
        hdul = fits.open(name, memmap=False)  # ouvre le fichier FITS
        hdr = hdul[0].header                  # header HDU primaire
        imax = hdr['NAXIS1']                  # taille X de l'image
        jmax = hdr['NAXIS2']                  # taille Y de l'image
        # On convertie les données du fichier FITS en un tableau 2D numpy
        data = np.reshape(hdul[0].data, (jmax, imax))
        data = data.astype(np.float32)   # conversion en flottant 32 bits
        hdul.close()
    except FileNotFoundError:
        print(f"ERROR: Image {name} not found.")
        print('End.')   
        sys.exit(0)
        
    return data, hdr

#======================================================
# SAVE_FITS_IMAGE
#======================================================
def save_fits_image(image_name, data, hdr, fits_ext):
    """  
    Sauvegarde d'une image 2D au format FITS
  
    Parameters
    ----------
    image_name: string
        Chemin et nom du fichier image (sans l'extension)
    data: array_like
        Tableau des données images
    hdr: array_like
        Intitulé de l'entête à inscrire dans le fichier FITS
    fits_ext: string
        Extension du fichier FITS
   
    Returns
    -------
    None
                
    Examples
    --------
    >>>save_fits_ilmage(name, img, hdr, '.fits')
    """
    name = image_name + fits_ext
    data = data.astype(np.float32)   # conversion en flottant 32 bits
    DiskHDU = fits.PrimaryHDU(data, hdr)
    DiskHDU.writeto(name, overwrite='True')
    
#=====================================================
# FILE_EXIST
# Contrôle la presente d'un fichier
#=====================================================
def file_exist(name):    
   
    if not os.path.exists(name):

        print('ERROR: File ' + name + ' not found.')
        print('End.') 
        return  True
    else:
        return False
       

def magnetogramme (WorkDir,racine_filtre1, racine_filtre2, nb_filtre1,nb_filtre2) :

            
    # ------------------------------
    # ------------------------------
    # On lance le calcul
    # ------------------------------
    # ------------------------------

      
    # ----------------------
    # On traite le filtre #1
    # ----------------------
    nb = nb_filtre1  # nombre d'images dans la séquence
    
    for i in range(nb):
        
        # ---------------
        # Aile bleue
        # ---------------
            
        image_name = WorkDir + racine_filtre1 + 'b-' + str(i+1)
        data, hdr = load_fits_image(image_name, '.fits')
        
        imax = hdr['NAXIS1']
        jmax = hdr['NAXIS2']
        xc = hdr['INTI_XC']
        yc = hdr['INTI_YC']
        radius = hdr['INTI_R']
        
        if i==0:      # La première image sert pour calculer la demi-largeur croppée
            delta = radius + 25
        
        # On croppe
        x1 = xc - delta
        x2 = xc + delta
        y1 = yc - delta
        y2 = yc + delta
        if x1 < 0 :
            x1 = 0
        if y1 < 0 : 
            y1 = 0
        if x2 > imax - 1 : 
            x1 = imax - 1
        if y2 > jmax - 1 :
            y2 = jmax - 1
        data2 = data[y1:y2 , x1:x2]
        hdr['NAXIS1'] = x2 - x1 + 1
        hdr['NAXIS2'] = y2 - y1 + 1
        
        # Sauvegarde de l'image réduite (a) - contrôle
        #image_name = WorkDir + 'tmpa' + str(i+1)
        #save_fits_image(image_name, data2, hdr, '.fits')
        
        # On calcule la somme
        if i==0:
            polb1 = data2
        else:
            polb1 += data2
            
        # ---------------
        # Aile rouge
        # ---------------
           
        image_name = WorkDir + racine_filtre1 + 'r-' + str(i+1)
        data, hdr = load_fits_image(image_name, '.fits')
        
        imax = hdr['NAXIS1']
        jmax = hdr['NAXIS2']
        xc = hdr['INTI_XC']
        yc = hdr['INTI_YC']
        radius = hdr['INTI_R']
          
        # On croppe
        x1 = xc - delta
        x2 = xc + delta
        y1 = yc - delta
        y2 = yc + delta
        if x1 < 0 :
            x1 = 0
        if y1 < 0 : 
            y1 = 0
        if x2 > imax - 1 : 
            x1 = imax - 1
        if y2 > jmax - 1 :
            y2 = jmax - 1
        data2 = data[y1:y2 , x1:x2]
        hdr['NAXIS1'] = x2 - x1 + 1
        hdr['NAXIS2'] = y2 - y1 + 1
        
        # Sauvegarde de l'image réduite (b) - contrôle
        #image_name = WorkDir + 'tmpb' + str(i+1)
        #save_fits_image(image_name, data2, hdr, '.fits')
        
        # On calcule la somme
        if i==0:
            polr1 = data2
        else:
            polr1 += data2
 
    polb1 = polb1 / float(nb)  # on normalise
    polr1 = polr1 / float(nb)
    
    # ----------------------
    # On traite le filtre #2
    # ----------------------
    nb = nb_filtre2  # nombre d'images dans la séquence
    
    for i in range(nb):
        
        # ---------------
        # Aile bleue
        # ---------------
            
        image_name = WorkDir + racine_filtre2 + 'b-' + str(i+1)
        data, hdr = load_fits_image(image_name, '.fits')
        
        imax = hdr['NAXIS1']
        jmax = hdr['NAXIS2']
        xc = hdr['INTI_XC']
        yc = hdr['INTI_YC']
        radius = hdr['INTI_R']
        
        # On croppe
        x1 = xc - delta
        x2 = xc + delta
        y1 = yc - delta
        y2 = yc + delta
        if x1 < 0 :
            x1 = 0
        if y1 < 0 : 
            y1 = 0
        if x2 > imax - 1 : 
            x1 = imax - 1
        if y2 > jmax - 1 :
            y2 = jmax - 1
        data2 = data[y1:y2 , x1:x2]
        hdr['NAXIS1'] = x2 - x1 + 1
        hdr['NAXIS2'] = y2 - y1 + 1
        
        # Sauvegarde de l'image réduite (c) - contrôle
        #image_name = WorkDir + 'tmpc' + str(i+1)
        #save_fits_image(image_name, data2, hdr, '.fits')
        
        # On calcule la somme
        if i==0:
            polb2 = data2
        else:
            polb2 += data2
            
        # ---------------
        # Aile rouge
        # ---------------
            
        image_name = WorkDir + racine_filtre2 + 'r-' + str(i+1)
        data, hdr = load_fits_image(image_name, '.fits')
        
        imax = hdr['NAXIS1']
        jmax = hdr['NAXIS2']
        xc = hdr['INTI_XC']
        yc = hdr['INTI_YC']
        radius = hdr['INTI_R']
             
        # On croppe
        x1 = xc - delta
        x2 = xc + delta
        y1 = yc - delta
        y2 = yc + delta
        if x1 < 0 :
            x1 = 0
        if y1 < 0 : 
            y1 = 0
        if x2 > imax - 1 : 
            x1 = imax - 1
        if y2 > jmax - 1 :
            y2 = jmax - 1
        data2 = data[y1:y2 , x1:x2]
        hdr['NAXIS1'] = x2 - x1 + 1
        hdr['NAXIS2'] = y2 - y1 + 1
        
        # Sauvegarde de l'image réduite (b) - contrôle
        #image_name = WorkDir + 'tmpd' + str(i+1)
        #save_fits_image(image_name, data2, hdr, '.fits')
        
        # On calcule la somme
        if i==0:
            polr2 = data2
        else:
            polr2 += data2

    polb2 = polb2 / nb  # on normalise
    polr2 = polr2 / nb
    
    """
    # Sauvegarde des 4 images latérales après addition
    image_name = WorkDir + 'tmp_b+45'
    save_fits_image(image_name, polb1, hdr, '.fits')  

    image_name = WorkDir + 'tmp_r+45'
    save_fits_image(image_name, polr1, hdr, '.fits')
    
    image_name = WorkDir + 'tmp_b-45'
    save_fits_image(image_name, polb2, hdr, '.fits')  

    image_name = WorkDir + 'tmp_r-45'
    save_fits_image(image_name, polr2, hdr, '.fits')  
    """
    
    # Calcul du magnétogramme
    V = (polb1 - polr1) - (polb2 - polr2)
    I = polb1 + polr1 + polb2 + polr2
    II = I / 4.0
    VN = V / I * I[int(y2/2), int(x2/2)]
    

    #image_name = WorkDir + result_magnet + "0"
    #save_fits_image(image_name, V, hdr, '.fits')  
    img_mag0= V
    
    #image_name = WorkDir + result_cont
    #save_fits_image(image_name, II, hdr, '.fits')  
    img_cont=II
    
    #image_name = WorkDir + result_magnet
    #save_fits_image(image_name, VN, hdr, '.fits')
    #img_mag=VN


    # test pour mettre a zero le fond connaissant radius et center
    w = VN.shape[1]
    h =VN.shape[0]
    center=[w/2,h/2]
    Y, X = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((X - center[0])**2 + (Y-center[1])**2)

    mask = dist_from_center <= radius
    masked_img = VN.copy()
    masked_img[~mask] = -32767
    img_mag=np.copy(masked_img)
            
    return img_mag, img_mag0, img_cont, polb1, polb2, polr1, polr2, hdr

