# -*- coding: utf-8 -*-
"""
Created on Mon Nov 27 20:32:54 2023

@author: valer

https://github.com/grmarcil/image_spline/blob/master/spline.py
"""
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import scipy
import scipy.ndimage as ndimage
import cv2


def im_reduce(img):
    '''
    Apply gaussian filter and drop every other pixel
    '''
    filter = 1.0 / 20 * np.array([1, 5, 8, 5, 1])
    lowpass = ndimage.filters.correlate1d(img, filter, 0)
    lowpass = ndimage.filters.correlate1d(lowpass, filter, 1)
    im_reduced = lowpass[::2, ::2, ...]
    return im_reduced

def im_expand(img, template):
    '''
    Re-expand a reduced image by interpolating according to gaussian kernel
    Include template parameter to match size, easy way to avoid off by 1 errors
    re-expanding a previous layer that may have had odd or even dimension
    '''
    # y_temp, x_temp = template.shape[:2]
    # im_expanded = np.zeros((y_temp, x_temp) + template.shape[2:], img.dtype)
    im_expanded = np.zeros(template.shape, img.dtype)
    im_expanded[::2, ::2, ...] = img

    filter = 1.0 / 10 * np.array([1, 5, 8, 5, 1])
    lowpass = ndimage.filters.correlate1d(
        im_expanded, filter, 0, mode="constant")
    lowpass = ndimage.filters.correlate1d(lowpass, filter, 1, mode="constant")
    return lowpass

def gaussian_pyramid(image, layers):
    '''
    pyramid of increasingly strongly low-pass filtered images,
    shrunk 2x h and w each layer
    '''
    pyr = [image]
    temp_img = image
    for i in range(layers):
        temp_img = im_reduce(temp_img)
        pyr.append(temp_img)
    return pyr

def laplacian_pyramid(gaussian_pyramid):
    '''
    laplacian pyramid is a band-pass filter pyramid, calculated by the
    difference between subsequent gaussian pyramid layers, terminating with top
    layer of gaussian. Laplacian pyramid can be summed to give back original
    image
    '''
    pyr = []
    for i in range(len(gaussian_pyramid) - 1):
        g_k = gaussian_pyramid[i]
        g_k_plus_1 = gaussian_pyramid[i + 1]
        g_k_1_expand = im_expand(g_k_plus_1, g_k)
        laplacian = g_k - g_k_1_expand
        pyr.append(laplacian)

    pyr.append(gaussian_pyramid[-1])
    return pyr


def laplacian_collapse(pyr):
    '''
    Rejoin all levels of a laplacian pyramid. As the pyramid is a spanning set
    of band-pass filter outputs (all frequencies represented once and only
    once), joining all levels will give back the original image, modulo
    compression loss
    '''
    ''' Start with lowest pass data, top of pyramid '''
    partial_img = pyr[-1]
    for i in range(len(pyr) - 1):
        next_lowest = pyr[-2 - i]
        expanded_partial = im_expand(partial_img, next_lowest)
        partial_img = expanded_partial + next_lowest
    return partial_img

"""
-------------------------------------------------------------------------
The function !
Crop n laplacians to combine each layers
-------------------------------------------------------------------------
"""

def laplacian_pyr_join(lpi, mid_point):
    
    debug=False
    plt.set_cmap('gray')
    
    pyr = []
    sub_lpi=[]
    mid_point=np.array(mid_point)
    
    for i in range(len(lpi[0])):
        sub_lpi=[]
        for k in range(len(lpi)) :
            sub_lpi.append(lpi[k][i])
                           
        layer = np.zeros(sub_lpi[0].shape, sub_lpi[0].dtype)
        y,x=sub_lpi[0].shape
        #print("y :",y)
     
        
        # boucle sur les n lpi
        sub_layers=sub_lpi[0] # haut
        for k in range(len(sub_lpi)-1):
            half=mid_point[k]

            ''' assign halves '''
            layer[:half,:, ...] = sub_layers[:half,:, ...]
            layer[ half:,:, ...] = sub_lpi[k+1][ half:,:, ...]
            
            ''' blend overlap zone '''
       
            layer[half-1:half-1,:, ...] = sub_layers[half-1:half-1,:, ...]*3/4 + sub_lpi[k+1][half-1:half-1,:, ...]*1/4
            layer[half:half,:, ...] = (sub_layers[half:half,:, ...] + sub_lpi[k+1][half:half,:, ...])//2
            layer[half+1:half+1,:, ...] = sub_layers[half+1:half+1,:, ...]*1/4 + sub_lpi[k+1][half+1:half+1,:, ...]*3/4
            sub_layers=np.copy(layer)
        
            if debug :
                print("half", half)
                for k in range(len(sub_lpi)) :
                    plt.title("sub_lpi"+str(i))
                    plt.imshow(sub_layers[:half,:, ...])
                    plt.show()
                    plt.title("sub_lpi"+str(i))
                    plt.imshow(sub_layers[half:,:, ...])
                    plt.show()

        if debug :        
            plt.title("combine lpi"+str(i))
            plt.imshow(layer)
            plt.show()
        
        pyr.append(layer)
        mid_point=mid_point//2
    return pyr


