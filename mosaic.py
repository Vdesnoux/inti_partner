# -*- coding: utf-8 -*-
"""
******************************************************************************
Created on Sun Jan  2 16:06:01 2022

@author: valerie Desnoux

d'apres https://github.com/grmarcil/image_spline/blob/master/spline.py
et papier Burt and Adelson's "A Multiresolution Spline With Application to Image Mosaics"

******************************************************************************

creation module mosaic.py avec separation de UI pour inclusion avec inti_suite

"""

import numpy as np
#import matplotlib.pyplot as plt
from PIL import Image
import os
from pathlib import Path
import io
from astropy.io import fits
import matplotlib.pyplot as plt
import cv2
import blend_functions as bl
import scipy.ndimage as ndimage


"""
def get_baseline(f):
    f_short=os.path.split(f)[1]
    f_path=os.path.split(f)[0]
    prefix=f_short.rfind('st')
    if prefix != -1 :
        f_short=f_short[2:]
        f=f_path+os.sep+f_short
    
    index=f.rfind('_dp')
    if index == -1 :
        index=f.rfind("_")
        
    index=f.rfind('_color')
    if index == -1 :
        index=f.rfind("_")
        
    baseline= f[:index]

        
    return baseline
"""

def get_baseline (f) :
    f_short=os.path.split(f)[1]
    f_path=os.path.split(f)[0]
    prefix=f_short.rfind('st')
    if prefix != -1 :
        f_short=f_short[2:]
        f=f_path+os.sep+f_short
        
    index=-1
    if f.rfind('_dp') !=1 :
        index=f.rfind('_dp')
    if f.rfind('_color') != -1 :
        index=f.rfind('_color')
    if f.rfind('_doppler') != -1 :
        index =f.rfind('_doppler')
    if index == -1 :
        index=f.rfind("_")
        
    baseline= f[:index] # chemin complet
        
    return baseline


def decode_log(flog):
    try:
        with open(flog,encoding='latin-1') as f:
            lines_log=f.readlines()
            # trouve la ligne avec centre et rayon
            # ajout ligne pour image croppée
            try :
                ligne2=[l  for l in lines_log if 'xcc,ycc' in l]
            except:
                ligne2=[l  for l in lines_log if 'xc,yc' in l]
            ligne2[0]=ligne2[0].replace('\n','')
            # decoupe la ligne apres le ':' pour les coordonnées du centre xc,yc et rayon
            sc=str(ligne2[0]).split(':')[1].split(' ')
            #print('sc',sc)
            cx=sc[1]
            cy=sc[2]
            sr=sc[3]
            
            # decode haut bas
            # trouve la ligne avec box y1,y2,x1,x2
            maligne1=[l  for l in lines_log if l[0:5]=="Coord" ]
            if len(maligne1) !=0 :
                maligne1[0]=maligne1[0].replace('\n','')
                # decoupe la ligne pour extraire les quatre coordonnées
                bb=str(maligne1[0]).split(':')[1].split(' ')
                box1 = bb[1].split(',')
                box2 = bb[2].split(',')
                ay1=box1[0]
                ay2=box1[1]
                ax1=box2[0]
                ax2=box2[1]
            else :
                ax1=ax2=ay1=ay2=0
    except :
        print('Erreur fichier : ', flog)
        cx=cy=sr=ax1=ax2=ay1=ay2=0
        
    return cx,cy,sr,ay1,ay2,ax1,ax2

def im_reduce(img):
    '''
    Apply gaussian filter and drop every other pixel
    '''
    filter = 1.0 / 20 * np.array([1, 5, 8, 5, 1])
    lowpass = ndimage.filters.correlate1d(img, filter, 0)
    lowpass = ndimage.filters.correlate1d(lowpass, filter, 1)
    im_reduced = lowpass[::2, ::2, ...]
    return im_reduced

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

def fits_to_PIL (myimg, s1,s2):
    myimg_s=seuil_image(myimg, s1, s2)
    myimg8=cv2.convertScaleAbs(myimg_s,alpha=255/(65535), beta=0.1)
    im = Image.fromarray(myimg8)
    return im
    
