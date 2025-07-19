# -*- coding: utf-8 -*-
"""
Created on Sat Nov 23 12:29:19 2024

@author: Christian Buil
"""

# =================================================================
# SUNSCAN - DEDISTOR
# Correction des déformations induites par la turbulence
# sur des séquences d'images
# =================================================================

import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import map_coordinates
from scipy.fft import fft2, ifft2, fftshift
from astropy.io import fits
#import imageio.v2
import cv2

# ------------------------------------
# CROSS_CORRELATE_SHIFT_FFT
# ------------------------------------
def cross_correlation_shift_fft(patch_ref, patch_def):
    """
    Calculate the shift (dx, dy) using FFT-based cross-correlation with sub-pixel accuracy.
    """
    fft_ref = fft2(patch_ref)
    fft_def = fft2(patch_def)
    cross_corr = fftshift(ifft2(fft_ref * np.conj(fft_def)).real)

    max_idx = np.unravel_index(np.argmax(cross_corr), cross_corr.shape)
    center = np.array(cross_corr.shape) // 2
    shifts = np.array(max_idx) - center

    def fit_parabola_1d(values):
        denom = 2 * (2 * values[1] - values[0] - values[2])
        if denom == 0:
            return 0
        return (values[0] - values[2]) / denom

    dy_offset = 0
    dx_offset = 0

    if 1 <= max_idx[0] < cross_corr.shape[0] - 1:
        dy_offset = fit_parabola_1d([
            cross_corr[max_idx[0] - 1, max_idx[1]],
            cross_corr[max_idx[0], max_idx[1]],
            cross_corr[max_idx[0] + 1, max_idx[1]]
        ])
    if 1 <= max_idx[1] < cross_corr.shape[1] - 1:
        dx_offset = fit_parabola_1d([
            cross_corr[max_idx[0], max_idx[1] - 1],
            cross_corr[max_idx[0], max_idx[1]],
            cross_corr[max_idx[0], max_idx[1] + 1]
        ])

    shifts = shifts[::-1]
    shifts = shifts + np.array([dy_offset, dx_offset])
    return shifts

# --------------------------------------------------------------
# INTERPOLATE_DISPLACEMENT
# --------------------------------------------------------------
def interpolate_displacement(x_values, y_values, displacement_values, image_shape):
    """
    Interpolate displacement values (dx or dy) over the entire image using griddata.
    """
    # Create a grid corresponding to the full image
    grid_y, grid_x = np.mgrid[0:image_shape[0], 0:image_shape[1]]

    # Interpolation with griddata (linear interpolation + extrapolation)
    displacement_map = griddata(
        points=(y_values, x_values),
        values=displacement_values,
        xi=(grid_y, grid_x),
        method='cubic',
        fill_value=0  # Extrapolate with zeros if needed
    )
    return displacement_map

# ---------------------------------------------
# CORRECT_IMAGE
# ---------------------------------------------
def correct_image(def_image, dx_map, dy_map):
    """
    Correct the deformed image using dx and dy maps with linear interpolation.
    """
    coords_y, coords_x = np.meshgrid(np.arange(def_image.shape[0]), np.arange(def_image.shape[1]), indexing='ij')
    corrected_coords_y = coords_y - dy_map
    corrected_coords_x = coords_x - dx_map
    corrected_image = map_coordinates(def_image, [corrected_coords_y, corrected_coords_x], order=1, mode='nearest')
    return corrected_image

