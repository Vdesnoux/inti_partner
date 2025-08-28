# -*- coding: utf-8 -*-
"""
Created on Mon Aug 25 18:47:09 2025

@author: valer
"""

import matplotlib.pyplot as plt
import cv2 as cv2
import synoptic as syn
import inti_partner as ip


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