def seuil_image (i, Seuil_bas, Seuil_haut):
    img=np.copy(i)
    img[img>Seuil_haut]=Seuil_haut
    if Seuil_haut!=Seuil_bas :
        img_seuil=(img-Seuil_bas)* (65535/(Seuil_haut-Seuil_bas))
        img_seuil[img_seuil<0]=0
    else:
        img_seuil=img
    return img_seuil

def img_resize_frompng (nomfich,dim):
    image = Image.open(nomfich)
    image.thumbnail((dim, dim))
    bio = io.BytesIO()
    image.save(bio, format="PNG")
    out=bio.getvalue()
    #with io.BytesIO() as output:
        #image.save(output, format="PNG")
        #out = output.getvalue()
    return out

def img_resize (im,li,co):
    im.thumbnail((li, co))
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    out=bio.getvalue()
    return out

def img_paste (result, im1,im2, dx, dy):
    result.paste(im1, (0,0)) #left, top
    result.paste(im2, (dx,dy))
    
def trad (textFR, textEN):
    LG=1
    if LG == 1 :
        print(textFR)
    else:
        print(textEN)
    return


def seuil_image_force (img, Seuil_haut, Seuil_bas):
    img[img>Seuil_haut]=Seuil_haut
    img_seuil=(img-Seuil_bas)* (65535/(Seuil_haut-Seuil_bas))
    img_seuil[img_seuil<0]=0
    
    return img_seuil