# -------------------------------
# FIND_DISTORSION 
# -------------------------------
def find_distorsion(path, reference_name, deformed_name, patch_size, step_size, intensity_threshold):
    """
    Parameters
    ----------
    path : TYPE
        Chemin des images
    reference_name : TYPE
        Nom de l'image maître de référence'
    deformed_name : TYPE
        Nom  de l'image déformée à rectivier'
    patch_size : TYPE
        Taille du patch corrélation
    step_size : TYPE
        Pas du cadrillage du patch de corrélation (en X et Y)
    intensity_threshold : TYPE
        Seuil d'intensité au dessus duquel la corrélaton est calculé

    Returns
    -------
    dx_map : TYPE
        Carte des décalages en X
    dy_map : TYPE
        Carte des décalages en Y
    amplitude_map : TYPE
        Carte de l'amplitude des décalages '
    """

    # Le traitement est fait par paire d'imagees, on charge la paire au format PNG
    #full_reference_path = path + reference_name + '.png'
    #full_deformed_path = path + deformed_name + '.png'
    
    full_reference_path = reference_name 
    full_deformed_path = deformed_name 
    
    #ref_image = imageio.v2.imread(full_reference_path)
    #def_image = imageio.v2.imread(full_deformed_path)
    ref_image = cv2.imread(full_reference_path,cv2.IMREAD_UNCHANGED)
    def_image = cv2.imread(full_deformed_path,cv2.IMREAD_UNCHANGED)
    
    # Conversion sur ne base 16 bits N&B (impératif avec images SUNSCAN)
    ref_image = np.array(ref_image, np.uint16)
    def_image = np.array(def_image, np.uint16)
   
    # Passe-haut pour améliorre la registration (accroissement des contrastes) (NA)
    #ref_image = sharpen_image(ref_image, 3)
    #def_image = sharpen_image(def_image, 3)
    
    rows, cols = ref_image.shape
    grid_y, grid_x = np.mgrid[0:rows:step_size, 0:cols:step_size]
    dx_values, dy_values, x_values, y_values = [], [], [], []

    for y, x in zip(grid_y.ravel(), grid_x.ravel()):
        
        if y + patch_size > rows or x + patch_size > cols:
            continue

        patch_ref = ref_image[y:y + patch_size, x:x + patch_size]
        patch_def = def_image[y:y + patch_size, x:x + patch_size]
        
        if patch_ref.min() < intensity_threshold:
            continue

        if patch_ref.shape == (patch_size, patch_size) and patch_def.shape == (patch_size, patch_size):
            dx, dy = cross_correlation_shift_fft(patch_ref, patch_def)
            dx_values.append(dx)
            dy_values.append(dy)
            x_values.append(x + patch_size // 2)
            y_values.append(y + patch_size // 2)
            
    # Interpolation des images point de mesures en des cartes dx, dy
    # (images au même format que les images d'entrée)
    dx_map = interpolate_displacement(np.array(x_values), np.array(y_values), np.array(dx_values), ref_image.shape)
    dy_map = interpolate_displacement(np.array(x_values), np.array(y_values), np.array(dy_values), ref_image.shape)
    amplitude_map = np.sqrt(dx_map ** 2 + dy_map ** 2)
        
    return dx_map, dy_map, amplitude_map

# -----------------------------------------------------------------
# CORRECT_IMAGE_PNG
# Corrige une image déformée avec l'information des cartes dx, dy
# -----------------------------------------------------------------
def correct_image_png(path, input_name, dx_map, dy_map):
    """
    Parameters
    ----------
    path : TYPE
        Chemin de l'image'
    input_name : TYPE
        Nom de l'image (au format JPG)
    dx_map : TYPE
        Carte des déformations en X
    dy_map : TYPE
        Carte des déformations en Y 

    Returns
    -------
    corrected_image : TYPE
        L'image corrigée de la distorsion

    """
    
    # Charge l'image déformée (version FITS)
    #input_path = path + input_name + '.fits'
    #def_image = fits.getdata(input_path)
    
    # Charge l'image déforlée (version PNG)
    #input_path = path + input_name + '.png'
    input_path = input_name
    #def_image = imageio.v2.imread(input_path)
    def_image = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
    
    # Convertie en 16 bits N&B
    def_image = np.array(def_image, np.uint16)
    
    # Correction de la distorsion (pixel au plus proche voisin)
    coords_y, coords_x = np.meshgrid(np.arange(def_image.shape[0]), np.arange(def_image.shape[1]), indexing='ij')
    corrected_coords_y = coords_y - dy_map
    corrected_coords_x = coords_x - dx_map
    corrected_image = map_coordinates(def_image, [corrected_coords_y, corrected_coords_x], order=1, mode='nearest')
    return corrected_image

# ------------------------------------
# SHARPEN_IMAGE
# ------------------------------------
def sharpen_image(image, level):
   
    for i in range(0,level):
        # Apply Gaussian blur with a 9x9 kernel and sigma of 10.0
        gaussian_3 = cv2.GaussianBlur(image, (9,9), 10.0)
        # Sharpen the image by subtracting the blurred image
        image = cv2.addWeighted(image, 1.5, gaussian_3, -0.5, 0, image)
         
        if (i <2):
            # Apply Gaussian blur with a 3x3 kernel and sigma of 8.0
            gaussian_3 = cv2.GaussianBlur(image, (3,3), 8.0)
            # Sharpen the image one more time
            image = cv2.addWeighted(image, 1.5, gaussian_3, -0.5, 0, image)
    return image


# ------------------------------
# SCALE_IMAGE
# ------------------------------
def scale_image(image, scale_factor):
   
    # Obtenir les dimensions de l'image originale
    original_height, original_width = image.shape[:2]

    # Calculer les nouvelles dimensions
    new_width = int(original_width / scale_factor)
    new_height = int(original_height / scale_factor)

    # Redimensionner l'image avec interpolation bicubique pour préserver les détails
    resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

    return resized_image

# ----------------------------------
# CROP_IMAGE
# ----------------------------------
def crop_image(image, target_width, target_height):
  
    # Dimensions de l'image originale
    original_height, original_width = image.shape[:2]

    # Vérifier que les dimensions cibles sont valides
    if target_width > original_width or target_height > original_height:
        raise ValueError("Les dimensions cibles doivent être inférieures ou égales aux dimensions de l'image originale.")

    # Calculer les coordonnées pour le crop centré
    start_x = (original_width - target_width) // 2
    start_y = (original_height - target_height) // 2
    end_x = start_x + target_width
    end_y = start_y + target_height

    # Découper l'image
    cropped_image = image[start_y:end_y, start_x:end_x]
    
    return cropped_image

# ---------------------------------
# MAKE_ECLIPSE_EFFECT
# ---------------------------------
def make_eclipse_effect(image, diameter,dx, dy):
    
    # Obtenir les dimensions de l'image
    height, width = image.shape[:2]

    # Vérifier que le diamètre est valide
    if diameter > min(width, height):
        raise ValueError("Le diamètre du disque doit être inférieur ou égal à la plus petite dimension de l'image.")

    # Créer un masque noir avec un disque blanc au centre
    mask = np.zeros((height, width), dtype=np.uint8)
    #center = (width // 2 + dx, height // 2 - dy)
    center=(dx,dy)
    radius = diameter // 2

    # Dessiner un disque blanc avec des bords adoucis
    cv2.circle(mask, center, radius, (255,), thickness=-1, lineType=cv2.LINE_AA)

    # Inverser le masque pour créer le disque noir
    mask_inv = cv2.bitwise_not(mask)

    # Appliquer le masque sur l'image
    black_disk = np.zeros_like(image)
    image_with_eclipse = cv2.bitwise_and(image, image, mask=mask_inv)
    image_with_eclipse += cv2.bitwise_and(black_disk, black_disk, mask=mask)

    return image_with_eclipse


"""
######################################################################
# Main
# --------------------------------------------------------------------
# On fournit le nom racine d'une séquence d'images SUNSCAN déformées par
# la turbulence. La première image de la séqunce est prise comme 
# reférence pour la registration. Cette séquence principale 
# est typiquement celle des images Clahe (mais le RAW est possible).
# Le format d'entrée est le PNG. Les fichier image sont renommées et 
# indéxés pour êtres de la forme xxx-1.png, xxx-2.png, www-3.png ... 
#
# Une seconde séquence est traitée en parallèle en se servant des
# coefficients de déformation trouvés dans le séquence principale.
# Typiquement, la séquence secondaire est celle de la photosphère.
# Si on ne dispose pas d'une séquence secondaire, on donne pour le
# nom racine de la séquence correspondante celui de de la séquence
# principale.
#
# Après la registration proprement dite, du prétraitement est réalisé :
# crop, changement d'échelle, rehaussement type maque flou (même
# algo que celui implémenté dans l'application), génération d'un "effet
# éclipse".
#
# Les résultats sont sauvegardés dans le format PNG (16 bits),
# JPEG (8 bits) et quelques images de conttrôle dans le format FITS.
######################################################################

# -------------------------------------------------------------
path = '/Users/macbuil/Documents/SunScan/sunscan_041224/'

deformed_root = 'clahe-'  # séquence d'images sur laquelle porte la recherche des déformation
deformed_root_second = 'cont-'  # séquence secondaire traitée avec les mpemes (dx, dy)

sharp_coef = 1     # coefficient de rehaussement 
sharp_coef_second = 1     # coefficient de rehaussement sur l'image secondaire

number_image = 8     # nombre d'images
scale_coef = 1.3     # réduction de la taille de l'imag 

stack_name = 'stack' # nom de l'image finale stackée de la séquence principale
stack_name_second = 'stack2' # nom de l'image finale stackée de la séquence secondaire

eclipse_diam = 817
eclipse_coef = 3
eclipse_dx = -1
eclipse_dy = 3
eclipse_name = 'eclipse'
# -------------------------------------------------------------

# Initialisation du stacking
sum_image = imageio.v2.imread(path + deformed_root + '1.png') # on récupère de format des images et on sauvegarde la première
sum_image = sum_image.astype(np.uint32)  # conversion en 32 bits

sum_image_second = imageio.v2.imread(path + deformed_root_second + '1.png') # on récupère de format des images et on sauvegarde la première
sum_image_second = sum_image_second.astype(np.uint32)  # conversion en 32 bits

# Boucle sur les images
#for i in range(number_image):
for i in range(1, number_image + 1, 1):
    print('Image #' + str(i))
    
    # Calcul des cartes de décalage
    # patch_size : taille du patch de cross-corrélation
    # step_size : pas de cross-corrélation (en X et Y)
    # intensity_threshold : seuil d'intensité en dessous duquel la corrélation n'est pas calculé
    deformed_name = deformed_root + str(i)
    deformed_name_second = deformed_root_second + str(i)
    dx_map, dy_map, amplitude_map = find_distorsion(path, deformed_root+ '1', deformed_name, patch_size=32, step_size=10, intensity_threshold=0)
        
    # Correction des distorsions dans la séquence principale (format PNG en entrée)
    corrected_image = correct_image_png(path, deformed_name, dx_map, dy_map)
 
    # Correction des distorsions dans la séquence secondaire (format PNG en entrée)
    corrected_image_second = correct_image_png(path, deformed_name_second, dx_map, dy_map)
     
    # Sommation (stacking)
    if i > 1:
        sum_image = sum_image + corrected_image.astype(np.uint32)
        sum_image_second = sum_image_second + corrected_image_second.astype(np.uint32)

# Normalisation sur 16 bits
sum_image = sum_image / number_image
image_eclipse = sum_image
sum_image = sum_image.astype(np.uint16)
sum_image_second = sum_image_second / number_image
sum_image_second = sum_image_second.astype(np.uint16)

# Sauvegarde des stacks bruts en format FITS (contrôle)
corrected_name_path = path + 'check1.fits'
fits.writeto(corrected_name_path, sum_image, overwrite=True)
corrected_name_path = path + 'check_second1.fits'
fits.writeto(corrected_name_path, sum_image_second, overwrite=True)

# Rehaussement
sum_image_sharped = sharpen_image(sum_image, sharp_coef)
sum_image_sharped_second = sharpen_image(sum_image_second, sharp_coef_second)

# Sauvegarde des stacks rehaussés en format FITS (contrôle)
corrected_name_path = path + 'check2.fits'
fits.writeto(corrected_name_path, sum_image_sharped, overwrite=True)
corrected_name_path = path + 'check_second2.fits'
fits.writeto(corrected_name_path, sum_image_sharped_second, overwrite=True)

# Génère une image éclipse
image_eclipse = image_eclipse * eclipse_coef  # intensité
image_eclipse = make_eclipse_effect(image_eclipse, eclipse_diam, eclipse_dx, eclipse_dy)

# Recadrage images SUNSCAN
sum_image_sharped  = crop_image(sum_image_sharped, 920, 920)
sum_image_sharped_second  = crop_image(sum_image_sharped_second, 920, 920)
image_eclipse  = crop_image(image_eclipse, 920, 920)

# Réduction de la taille des images d'un facteur scale
sum_image_sharped = scale_image(sum_image_sharped, scale_coef)
sum_image_sharped_second = scale_image(sum_image_sharped_second, scale_coef)
image_eclipse = scale_image(image_eclipse, scale_coef)

# Normalise sur 16 bits
max_value = np.max(sum_image_sharped)
if max_value != 0:
    sum_image_sharped = (sum_image_sharped / max_value) * 65535.0
sum_image_sharped = sum_image_sharped.astype(np.uint16)

max_value = np.max(sum_image_sharped_second)
if max_value != 0:
    sum_image_sharped_second = (sum_image_sharped_second / max_value) * 65535.0
sum_image_sharped_second = sum_image_sharped_second.astype(np.uint16)

# Clip de l'image éclipse
image_eclipse = np.clip(image_eclipse, 0, 65535)
image_eclipse = image_eclipse.astype(np.uint16)

# Sauvegarde des image finales en PNG 16 bits
imageio.v2.imwrite(path + stack_name + ".png", sum_image_sharped, format="png")
imageio.v2.imwrite(path + stack_name_second + ".png", sum_image_sharped_second, format="png")
imageio.v2.imwrite(path + eclipse_name + ".png", image_eclipse, format="png")

# Sauvegarde des image finales en JPEG 8 bits
sum_image_sharped = sum_image_sharped / 256
sum_image_sharped = sum_image_sharped.astype(np.uint8)
imageio.v2.imwrite(path + stack_name + ".jpg", sum_image_sharped, format="jpg")
sum_image_sharped_second = sum_image_sharped_second / 256
sum_image_sharped_second = sum_image_sharped_second.astype(np.uint8)
imageio.v2.imwrite(path + stack_name_second + ".jpg", sum_image_sharped_second, format="jpg")
image_eclipse = image_eclipse / 256
image_eclipse = image_eclipse.astype(np.uint8)
imageio.v2.imwrite(path + eclipse_name + ".jpg", image_eclipse, format="jpg")

print("Correction completed and results saved.")

"""