def prepare_files(WorkDir, ImgFiles) : 

                
    # faire test si un seul fichier
    if len(ImgFiles) <2 :
        trad("Sélectionner au moins 2 fichiers","Select at least 2 files")
    else :
        ImgFile1=ImgFiles[0]
        ImgFile2=ImgFiles[1]

        ih=[]
        iw=[]
        centerY=[]
        centerX=[]
        solarR=[]
        y1=[]
        y2=[]
        x1=[]
        x2=[]
        myimg=[]
        a=''
        # detecte extension fichier fits ou png
        base=os.path.basename(ImgFile1)
        ext=os.path.splitext(base)[1]
        try :
            for i in range(len(ImgFiles)) :
                if ext=='.fits':
                    #lit le fichier fits 1 avec memmap false pour eviter les fichiers ne se ferme pas
                    hdulist1 = fits.open(ImgFiles[i], memmap=False)
                    hdu1=hdulist1[0]
                    mysun1=hdu1.data
            
                    ih.append(hdu1.header['NAXIS2'])
                    iw.append(hdu1.header['NAXIS1'])
                    centerX.append(hdu1.header['CENTER_X'])
                    centerY.append(hdu1.header['CENTER_Y'])
                    solarR.append(hdu1.header['SOLAR_R'])
                    myimg.append(np.reshape(mysun1, (ih[i],iw[i])))
                    print(ImgFiles[i])
                    t=str(centerX[i])+" "+str(centerY[i])+" "+str(solarR[i])
                    trad("Centre x,y - rayon : "+ t, "Center x,y - radius : "+t)
                    print(iw[i],' x ', ih[i])
                    print("")
    
                    try : 
                        # utilise le header fits version inti 6.1+
                        ay1 = hdu1.header['INTI_Y1']
                        ay2 = hdu1.header['INTI_Y2']
                        ax1 = hdu1.header['INTI_X1']
                        ax2 = hdu1.header['INTI_X2']
                    except :
                        print("Processed with too old version of Inti")
                        try :
                            # decode le fichier log pour xc, yc, radius, y1,y2,x1,x2
                            file_log=get_baseline(os.path.splitext(ImgFiles[i])[0])+"_log.txt"
                            cx,cy,sr,ay1,ay2,ax1,ax2 = decode_log(file_log)
                        except :
                            print("Fichier _log.txt non trouvé")
                        
                    
                    y1.append(ay1)
                    y2.append(ay2)
                    x1.append(ax1)
                    x2.append(ax2)
                    
                    """
                    #conversion fits to png8
                    s1=np.percentile(myimg[i], 25)
                    s2=np.percentile(myimg[i],99.9999)*1.05
                    im= fits_to_PIL (myimg[i], s1, s2)
                    
                    # resize pour disp1
                    li=tdim
                    co=tdim
                    imgbytes=img_resize (im,li,co)
                    
                    # affiche en dur des thumbnails TODO en faire une liste
                    #if i in range(len(ImgFiles)) :
                    disp[i].DrawImage(data=imgbytes, location=(0,tdim))
                    """
                
                if ext==".png" :
                    # lit fichier png
                    imm=Image.open(ImgFiles[i])
                    myimg.append(np.flip(np.array(imm),0))
                    ih.append(myimg[i].shape[0])
                    iw.append(myimg[i].shape[1])
                   
                    # decode le fichier log pour xc, yc, radius, y1,y2,x1,x2
                    #file_log=get_baseline(os.path.splitext(ImgFiles[i])[0])+"_log.txt"
                    base = os.path.basename(ImgFiles[i])
                    baseline = get_baseline(os.path.splitext(base)[0])
                    file_log=get_baseline(os.path.splitext(ImgFiles[i])[0])+"_log.txt"
                    # test si pas de fichier et remonte d'un cran
                    if not os.path.exists(file_log):
                        # remonte d'un cran le chemin
                        parent_path = Path(WorkDir).parent
                        file_log=str(parent_path)+os.sep+baseline+"_log.txt"
                    
                    cx,cy,sr,ay1,ay2,ax1,ax2 = decode_log(file_log)
                    
                    if cx+cy+sr+ay1+ay2+ax1+ax2 == 0 :
                         flag_error = True
                    else :
                        flag_error= False
                    
                    centerX.append(int(cx))
                    centerY.append(int(cy))
                    solarR.append(int(sr))
                    y1.append(int(ay1))
                    y2.append(int(ay2))
                    x1.append(int(ax1))
                    x2.append(int(ax2))
                    
            
            # affiche valeurs de rayons
            by = np.array(y2)-np.array(y1)
            bx = np.array(x2)-np.array(x1)

            
            # test si meme dimensions
            if (np.min(iw)!=np.max(iw)) or (np.min(ih)!=np.max(ih)):
                trad("Les images n'ont pas la même dimension !!","Images do not have same dimension !!")
                raise Exception
            
            # ordonne les fichiers en partant du plus haut
            ImgFiles=np.array(ImgFiles)
            centerY=np.array(centerY)
            centerX=np.array(centerX)
            solarR=np.array(solarR)
            myimg=np.array(myimg)
            by=np.array(by)
            bx=np.array(bx)
            y1=np.array(y1)
            y2=np.array(y2)
            x1=np.array(x1)
            x2=np.array(x2)

            idx=np.flip(np.argsort(centerY)) #ordre decroissant !


            ImgFiles=ImgFiles[idx]
            centerY=centerY[idx]
            centerX=centerX[idx]
            myimg=myimg[idx]
            solarR=solarR[idx]
            by=by[idx]
            bx=bx[idx]
            
            y1=y1[idx]
            y2=y2[idx]
            x1=x1[idx]
            x2=x2[idx]
            
            """
            window['Run'].update(disabled=False)
            #window['Rescale'].update(disabled=False)
            
            WorkDir=os.path.dirname(ImgFiles[0])+os.path.sep
            """
     
        except :
            for i in range(len(ImgFiles)) :
                base=(os.path.basename(ImgFiles[i]))
                basefich=os.path.splitext(base)[0]
                ImgFiles[i]=base
            trad("Probleme de format de fichiers", "Error in files format")
            trad("Verifier entête fits","Check file header")
            trad("Mots clefs CENTER_X, CENTER_Y, SOLAR_R", "Keywords CENTER_X, CENTER_Y, SOLAR_R")
            print(ImgFiles)
            print("")
            if ext ==".fits": 
                hdulist1.close()
            else:
                print('file not selected')
    return myimg, iw, ih, centerX, centerY, solarR, x1, x2, y1, y2, flag_error

def create_mosa (WorkDir, ImgFiles, ext, myimg, iw, ih, centerX, centerY, solarR, x1, x2, y1, y2) :
    flag_error=False
    debug =False
    os.chdir(WorkDir)
    ext='.'+ext
    
    
    
    for i in range(len(ImgFiles)) :
        base=(os.path.basename(ImgFiles[i]))
        basefich=os.path.splitext(base)[0]
        ImgFiles[i]=base

    nom_base=ImgFiles[0].split('.')[0]+"-"+ImgFiles[len(ImgFiles)-1].split('.')[0]
    
    
    # test si image couleur
    if len(myimg[0].shape) == 3 :
        print ('color')
        nbplan=3
        myimg_color=np.copy(myimg)
        im_crop_color=[]
        myimg=[]
    else: 
        nbplan=1
        im_crop_color=[]


    
    # nombre de couche de multiresolution
    layers=7
    
    for k in range(0,nbplan) :

        if nbplan ==3 :
            im_crop=[]
            myimg=[]
            for i in range(len(ImgFiles)):
                myimg.append(myimg_color[i][:,:,k])

            
            
        """
        -------------------------------------------------------------------------
        Creation grande image
        -------------------------------------------------------------------------
        """
        iht=ih[0]
        offset=[]
        
        for i in range(len(ImgFiles)-1):
            iht=iht+ih[i]
            offset.append(centerY[i]-centerY[i+1])
        
        #img_grande=np.zeros((iht,iw[0]))
        #offset=centerY[0]-centerY[1]
            
         
        # correction d'exposition
        for i in range(len(ImgFiles)-1):
            zone_over= y2[i]-offset[i]+y1[i+1]
            print(ImgFiles[i]+" -- "+ImgFiles[i+1])
            t=str( zone_over)+ " pixels"
            trad("Recouvrement de : "+t, "Overlap of : "+t)
            if zone_over <=280:
                if zone_over <=40 :
                    trad("Pas assez de recouvrement !!", "not enought overlap !!")
                    flag_error =True
                else :
                    print("Attention, faible zone de recouvrement, mode degradé ", "Caution, low overlap zone, degraded mode")
                    layers= int(zone_over/40)
                    print("Niveaux de multiresolution : "+ str(layers)," Levels of multiresolution : "+str(layers))
                    
            try :
                z_lum1=np.mean(myimg[i][offset[i]+y1[i+1]:y2[i],:])
                z_lum2=np.mean(myimg[i+1][y1[i+1]:y2[i]-offset[i],:])
                
        
                rlum=z_lum1/z_lum2
                if rlum >1 :
                    rlum=z_lum2/z_lum1
                    myimg[i]=(rlum)*myimg[i]
                    print("Correction exposition Img1 :", rlum)
                else :
                    myimg[i+1]=(rlum)*myimg[i+1]
                    print("Correction exposition Img2 :", rlum)
            except:
                pass
    
        if flag_error != True :
            # correction de scaling basée sur le rapport des deux diametres
            
            for i in range(len(ImgFiles)-1):
                sc=solarR[0]/solarR[i+1]
                myimg2_sc=cv2.resize(myimg[i+1],(int(iw[i+1]*sc),int(ih[i+1]*sc)),interpolation=cv2.INTER_LINEAR_EXACT)
                #print('Facteur de rescaling Image'+str(i+1)+' : ',sc)
                
                if sc >=1 :
                    # crop
                    w1=int((int(iw[i+1]*sc)-iw[i+1])/2)
                    w2=-(int(iw[i+1]*sc)-iw[i+1]-w1)
                    h1=int((int(ih[i+1]*sc)-ih[i+1])/2)
                    h2=-(int(ih[i+1]*sc)-ih[i+1]-h1)
                    if h2 == 0 :
                        h2=ih[i]
                    if w2==0 :
                        w2=iw[i]
                    myimg[i+1]=myimg2_sc[h1:h2,w1:w2]
                    #print('shape resized crop :',myimg[i+1].shape)
                else :
                    # padding
                    w1=-int((int(iw[i+1]*sc)-iw[i+1])/2)
                    w2=-(int(iw[i+1]*sc)-iw[i+1]+w1)
                    h1=-int((int(ih[i+1]*sc)-ih[i+1])/2)
                    h2=-(int(ih[i+1]*sc)-ih[i+1]+h1)
                    myimg[i+1][h1:-h2,w1:-w2]=myimg2_sc
                    #print('shape resized padding:',myimg[i+1].shape)
                

            
            img_gr=[]
            #iht=2*ih[0]
            for i in range(len(ImgFiles)):
                # Prepare la grande image
                img_gr.append(np.full((iht,iw[0]),0)) #was 300
                
            debug=False
            # Elimine les bandes noires en bas de l'image 1 et haut de l'image 2
            img_gr[0][:y2[0],:]=myimg[0][:y2[0],:]
            a=0
            for i in range(1,len(ImgFiles)):
                a=a+offset[i-1]
                img_gr[i][a+y1[i]:a+y2[i],:]=myimg[i][y1[i]:y2[i]]
                if i == len(ImgFiles)-1:
                    img_gr[i][a+y1[i]:a+ih[i]-y1[i],:]=myimg[i][y1[i]:ih[i]-y1[i]]
    
            if debug :
                for i in range(len(ImgFiles)) :
                    plt.imshow(img_gr[i])
                    plt.show()
    
            
            
            # gestion de la zone de transition, il faut prendre en compte les artefacts de bords 
            # avec le filtrage gaussien
            a=0
            mid_point=[]
            for i in range(0,len(ImgFiles)-1) :
                a=a+offset[i]
                transition1= (a-offset[i]+y2[i]-(layers)*45)
                transition2=((a+y1[i+1])+(layers)*45)
                m=(transition2-transition1)//2
                m=transition1+m
                mid_point.append(m)
    
            print(mid_point)
            
            # le coeur de l'algo !!! decomposition en laplacien
            print("")
            trad("Calcul des niveaux de résolution.......", "Resolution levels computation.......")
            gpi=[]
            lpi=[]
            
            for i in range(len(ImgFiles)):
                gpi.append(bl.gaussian_pyramid(img_gr[i], layers))
                lpi.append(bl.laplacian_pyramid(gpi[i]))
         
            # le coeur de l'algo !!! on recompose l'image 
            trad("Recomposition de l'image.......", "Image recomposition.......")
            # on aboute les laplacien avec les transitions definies dans mid_point
            lp_join = bl.laplacian_pyr_join(lpi, mid_point)
            # on recompose l'image car la somme des laplaciens donne l'image finale
            im_join = bl.laplacian_collapse(lp_join)
            
            # on crop au carré - hauteur= largeur de la premiere image
            if centerY[0]*2 > iw[0] :
                miw= centerY[0]*2
            else :
                miw=iw[0]
            
            im_join=im_join[:miw, :]
            
            if debug :
                plt.imshow(im_join)
                plt.show()
                
                
            # on recentre et on crop au carré sur la largeur
            im_crop=np.full((iw[0], iw[0]), 0)    # on cree l'image finale
            
            dy= centerY[0]-iw[0]//2              # offset en y pour recentrage
            dx=centerX[0]-iw[0]//2                  # offset en x pour recentrage
            
            if iw[0] <= iht :
                if dy<=0 and dx>=0 :
                    im_crop[-dy:iw[0],:]=im_join[0:dy+iw[0], dx:dx+iw[0]]
                
                else :
                    trad("Allo Houston, on n'a un problème","Allo houston, we have a problem..")
                    im_crop=[]
                    im_crop=np.copy(im_join)
            else :
                dec=(iw[0]-iht)//2
                if dy<=0 and dx>=0 :
                    im_crop[-dy:iht-dy,:]=im_join[0:iht, dx:dx+iw[0]]
                
                else :
                    trad("Allo Houston, on n'a un problème","Allo houston, we have a problem..")
                    im_crop=[]
                    im_crop=np.copy(im_join)
            
            im_crop[im_crop<0]=0
            im_crop_color.append(im_crop)
            
    # fin de boucle
    if nbplan ==3 :
        img_color=np.zeros([im_crop.shape[0], im_crop.shape[1], 3],dtype='uint8')
        img_color[:,:,0]=np.array(im_crop_color[2], dtype='uint8')
        img_color[:,:,1]=np.array(im_crop_color[1], dtype='uint8')
        img_color[:,:,2]=np.array(im_crop_color[0], dtype='uint8')
        
    """    
    else :
    
        #conversion fits to png8
        s1=np.percentile(im_crop, 25)
        s2=np.percentile(im_crop,99.9999)*1.05
        im= fits_to_PIL (im_crop, s1, s2)
        # sortie im 
    """  
       
    
    # sauvegarde resultats
    if ext == '.fits' :
        # lit header du premier fichier
        hdulist1 = fits.open(ImgFiles[0], memmap=False)
        hdu1=hdulist1[0]
        # sauve fits
        hdu1.header['NAXIS2']=iw[0]
        hdu1.header['centerY']=centerY[0]
        hdu1.header['solar_R']=solarR[0]
        nom_fits_short=ImgFiles[0].split('.')[0]+"-"+ImgFiles[len(ImgFiles)-1].split('.')[0]+".fits"
        nom_fits=WorkDir+os.sep+nom_fits_short
        DiskHDU=fits.PrimaryHDU(im_crop,hdu1.header)
        DiskHDU.writeto(nom_fits, overwrite='True')
        
        # sauve png
        #im_join=np.array(im_join, dtype='uint16')
        s2=np.percentile(im_crop, 25)
        s1=np.percentile(im_crop,99.9999)*1.05
        im = seuil_image_force(im_crop,s1,s2)
        im_png=np.array(im, dtype='uint16')
        im_png=cv2.flip(im_png,0)
        nom_png_short=ImgFiles[0].split('.')[0]+"-"+ImgFiles[len(ImgFiles)-1].split('.')[0]+".png"
        nom_png=WorkDir+os.sep+nom_png_short
        cv2.imwrite(nom_png,im_png)
        
    if ext=='.png':
        if nbplan==1 :
            # sauve png
            #im_join=np.array(im_join, dtype='uint16')
            s2=np.percentile(im_crop, 25)
            s1=np.percentile(im_crop,99.9999)*1.05
            im = seuil_image_force(im_crop,s1,s2)
            im_png=np.array(im, dtype='uint16')
            im_png=cv2.flip(im_png,0)
            nom_png_short=ImgFiles[0].split('.')[0]+"-"+ImgFiles[len(ImgFiles)-1].split('.')[0]+".png"
            nom_png=WorkDir+os.sep+nom_png_short
            cv2.imwrite(nom_png,im_png)
        
        else :
            # sauve png
            #im_join=np.array(im_join, dtype='uint16')
            s2=np.percentile(img_color, 25)
            s1=np.percentile(img_color,99.9999)*1.05
            im = seuil_image_force(img_color,s1,s2)
            
            im_png=np.array(im, dtype='uint16')
            im_png=cv2.flip(im_png,0)
            nom_png_short=ImgFiles[0].split('.')[0]+"-"+ImgFiles[len(ImgFiles)-1].split('.')[0]+".png"
            nom_png=WorkDir+os.sep+nom_png_short
            cv2.imwrite(nom_png,im_png)
            
            # conversion BGR pour cv2 en RGB pour display
            destRGB = cv2.cvtColor(img_color, cv2.COLOR_BGR2RGB)
            im=seuil_image_force(destRGB, s1,s2)
            im=np.array(im, dtype='uint16')
            im=cv2.flip(im,0)

            
    
    
    print("")
    trad("Succès !!", "Success !!")
    if ext ==".fits":
        trad("Image fits : "+nom_fits_short, "Fits image : "+nom_fits_short)
    trad("Image png : "+nom_png_short, "Png image : "+nom_png_short)
    print("")
    
    return im, nbplan, nom_base
                
# routine de resizing circulaire

"""       
if event=="Rescale":
    flag_error=False
    os.chdir(WorkDir)
    for i in range(len(ImgFiles)) :
        base=(os.path.basename(ImgFiles[i]))
        basefich=os.path.splitext(base)[0]
        ImgFiles[i]=base
   
    
    if flag_error != True :
        # correction de scaling basée sur le rapport des deux diametres
        
        # valeur de reference
        #solarR_ref=int(values["-RAYREF-"])
        bx_ref=int(np.min(bx))
        by_ref=int(np.min(by))
        solarR_ref=bx_ref//2
        
         

    for i in range(len(ImgFiles)):
        #sc=solarR_ref/solarR[i]
        scx=bx_ref/bx[i]
        scy=by_ref/by[i]
        #scx=1
        #scy=1
        myimgR=np.copy(myimg[i])
        
        myimg2_sc=cv2.resize(myimg[i],(int(iw[i]*scx),int(ih[i]*scy)),interpolation=cv2.INTER_LINEAR_EXACT)
        print('Facteur de rescaling Image R en largeur et hauteur'+str(i+1)+' : ',scx, scy) 
        print(myimg2_sc.shape)
        
        w1=int((int(iw[i]*scx)-iw[i])/2)
        w2=-(int(iw[i]*scx)-iw[i]-w1)
        h1=int((int(ih[i]*scy)-ih[i])/2)
        h2=-(int(ih[i]*scy)-ih[i]-h1)
        if w2==0 :
            w2=iw[i]
        if h2==0 :
            h2=ih[i]
        print(w1,w2,h1,h2)
        
        
        if scx >=1 and scy >=1:
            # crop en largeur et hauteur
            myimg[i]=myimg2_sc[h1:h2,w1:w2]
            print('shape resized crop :',myimg[i].shape)
        
        if scx<1 and scy<1 :
            myimg[i][-h1:-h2,-w1:-w2]=myimg2_sc
            print('shape resized padding:',myimg[i].shape)
            
        if scy>= 1 and scy <1:
            myimg[i][:,-w1:w2]=myimg2_sc[h1:h2,:]
            print('shape resized y crop x padd:',myimg[i].shape)
        
        if scx<1 and scy>=1:
            myimg[i][-h1:h2,:]=myimg2_sc[:,w1:w2]
            print('shape resized y padd x crop:',myimg[i].shape)

        
 
    # On sauve
    for i in range(len(ImgFiles)):
        # sauve fits
        hdu1.header['NAXIS2']=ih[i]
        hdu1.header['centerY']=centerY[i]
        hdu1.header['solar_R']=solarR_ref
        nom_fits_short=ImgFiles[i].split('.')[0]+"_r.fits"
        nom_fits=WorkDir+nom_fits_short
        DiskHDU=fits.PrimaryHDU(myimg[i],hdu1.header)
        DiskHDU.writeto(nom_fits, overwrite='True')
        
        # sauve png
        #im_join=np.array(im_join, dtype='uint16')
        im_join=myimg[i]
        s2=np.percentile(im_join, 25)
        s1=np.percentile(im_join,99.9999)*1.05
        im = inti.seuil_image_force(im_join,s1,s2)
        im_png=np.array(im, dtype='uint16')
        im_png=cv2.flip(im_png,0)
        nom_png_short=ImgFiles[i].split('.')[0]+"_r.png"
        nom_png=WorkDir+nom_png_short
        cv2.imwrite(nom_png,im_png)
        print("Images rescaled", nom_fits_short, nom_png)
"""
            







